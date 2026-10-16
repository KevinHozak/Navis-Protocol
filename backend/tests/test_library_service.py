import sqlite3

import pytest

from services import library_service


def test_dashboard_distinguishes_missing_malformed_empty_and_populated_sources(tmp_path, monkeypatch):
    db_path = tmp_path / "Library" / "Library_Intelligence.db"
    db_path.parent.mkdir()
    monkeypatch.setattr(library_service, "DB_PATH", str(db_path))
    monkeypatch.setattr(library_service, "NAVIS_ROOT", str(tmp_path))

    with pytest.raises(library_service.LibraryDataError) as missing:
        library_service.get_library_dashboard_metrics()
    assert missing.value.code == "library_database_missing"

    db_path.write_bytes(b"not a sqlite database")
    with pytest.raises(library_service.LibraryDataError) as malformed:
        library_service.get_library_dashboard_metrics()
    assert malformed.value.code == "library_schema_invalid"

    db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE library_vectors (category TEXT, file_path TEXT, last_modified TEXT, chunk_text TEXT)")
    assert library_service.get_library_dashboard_metrics() == {
        "total_documents": 0,
        "categories": [],
        "recent_documents": [],
    }

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO library_vectors VALUES (?, ?, ?, ?)",
            ("Notes", str(tmp_path / "Library/Notes/fixture.md"), "2026-10-08", "private fixture content"),
        )
        conn.execute(
            "INSERT INTO library_vectors VALUES (?, ?, ?, ?)",
            ("Notes", str(tmp_path / "Library/Notes/undated.md"), None, "another private fixture"),
        )
    dashboard = library_service.get_library_dashboard_metrics()
    assert dashboard["total_documents"] == 2
    assert dashboard["categories"] == [{"name": "Notes", "count": 2}]
    undated = next(doc for doc in dashboard["recent_documents"] if doc["id"] == "Library/Notes/undated.md")
    assert undated["last_modified"] is None


def test_read_only_uri_preserves_unc_paths():
    assert library_service._readonly_db_uri(r"\\vault\share\Library\index #1.db") == (
        "file:////vault/share/Library/index%20%231.db?mode=ro"
    )


def test_cloud_search_requires_explicit_project_and_bucket(monkeypatch):
    monkeypatch.delenv("NAVIS_GCP_PROJECT", raising=False)
    monkeypatch.delenv("NAVIS_GCS_BUCKET", raising=False)
    with pytest.raises(library_service.LibraryDataError) as missing:
        library_service.search_library("synthetic query")
    assert missing.value.code == "library_search_unconfigured"

    monkeypatch.setenv("NAVIS_GCP_PROJECT", "synthetic-project")
    with pytest.raises(library_service.LibraryDataError) as partial:
        library_service.search_library("synthetic query")
    assert partial.value.code == "library_search_unconfigured"


def test_cloud_search_uses_configured_project_and_bucket(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace
    from unittest.mock import Mock

    monkeypatch.setenv("NAVIS_GCP_PROJECT", "synthetic-project")
    monkeypatch.setenv("NAVIS_GCS_BUCKET", "synthetic-bucket")
    client = Mock()
    client.serving_config_path.return_value = "synthetic-serving-config"
    client.search.return_value = SimpleNamespace(results=[
        SimpleNamespace(document=SimpleNamespace(derived_struct_data={
            "link": "gs://synthetic-bucket/Library/Notes/fixture.md",
            "snippets": [{"snippet": "Synthetic <b>example</b>"}],
        }))
    ])
    discovery = SimpleNamespace(SearchServiceClient=Mock(return_value=client), SearchRequest=Mock())
    google = ModuleType("google")
    cloud = ModuleType("google.cloud")
    google.cloud = cloud
    cloud.discoveryengine = discovery
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    results = library_service.search_library("fixture", "Notes")
    assert client.serving_config_path.call_args.kwargs["project"] == "synthetic-project"
    assert results[0]["id"] == "Library/Notes/fixture.md"
    assert results[0]["snippet"] == "Synthetic **example**"
