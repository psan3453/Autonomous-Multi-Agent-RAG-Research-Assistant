import requests

url = "https://api.semanticscholar.org/graph/v1/paper/search"
params = {
    "query": "Parameter-Efficient Fine-Tuning LoRA",
    "limit": 3,
    "fields": "title,authors,abstract,year,citationCount,externalIds,openAccessPdf,url"
}
headers = {
    "User-Agent": "ResearchAssistantBot/1.0 (academic research project; mailto:student@university.edu)"
}

try:
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    print("S2 Status code:", resp.status_code)
    print("S2 Response header:", resp.headers.get("content-type"))
    print("S2 Body preview:", resp.text[:300])
except Exception as e:
    print("S2 Request error:", e)
