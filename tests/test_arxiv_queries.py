import urllib.parse
import xml.etree.ElementTree as ET
import requests
import re

queries = [
    "Agentic RAG for Medical Question Answering",
    "Parameter-Efficient Fine-Tuning LoRA vs Full Fine-Tuning",
    "Hallucination Mitigation in Retrieval-Augmented Generation",
    "human activity and suspicious behavior",
    "deep fake image identification",
    "Graph Neural Networks for Drug Repurposing"
]

for q in queries:
    clean_q = re.sub(r"[^\w\s]", " ", q).strip()
    words = [w for w in clean_q.split() if len(w) > 2]
    # Current arxiv method:
    q_all = f"all:{' '.join(words)}"
    
    resp = requests.get(
        "http://export.arxiv.org/api/query",
        params={"search_query": q_all, "start": 0, "max_results": 3, "sortBy": "relevance", "sortOrder": "descending"},
        timeout=10
    )
    root = ET.fromstring(resp.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)
    print(f"Query: '{q[:35]}' -> arXiv raw matches: {len(entries)}")
    if not entries:
        # Test AND/OR or fallback
        ti_q = " OR ".join([f"all:{w}" for w in words[:4]])
        resp2 = requests.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": ti_q, "start": 0, "max_results": 3, "sortBy": "relevance", "sortOrder": "descending"},
            timeout=10
        )
        root2 = ET.fromstring(resp2.text)
        entries2 = root2.findall("atom:entry", ns)
        print(f"   Fallback multi-term matches: {len(entries2)}")
