import sys
sys.path.insert(0, ".")
import re
from typing import List, Dict, Any, Tuple

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

def extract_search_phrases(query: str) -> Tuple[str, List[str], List[str]]:
    """
    Extract:
    1. primary_phrase: e.g. 'image captioning'
    2. core_terms: e.g. ['image', 'captioning']
    3. modifier_terms: e.g. ['deep', 'learning']
    """
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()
    raw_tokens = [w for w in clean_q.split() if w]
    
    # Filter stopwords
    content_tokens = [w for w in raw_tokens if w.lower() not in COMMON_STOPWORDS]
    
    core_terms = []
    modifier_terms = []
    for t in content_tokens:
        if t.lower() in GENERIC_METHOD_MODIFIERS:
            modifier_terms.append(t.lower())
        else:
            core_terms.append(t.lower())
            
    # Primary phrase is first 2 content tokens if available, or core terms
    if len(content_tokens) >= 2 and content_tokens[0].lower() not in GENERIC_METHOD_MODIFIERS:
        primary_phrase = f"{content_tokens[0]} {content_tokens[1]}"
    elif core_terms:
        primary_phrase = " ".join(core_terms[:2])
    else:
        primary_phrase = " ".join(content_tokens[:2])
        
    return primary_phrase, core_terms, modifier_terms

# Test extraction
queries = [
    "Image Captioning using Deep Learning",
    "Image Enhancement",
    "Image Classification",
    "Image Segmentation",
    "Human Activity Recognition and Suspicious Behavior",
    "Fake News Detection using Deep Learning"
]

for q in queries:
    phrase, core, mods = extract_search_phrases(q)
    print(f"Query: '{q}' -> Primary Phrase: '{phrase}', Core: {core}, Modifiers: {mods}")
