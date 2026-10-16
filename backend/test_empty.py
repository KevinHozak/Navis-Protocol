import os

from google.cloud import discoveryengine

project_id = os.environ.get("NAVIS_GCP_PROJECT", "").strip()
if not project_id:
    raise SystemExit("Set NAVIS_GCP_PROJECT before querying the datastore.")

client = discoveryengine.SearchServiceClient()
serving_config = client.serving_config_path(
    project=project_id,
    location="global",
    data_store="navis-vault-datastore",
    serving_config="default_config",
)
request = discoveryengine.SearchRequest(
    serving_config=serving_config, query="", page_size=10
)
try:
    response = client.search(request)
    print(f"Success! Found {len(list(response.results))} results for empty query")
except Exception as e:
    print(f"Error: {e}")
