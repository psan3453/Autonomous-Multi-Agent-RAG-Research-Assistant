import sys
sys.path.insert(0, ".")
import re
import requests
from typing import List, Dict, Any, Tuple
from services.paper_search import _parse_arxiv_response, clean_text, normalize_title

COMMON_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "over", "after", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "vs", "versus", "using", "based", "via", "through"
}

GENERIC_METHOD_MODIFIERS = {
    "deep", "learning", "machine", "neural", "network", "networks", "model", "models",
    "approach", "method", "methods", "system", "systems", "framework", "study", "analysis",
    "survey", "algorithm", "algorithms", "technique", "techniques", "ai", "artificial",
    "intelligence", "nlp", "evaluation", "comparative", "investigation"
}

# Task-specific conflicting signatures
TASK_SIGNATURES = {
    "caption": ["caption", "captioning", "captions", "image-to-text", "visual description"],
    "enhancement": ["enhancement", "enhancing", "super-resolution", "low-light", "denoising", "restoration", "retargeting"],
    "classification": ["classification", "classifier", "classifying", "categorization", "recognition", "diagnose"],
    "segmentation": ["segmentation", "segmenting", "segmenter", "pixel-level", "contour", "mask"]
}

def extract_search_phrases(query: str) -> Tuple[str, List[str], List[str]]:
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()
    raw_tokens = [w for w in clean_q.split() if w]
    content_tokens = [w for w in raw_tokens if w.lower() not in COMMON_STOPWORDS]
    
    core_terms = []
    modifier_terms = []
    for t in content_tokens:
        if t.lower() in GENERIC_METHOD_MODIFIERS:
            modifier_terms.append(t.lower())
        else:
            core_terms.append(t.lower())
            
    if len(content_tokens) >= 2 and content_tokens[0].lower() not in GENERIC_METHOD_MODIFIERS:
        primary_phrase = f"{content_tokens[0]} {content_tokens[1]}"
    elif core_terms:
        primary_phrase = " ".join(core_terms[:2])
    else:
        primary_phrase = " ".join(content_tokens[:2])
        
    return primary_phrase, core_terms, modifier_terms

def classify_and_score_paper(paper: Dict[str, Any], query: str, primary_phrase: str, core_terms: List[str]) -> Tuple[float, str, str]:
    title_lower = (paper.get("title") or "").lower()
    abstract_lower = (paper.get("abstract") or "").lower()
    full_text = f"{title_lower} {abstract_lower}"
    phrase_lower = primary_phrase.lower()

    # Determine target task category
    target_task = None
    for task_key, terms in TASK_SIGNATURES.items():
        if any(t in query.lower() for t in terms):
            target_task = task_key
            break

    # Check for direct phrase match
    phrase_in_title = phrase_lower in title_lower
    phrase_in_abstract = phrase_lower in abstract_lower
    
    # Check core terms presence
    core_in_title = sum(1 for t in core_terms if t in title_lower)
    core_in_abstract = sum(1 for t in core_terms if t in abstract_lower)
    all_core_present = (core_in_title + core_in_abstract) >= len(core_terms)

    # Check task signature
    task_match = False
    conflicting_task = None
    if target_task:
        target_words = TASK_SIGNATURES[target_task]
        task_match = any(w in full_text for w in target_words)
        
        # Check if the paper actually belongs to a DIFFERENT conflicting task
        for other_task, other_words in TASK_SIGNATURES.items():
            if other_task != target_task and any(w in title_lower for w in other_words):
                if not task_match:
                    conflicting_task = other_task

    # Scoring & Classification logic
    score = 0.0
    classification = "Irrelevant"
    justification = ""

    if conflicting_task and not task_match:
        # Paper explicitly belongs to a different computer vision task!
        score = 0.5
        classification = "Irrelevant"
        justification = f"Focuses on Image {conflicting_task.title()}, which is distinct from {primary_phrase}."
        return score, classification, justification

    if phrase_in_title:
        score += 20.0
        classification = "Relevant"
        justification = f"Direct match for primary topic '{primary_phrase}' in paper title."
    elif phrase_in_abstract and all_core_present:
        score += 15.0
        classification = "Relevant"
        justification = f"Primary topic '{primary_phrase}' explicitly investigated in research abstract."
    elif task_match and all_core_present:
        score += 12.0
        classification = "Relevant"
        justification = f"Addresses core task objectives ({', '.join(core_terms)}) in methodology and evaluation."
    elif task_match or (phrase_in_abstract and "image" in full_text):
        score += 7.0
        classification = "Partially Relevant"
        justification = f"Investigates related concepts or downstream applications connected to {primary_phrase}."
    else:
        score = 1.0
        classification = "Irrelevant"
        justification = f"Does not address core research objective of '{primary_phrase}'."

    # Boosts for PDF and recency
    if paper.get("pdf_url"):
        score += 2.0
    year = paper.get("year")
    if year and isinstance(year, int):
        if year >= 2024:
            score += 1.5
        elif year >= 2022:
            score += 1.0

    return score, classification, justification

# Run audit on the 4 queries
queries = [
    "Image Captioning using Deep Learning",
    "Image Enhancement",
    "Image Classification",
    "Image Segmentation"
]

for q in queries:
    phrase, core, mods = extract_search_phrases(q)
    print(f"\n=======================================================")
    print(f"AUDITING QUERY: '{q}' (Phrase: '{phrase}')")
    print(f"=======================================================")
    
    # Query arXiv with phrase
    params = {'search_query': f'all:"{phrase}"', 'start': 0, 'max_results': 5, 'sortBy': 'relevance', 'sortOrder': 'descending'}
    resp = requests.get('https://export.arxiv.org/api/query', params=params, timeout=12)
    papers = _parse_arxiv_response(resp.text)
    
    for idx, p in enumerate(papers, 1):
        score, classification, justification = classify_and_score_paper(p, q, phrase, core)
        print(f"\nPaper {idx}: {p['title']}")
        print(f"  Year: {p.get('year')} | Source: {p.get('source')} | PDF: {bool(p.get('pdf_url'))}")
        print(f"  Classification: [{classification}] (Score: {score:.1f})")
        print(f"  Justification: {justification}")
        print(f"  Abstract excerpt: {p.get('abstract', '')[:140]}...")
