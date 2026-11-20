import sys
sys.path.insert(0, ".")
import requests
from services.paper_search import _parse_arxiv_response

queries = [
    "Image Captioning using Deep Learning",
    "Image Enhancement",
    "Image Classification",
    "Image Segmentation"
]

for raw_q in queries:
    print(f"\n=================== TESTING QUERY: {raw_q} ===================")
    # Strategy 1: Exact phrase on the primary topic
    # e.g., if 'image captioning' in query -> all:"image captioning"
    # let's test:
    # 1. all:"<full or key phrase>"
    # 2. ti:"..." OR abs:"..."
    # 3. all:term1 AND all:term2
    
    # Try exact phrase for the first 2 content words:
    words = [w for w in raw_q.split() if w.lower() not in {"using", "based", "via", "through", "with", "for", "and", "or", "in", "on", "of", "to", "a", "an", "the"}]
    key_phrase = f"{words[0]} {words[1]}" if len(words) >= 2 else raw_q
    
    q1 = f'all:"{key_phrase}"'
    params = {'search_query': q1, 'start': 0, 'max_results': 5, 'sortBy': 'relevance', 'sortOrder': 'descending'}
    resp = requests.get('https://export.arxiv.org/api/query', params=params, timeout=10)
    papers = _parse_arxiv_response(resp.text)
    print(f"arXiv all:\"{key_phrase}\" -> {[p['title'] for p in papers]}")
