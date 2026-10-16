import json
import os
from google.cloud import storage
from google.cloud import discoveryengine

project_id = os.environ.get("NAVIS_GCP_PROJECT", "")
location = "global"
data_store_id = "navis-vault-datastore"
bucket_name = os.environ.get("NAVIS_GCS_BUCKET", "")
metadata_filename = "metadata.jsonl"


def generate_and_upload_metadata():
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    print(f"Scanning bucket gs://{bucket_name} for .md files...")
    blobs = bucket.list_blobs()

    with open(metadata_filename, "w", encoding="utf-8") as f:
        count = 0
        for blob in blobs:
            if blob.name.endswith(".md"):
                # Safe ID: alphanumeric and underscores only, length up to 63
                # Replace unsupported characters with underscores
                safe_id = "".join([c if c.isalnum() else "_" for c in blob.name])[:60]

                record = {
                    "id": safe_id,
                    "structData": {"title": blob.name},
                    "content": {
                        "mimeType": "text/plain",
                        "uri": f"gs://{bucket_name}/{blob.name}",
                    },
                }
                f.write(json.dumps(record) + "\n")
                count += 1

    print(f"Generated {count} records in {metadata_filename}")

    print("Uploading metadata.jsonl to GCS...")
    blob = bucket.blob(metadata_filename)
    blob.upload_from_filename(metadata_filename)
    print(f"Uploaded to gs://{bucket_name}/{metadata_filename}")


def import_documents():
    client = discoveryengine.DocumentServiceClient()
    parent = client.branch_path(
        project=project_id,
        location=location,
        data_store=data_store_id,
        branch="default_branch",
    )

    gcs_uri = f"gs://{bucket_name}/{metadata_filename}"
    print(f"Triggering Vertex AI Search import from {gcs_uri}...")

    request = discoveryengine.ImportDocumentsRequest(
        parent=parent,
        gcs_source=discoveryengine.GcsSource(
            input_uris=[gcs_uri], data_schema="document"
        ),
        reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
    )

    operation = client.import_documents(request=request)
    print("Import operation started. Waiting for completion...")
    response = operation.result()
    print("Import completed successfully!")
    print(response)


if __name__ == "__main__":
    if not project_id or not bucket_name:
        raise SystemExit("Set NAVIS_GCP_PROJECT and NAVIS_GCS_BUCKET before uploading.")
    generate_and_upload_metadata()
    import_documents()
