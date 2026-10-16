import sys
import json

sys.path.append("c:/Projects/Navis-Protocol/backend")
from services.library_service import search_library

print("Testing search...")
results = search_library("test", None)
with open("search_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print(f"Done, found {len(results)} results")
