import sys

sys.path.append("c:/Projects/Navis-Protocol/backend")
from services.library_service import search_library

print("Testing search...")
results = search_library("test", None)
print(f"Results: {results}")
