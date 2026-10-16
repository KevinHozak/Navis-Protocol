import os
import sys

# Add backend directory to path
sys.path.insert(0, r"C:\Projects\Navis-Protocol\backend")

from services.goodreads_parser import parse_goodreads_library

if __name__ == "__main__":
    result = parse_goodreads_library()
    if "System Error" in result:
        print("ERROR:", result["System Error"])
    else:
        print(f"Read: {len(result['Read'])}")
        print(f"To Read: {len(result['To Read'])}")
        print(f"Currently Reading: {len(result['Currently Reading'])}")
        if result['Read']:
            print("Sample Read Book:", result['Read'][0])
