import requests

try:
    response = requests.get(
        "http://localhost:8000/api/v1/library/search?q=test", timeout=5
    )
    print(f"Status: {response.status_code}")
    print(f"Data: {len(response.json().get('results', []))} results returned.")
except Exception as e:
    print(f"Error: {e}")
