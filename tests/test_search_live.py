import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.paper_search import search_semantic_scholar, search_arxiv, search_openalex, search_real_papers

query = "Parameter-Efficient Fine-Tuning LoRA"
print(f"Testing query: '{query}'")

print("\n--- 1. Testing arXiv ---")
try:
    arxiv_res = search_arxiv(query, limit=3)
    print(f"arXiv returned: {len(arxiv_res)} papers")
    for p in arxiv_res:
        print(f"  - [{p.get('source')}] {p.get('title')} ({p.get('year')}) | PDF: {bool(p.get('pdf_url'))}")
except Exception as e:
    print(f"arXiv failed with exception: {e}")

print("\n--- 2. Testing Semantic Scholar ---")
try:
    s2_res = search_semantic_scholar(query, limit=3)
    print(f"Semantic Scholar returned: {len(s2_res)} papers")
    for p in s2_res:
        print(f"  - [{p.get('source')}] {p.get('title')} ({p.get('year')}) | PDF: {bool(p.get('pdf_url'))}")
except Exception as e:
    print(f"Semantic Scholar failed with exception: {e}")

print("\n--- 3. Testing OpenAlex ---")
try:
    oa_res = search_openalex(query, limit=3)
    print(f"OpenAlex returned: {len(oa_res)} papers")
    for p in oa_res:
        print(f"  - [{p.get('source')}] {p.get('title')} ({p.get('year')}) | PDF: {bool(p.get('pdf_url'))}")
except Exception as e:
    print(f"OpenAlex failed with exception: {e}")

print("\n--- 4. Testing search_real_papers ---")
try:
    all_res = search_real_papers(query, max_results=5)
    print(f"search_real_papers returned: {len(all_res)} papers")
    for i, p in enumerate(all_res):
        print(f"  {i+1}. {p.get('title')} ({p.get('year')}) [{p.get('source')}]")
        print(f"     Authors: {p.get('authors')}")
        print(f"     PDF: {p.get('pdf_url')}")
        print(f"     Relevance: {p.get('relevance_note')}")
except Exception as e:
    print(f"search_real_papers failed with exception: {e}")
