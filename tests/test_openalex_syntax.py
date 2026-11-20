import sys
sys.path.insert(0, ".")
import requests
from services.paper_search import clean_text

for q in ["Image Captioning", "Image Captioning using Deep Learning", "image captioning", "Image Enhancement", "Image Classification", "Image Segmentation"]:
    resp = requests.get("https://api.openalex.org/works", params={"search": q, "per_page": 3}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        titles = [clean_text(w.get("display_name")) for w in data.get("results", [])]
        print(f"OpenAlex '{q}' -> {titles}")
    else:
        print(f"OpenAlex '{q}' -> Status {resp.status_code}")
