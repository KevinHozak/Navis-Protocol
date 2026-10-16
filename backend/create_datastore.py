import time
import os
from google.cloud import discoveryengine

project_id = os.environ.get("NAVIS_GCP_PROJECT", "")
location = "global"
data_store_id = "navis-vault-datastore"
bucket_name = os.environ.get("NAVIS_GCS_BUCKET", "")
gcs_uri = f"gs://{bucket_name}/*"


def create_data_store():
    client = discoveryengine.DataStoreServiceClient()
    parent = client.collection_path(project_id, location, "default_collection")

    data_store = discoveryengine.DataStore(
        display_name="Navis Vault",
        industry_vertical=discoveryengine.IndustryVertical.GENERIC,
        content_config=discoveryengine.DataStore.ContentConfig.CONTENT_REQUIRED,
    )

    request = discoveryengine.CreateDataStoreRequest(
        parent=parent,
        data_store=data_store,
        data_store_id=data_store_id,
    )

    print(f"Creating Data Store: {data_store_id}...")
    try:
        operation = client.create_data_store(request=request)
        response = operation.result()
        print(f"Created Data Store: {response.name}")
    except Exception as e:
        if "Already exists" in str(e) or "ALREADY_EXISTS" in str(e):
            print("Data store already exists.")
        else:
            raise e


def import_documents():
    client = discoveryengine.DocumentServiceClient()
    parent = client.branch_path(
        project=project_id,
        location=location,
        data_store=data_store_id,
        branch="default_branch",
    )

    request = discoveryengine.ImportDocumentsRequest(
        parent=parent,
        gcs_source=discoveryengine.GcsSource(
            input_uris=[gcs_uri], data_schema="content"
        ),
        reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
    )

    print(f"Importing documents from {gcs_uri}...")
    operation = client.import_documents(request=request)
    print("Import operation started. Waiting for completion...")
    response = operation.result()
    print("Import completed successfully!")
    print(response)


if __name__ == "__main__":
    if not project_id or not bucket_name:
        raise SystemExit("Set NAVIS_GCP_PROJECT and NAVIS_GCS_BUCKET before importing.")
    # create_data_store()
    time.sleep(2)
    import_documents()
