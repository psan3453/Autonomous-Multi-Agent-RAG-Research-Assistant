import sys
sys.path.insert(0, ".")
import requests
from services.paper_search import _parse_arxiv_response

test_queries = [
    'all:"image captioning"',
    'ti:"image captioning"',
    'all:image AND all:captioning',
    'all:Image Captioning Deep Learning'
]

for q in test_queries:
    params = {'search_query': q, 'start': 0, 'max_results': 3, 'sortBy': 'relevance', 'sortOrder': 'descending'}
    resp = requests.get('https://export.arxiv.org/api/query', params=params, timeout=10)
    papers = _parse_arxiv_response(resp.text)
    print(f"Query: {q} -> {[p['title'] for p in papers]}")
