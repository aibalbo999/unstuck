import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.external_data_google import fetch_google_search_catalysts
from backend.config import GOOGLE_SEARCH_API_KEY, GOOGLE_CSE_ID

print(f"GOOGLE_SEARCH_API_KEY loaded: {bool(GOOGLE_SEARCH_API_KEY)}")
print(f"GOOGLE_CSE_ID loaded: {bool(GOOGLE_CSE_ID)}")

if GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID:
    print("Testing fetch_google_search_catalysts...")
    identity = {"official_name": "Taiwan Semiconductor"}
    results = fetch_google_search_catalysts("TSM", "Taiwan Semiconductor", identity)
    print(f"Results fetched: {len(results)}")
    if results:
        print("Sample result:")
        print(results[0])
else:
    print("Google Search is NOT configured.")
