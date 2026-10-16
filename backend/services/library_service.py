import sqlite3
import os
from pathlib import Path
from urllib.parse import quote

NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
DB_PATH = os.path.join(NAVIS_ROOT, "Library", "Library_Intelligence.db")


class LibraryDataError(Exception):
    """A safe, machine-readable Library data-source failure."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _readonly_db_uri(db_path):
    db_path = os.fspath(db_path)
    if db_path.startswith(("\\\\", "//")):
        # Keep the URI authority empty so SQLite accepts Windows UNC paths.
        unc_path = db_path.replace("\\", "/").lstrip("/")
        return f"file:////{quote(unc_path, safe='/')}?mode=ro"
    return f"{Path(db_path).resolve().as_uri()}?mode=ro"


def _open_library():
    if not os.path.isfile(DB_PATH):
        raise LibraryDataError("library_database_missing")
    try:
        conn = sqlite3.connect(_readonly_db_uri(DB_PATH), uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as error:
        raise LibraryDataError("library_database_unreadable") from error


def get_library_dashboard_metrics():
    conn = _open_library()
    try:
        cur = conn.cursor()

        # Total unique documents (file_path)
        cur.execute("SELECT COUNT(DISTINCT file_path) as count FROM library_vectors")
        total_docs = cur.fetchone()["count"]

        # Categories breakdown
        cur.execute("""
            SELECT category, COUNT(DISTINCT file_path) as doc_count 
            FROM library_vectors 
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category 
            ORDER BY doc_count DESC 
            LIMIT 12
        """)
        categories = [
            {"name": row["category"], "count": row["doc_count"]}
            for row in cur.fetchall()
        ]

        # Recent documents
        cur.execute("""
            SELECT category, file_path, MAX(last_modified) as modified_time
            FROM library_vectors
            GROUP BY file_path
            ORDER BY modified_time DESC
            LIMIT 15
        """)
        recent_docs = []
        for row in cur.fetchall():
            filename = os.path.basename(row["file_path"])
            name = filename.replace(".md", "")

            # Convert absolute path to Vault API relative path
            rel_path = os.path.relpath(row["file_path"], NAVIS_ROOT)
            rel_path = rel_path.replace("\\", "/")

            recent_docs.append(
                {
                    "id": rel_path,
                    "name": name,
                    "category": row["category"] or "Uncategorized",
                    "path": row["file_path"],
                    "last_modified": row["modified_time"],
                }
            )

        conn.close()

        return {
            "total_documents": total_docs,
            "categories": categories,
            "recent_documents": recent_docs,
        }
    except sqlite3.Error as error:
        raise LibraryDataError("library_schema_invalid") from error
    finally:
        conn.close()


def search_library(query: str = None, category: str = None):
    project_id = os.environ.get("NAVIS_GCP_PROJECT", "").strip()
    bucket_name = os.environ.get("NAVIS_GCS_BUCKET", "").strip()
    if not project_id or not bucket_name:
        raise LibraryDataError("library_search_unconfigured")

    from google.cloud import discoveryengine
    import time

    # We allow empty queries to let Vertex AI Search fetch default recent/relevant documents
    # when a user selects a category without typing.
    try:
        client = discoveryengine.SearchServiceClient()
        serving_config = client.serving_config_path(
            project=project_id,
            location="global",
            data_store="navis-vault-datastore",
            serving_config="default_config",
        )

        search_query = (
            query if query else (category if category and category != "All" else "")
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=search_query,
            page_size=50,
            content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                    return_snippet=True
                )
            ),
        )

        # If category filtering is required, we can apply an expression if the custom schema supports it.
        # For unstructured raw markdown, metadata filtering requires JSONL ingestion mapping.
        # As we imported raw MD, we'll only rely on the query text.

        response = client.search(request)

        results = []
        for result in response.results:
            # result.document contains the matched document details
            document = result.document

            # The URI usually looks like gs://bucket/path/to/file.md
            gcs_uri = document.derived_struct_data.get("link", "")

            # Extract filename from GCS URI or struct data
            bucket_prefix = f"gs://{bucket_name}/"
            if gcs_uri.startswith(bucket_prefix):
                file_path = gcs_uri.removeprefix(bucket_prefix)
            else:
                file_path = "Unknown File"

            filename = os.path.basename(file_path)
            name = filename.replace(".md", "")

            # Reconstruct an absolute-ish path for the UI
            # (UI uses 'path' to open the file in obsidian or viewer)
            abs_path = os.path.join(NAVIS_ROOT, file_path.replace("/", "\\"))

            # Snippet text from Vertex AI
            snippet = ""
            if document.derived_struct_data.get("snippets"):
                snippet_html = document.derived_struct_data["snippets"][0].get(
                    "snippet", ""
                )
                # Simple strip HTML tags like <b> and </b> that Vertex uses for highlights
                snippet = snippet_html.replace("<b>", "**").replace("</b>", "**")

            # Determine category based on folder path as a fallback since unstructured doesn't have native metadata
            derived_category = "Uncategorized"
            path_parts = file_path.split("/")
            if len(path_parts) > 1:
                # If it's in the Library folder, the category is the subfolder (e.g. Tech, Psychology)
                if path_parts[0] == "Library" and len(path_parts) > 2:
                    derived_category = path_parts[1]
                else:
                    derived_category = path_parts[0]

            # If the user selected a category, we filter client-side since raw unstructured lacks native metadata filters
            if (
                category
                and category.lower() != derived_category.lower()
                and category != "All"
            ):
                continue

            results.append(
                {
                    "id": file_path,
                    "name": name,
                    "category": derived_category,
                    "path": abs_path,
                    "last_modified": int(
                        time.time()
                    ),  # Unstructured API doesn't return modified time directly in search response
                    "snippet": snippet,
                }
            )

        return results

    except Exception as error:
        # Provider errors can contain request data or private document details.
        raise LibraryDataError("library_search_unavailable") from error
