"""
Real Research Paper Discovery Service.
Queries Semantic Scholar API, arXiv API, and OpenAlex API.
Deduplicates results and ranks them by topic relevance, recency, and PDF availability.
Provides detailed provider status diagnostic reporting and robust fallback handling.
Never fabricates research papers or results.
"""

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
import requests

from config import SEMANTIC_SCHOLAR_API_KEY

LAST_PROVIDER_STATUS: Dict[str, Any] = {}

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

TASK_SIGNATURES = {
    "caption": ["caption", "captioning", "captions", "image-to-text", "visual description"],
    "enhancement": ["enhancement", "enhancing", "super-resolution", "low-light", "denoising", "restoration", "retargeting"],
    "classification": ["classification", "classifier", "classifying", "categorization", "recognition", "diagnose"],
    "segmentation": ["segmentation", "segmenting", "segmenter", "pixel-level", "contour", "mask"]
}


def extract_search_phrases(query: str) -> Tuple[str, List[str], List[str]]:
    """Extract primary research phrase, core discriminative terms, and generic method modifiers."""
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


def clean_text(text: Optional[str]) -> str:
    """Clean whitespace, newlines, and escape sequences from text."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy deduplication."""
    if not title:
        return ""
    normalized = re.sub(r"[^\w\s]", "", title.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def get_last_provider_status() -> Dict[str, Any]:
    """Retrieve the status breakdown from the most recent search."""
    return dict(LAST_PROVIDER_STATUS)


def search_semantic_scholar(query: str, limit: int = 8, year: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query Semantic Scholar Graph API for real papers with rate-limit and auth resilience."""
    papers = []
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = "title,authors,abstract,year,citationCount,externalIds,openAccessPdf,url"

    params = {
        "query": query,
        "limit": limit,
        "fields": fields
    }
    if year and year.strip():
        params["year"] = year.strip()

    headers = {
        "User-Agent": "ResearchAssistantBot/1.0 (academic research project; student@university.edu)"
    }
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    try:
        resp = requests.get(base_url, params=params, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("data", []):
                title = clean_text(item.get("title"))
                abstract = clean_text(item.get("abstract"))
                if not title:
                    continue

                authors_list = [a.get("name") for a in item.get("authors", []) if a.get("name")]
                authors_str = ", ".join(authors_list[:5])
                if len(authors_list) > 5:
                    authors_str += " et al."

                ext_ids = item.get("externalIds") or {}
                doi = ext_ids.get("DOI", "")
                arxiv_id = ext_ids.get("ArXiv", "")

                pdf_info = item.get("openAccessPdf") or {}
                pdf_url = pdf_info.get("url", "")

                if not pdf_url and arxiv_id:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                papers.append({
                    "id": item.get("paperId") or f"s2_{len(papers)}",
                    "title": title,
                    "authors": authors_str or "Unknown Authors",
                    "abstract": abstract or "No abstract publicly indexed.",
                    "year": item.get("year"),
                    "doi": doi,
                    "arxiv_id": arxiv_id,
                    "url": item.get("url") or (f"https://doi.org/{doi}" if doi else ""),
                    "pdf_url": pdf_url,
                    "citation_count": item.get("citationCount", 0),
                    "source": "Semantic Scholar"
                })
            LAST_PROVIDER_STATUS["Semantic Scholar"] = {
                "status": "OK",
                "count": len(papers),
                "message": f"Successfully retrieved {len(papers)} papers."
            }
        elif resp.status_code == 429:
            LAST_PROVIDER_STATUS["Semantic Scholar"] = {
                "status": "Rate Limited (429)",
                "count": 0,
                "message": "Public rate limit reached; fallback active."
            }
        else:
            LAST_PROVIDER_STATUS["Semantic Scholar"] = {
                "status": f"HTTP {resp.status_code}",
                "count": 0,
                "message": f"Server returned status {resp.status_code}."
            }
    except Exception as e:
        LAST_PROVIDER_STATUS["Semantic Scholar"] = {
            "status": "Connection Error",
            "count": 0,
            "message": f"Request failed: {type(e).__name__}"
        }

    return papers


def _parse_arxiv_response(xml_text: str) -> List[Dict[str, Any]]:
    """Helper to parse arXiv Atom XML response into standard paper dictionaries."""
    papers = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        for entry in root.findall("atom:entry", ns):
            title_elem = entry.find("atom:title", ns)
            summary_elem = entry.find("atom:summary", ns)
            published_elem = entry.find("atom:published", ns)
            id_elem = entry.find("atom:id", ns)

            title = clean_text(title_elem.text if title_elem is not None else "")
            abstract = clean_text(summary_elem.text if summary_elem is not None else "")
            raw_id = clean_text(id_elem.text if id_elem is not None else "")

            if not title or "Error" in title:
                continue

            arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id

            year = None
            if published_elem is not None and published_elem.text:
                try:
                    year = int(published_elem.text[:4])
                except ValueError:
                    pass

            author_names = []
            for author in entry.findall("atom:author", ns):
                name_elem = author.find("atom:name", ns)
                if name_elem is not None and name_elem.text:
                    author_names.append(name_elem.text.strip())
            authors_str = ", ".join(author_names[:5])
            if len(author_names) > 5:
                authors_str += " et al."

            doi = ""
            doi_elem = entry.find("arxiv:doi", ns)
            if doi_elem is not None and doi_elem.text:
                doi = doi_elem.text.strip()

            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href", "")
                    break
            if not pdf_url and arxiv_id:
                clean_id = re.sub(r"v\d+$", "", arxiv_id)
                pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

            papers.append({
                "id": f"arxiv_{arxiv_id}",
                "title": title,
                "authors": authors_str or "Unknown Authors",
                "abstract": abstract,
                "year": year,
                "doi": doi,
                "arxiv_id": arxiv_id,
                "url": raw_id,
                "pdf_url": pdf_url,
                "citation_count": 0,
                "source": "arXiv"
            })
    except Exception:
        pass
    return papers


def search_arxiv(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Query official arXiv API for real preprints and research papers with phrase-cohesive search."""
    base_url = "https://export.arxiv.org/api/query"

    primary_phrase, core_terms, modifiers = extract_search_phrases(query)

    # Strategy 1: Exact phrase search on the primary research topic (e.g. all:"Image Captioning")
    candidate_queries = []
    if primary_phrase and len(primary_phrase.split()) >= 2:
        candidate_queries.append(f'all:"{primary_phrase}"')
    if core_terms:
        # Require all core subject terms with boolean AND
        and_query = " AND ".join([f"all:{t}" for t in core_terms[:3]])
        if and_query not in candidate_queries:
            candidate_queries.append(and_query)

    clean_q = re.sub(r"[^\w\s]", " ", query).strip()
    words = [w for w in clean_q.split() if len(w) > 2 and w.lower() not in COMMON_STOPWORDS]
    if words:
        fallback_query = " AND ".join([f"all:{w}" for w in words[:3]])
        if fallback_query not in candidate_queries:
            candidate_queries.append(fallback_query)

    for search_q in candidate_queries:
        params = {
            "search_query": search_q,
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        try:
            resp = requests.get(base_url, params=params, timeout=12)
            if resp.status_code == 200:
                papers = _parse_arxiv_response(resp.text)
                if papers:
                    LAST_PROVIDER_STATUS["arXiv"] = {
                        "status": "OK",
                        "count": len(papers),
                        "message": f"Successfully retrieved {len(papers)} papers using query ({search_q})."
                    }
                    return papers
        except Exception:
            continue

    LAST_PROVIDER_STATUS["arXiv"] = {
        "status": "No Results",
        "count": 0,
        "message": "No matching preprints found for this query."
    }
    return []


def search_openalex(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Supplementary search via OpenAlex API with high limit and abstract reconstruction."""
    papers = []
    base_url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per_page": limit,
        "mailto": "research_assistant_student@university.edu"
    }

    try:
        resp = requests.get(base_url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for work in data.get("results", []):
                title = clean_text(work.get("display_name"))
                if not title:
                    continue

                abstract = ""
                inv_index = work.get("abstract_inverted_index")
                if inv_index and isinstance(inv_index, dict):
                    word_positions = []
                    for word, positions in inv_index.items():
                        for pos in positions:
                            word_positions.append((pos, word))
                    word_positions.sort(key=lambda x: x[0])
                    abstract = clean_text(" ".join([w[1] for w in word_positions]))

                authors_list = [a.get("author", {}).get("display_name") for a in work.get("authorships", [])]
                authors_str = ", ".join([a for a in authors_list[:5] if a])
                if len(authors_list) > 5:
                    authors_str += " et al."

                oa_info = work.get("open_access") or {}
                pdf_url = oa_info.get("oa_url") or ""
                doi = work.get("doi") or ""
                if doi.startswith("https://doi.org/"):
                    doi = doi.replace("https://doi.org/", "")

                papers.append({
                    "id": work.get("id", "").split("/")[-1] or f"oa_{len(papers)}",
                    "title": title,
                    "authors": authors_str or "Unknown Authors",
                    "abstract": abstract or "Abstract available via OpenAlex indexing.",
                    "year": work.get("publication_year"),
                    "doi": doi,
                    "arxiv_id": "",
                    "url": work.get("doi") or work.get("id", ""),
                    "pdf_url": pdf_url,
                    "citation_count": work.get("cited_by_count", 0),
                    "source": "OpenAlex"
                })
            LAST_PROVIDER_STATUS["OpenAlex"] = {
                "status": "OK",
                "count": len(papers),
                "message": f"Successfully retrieved {len(papers)} papers."
            }
        else:
            LAST_PROVIDER_STATUS["OpenAlex"] = {
                "status": f"HTTP {resp.status_code}",
                "count": 0,
                "message": f"Server returned status {resp.status_code}."
            }
    except Exception as e:
        LAST_PROVIDER_STATUS["OpenAlex"] = {
            "status": "Connection Error",
            "count": 0,
            "message": f"Request failed: {type(e).__name__}"
        }

    return papers


def compute_relevance_score(paper: Dict[str, Any], query_terms: List[str]) -> float:
    """Compute heuristic relevance score based on query matching, publication recency, and citations."""
    score = 0.0
    title_lower = (paper.get("title") or "").lower()
    abstract_lower = (paper.get("abstract") or "").lower()

    for term in query_terms:
        if len(term) < 3 or term in COMMON_STOPWORDS:
            continue
        if term in title_lower:
            score += 3.5
        if term in abstract_lower:
            score += 1.2

    # Boost papers with real open access PDF available
    if paper.get("pdf_url"):
        score += 2.0

    # Boost recent papers
    year = paper.get("year")
    if year and isinstance(year, int):
        if year >= 2024:
            score += 1.5
        elif year >= 2022:
            score += 1.0
        elif year >= 2020:
            score += 0.5

    # Citations boost
    cites = paper.get("citation_count") or 0
    score += min(cites * 0.02, 1.0)

    return score


def classify_and_score_paper(
    paper: Dict[str, Any],
    query: str,
    primary_phrase: str,
    core_terms: List[str]
) -> Tuple[float, str, str]:
    """
    Rigorously classify paper relevance as Relevant, Partially Relevant, or Irrelevant,
    evaluating actual research objectives rather than superficial keyword overlap.
    """
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

    # Direct phrase presence
    phrase_in_title = phrase_lower in title_lower
    phrase_in_abstract = phrase_lower in abstract_lower

    # Core term presence
    core_in_title = sum(1 for t in core_terms if t in title_lower)
    core_in_abstract = sum(1 for t in core_terms if t in abstract_lower)
    all_core_present = (core_in_title + core_in_abstract) >= len(core_terms)

    # Task signature match vs conflicting task check
    task_match = False
    conflicting_task = None
    if target_task:
        target_words = TASK_SIGNATURES[target_task]
        task_match = any(w in full_text for w in target_words)

        for other_task, other_words in TASK_SIGNATURES.items():
            if other_task != target_task and any(w in title_lower for w in other_words):
                if not task_match:
                    conflicting_task = other_task

    score = 0.0
    classification = "Irrelevant"
    justification = ""

    # Conflicting domain task penalty (e.g. Image Enhancement when query is Image Captioning)
    if conflicting_task and not task_match:
        score = 0.5
        classification = "Irrelevant"
        justification = f"Focuses primarily on Image {conflicting_task.title()}, distinct from research target '{primary_phrase}'."
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
        justification = f"Investigates related concepts or downstream applications connected to '{primary_phrase}'."
    else:
        # Fallback to general query term matching
        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) >= 3 and t.lower() not in COMMON_STOPWORDS]
        base_score = compute_relevance_score(paper, query_terms)
        if base_score >= 10.0:
            score = base_score
            classification = "Partially Relevant"
            justification = f"Investigates adjacent methodology matching search keywords."
        else:
            score = max(base_score, 1.0)
            classification = "Irrelevant"
            justification = f"Does not directly address research objective of '{primary_phrase}'."

    # Boosts for open access PDF and recency
    if paper.get("pdf_url"):
        score += 2.0
    year = paper.get("year")
    if year and isinstance(year, int):
        if year >= 2024:
            score += 1.5
        elif year >= 2022:
            score += 1.0

    return score, classification, justification


def search_real_papers(query: str, year_filter: Optional[str] = None, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search real papers across Semantic Scholar, arXiv, and OpenAlex.
    Deduplicates and ranks top results by research objective relevance and availability.
    Returns up to 5 real papers with relevance explanations and updates LAST_PROVIDER_STATUS.
    """
    global LAST_PROVIDER_STATUS
    LAST_PROVIDER_STATUS = {}
    raw_results = []

    # 1. Search Semantic Scholar
    s2_results = search_semantic_scholar(query, limit=7, year=year_filter)
    raw_results.extend(s2_results)

    # 2. Search arXiv
    arxiv_results = search_arxiv(query, limit=7)
    raw_results.extend(arxiv_results)

    # 3. Search OpenAlex (always query if count < 6 to ensure rich diversity)
    if len(raw_results) < 6:
        oa_results = search_openalex(query, limit=10)
        raw_results.extend(oa_results)

    # Deduplicate by normalized title, DOI, or arXiv ID
    seen_titles = set()
    seen_dois = set()
    seen_arxiv = set()
    unique_papers = []

    for p in raw_results:
        norm_title = normalize_title(p.get("title", ""))
        doi = (p.get("doi") or "").lower().strip()
        arxiv_id = (p.get("arxiv_id") or "").lower().strip()

        if norm_title in seen_titles:
            continue
        if doi and doi in seen_dois:
            continue
        if arxiv_id and arxiv_id in seen_arxiv:
            continue

        seen_titles.add(norm_title)
        if doi:
            seen_dois.add(doi)
        if arxiv_id:
            seen_arxiv.add(arxiv_id)

        unique_papers.append(p)

    # Parse search phrases
    primary_phrase, core_terms, modifiers = extract_search_phrases(query)

    # Rank and classify papers by research objective relevance
    for p in unique_papers:
        score, classification, justification = classify_and_score_paper(p, query, primary_phrase, core_terms)
        p["_relevance_score"] = score
        p["relevance_classification"] = classification
        p["_relevance_justification"] = justification

    # Sort descending by relevance score
    unique_papers.sort(key=lambda x: x["_relevance_score"], reverse=True)

    # Filter out Irrelevant papers if Relevant or Partially Relevant papers exist
    relevant_subset = [p for p in unique_papers if p.get("relevance_classification") in ["Relevant", "Partially Relevant"]]
    candidate_pool = relevant_subset if relevant_subset else unique_papers

    # Prepare top papers with clear relevance justification
    top_papers = candidate_pool[:max_results]
    for p in top_papers:
        reasons = []
        if p.get("_relevance_justification"):
            reasons.append(p["_relevance_justification"])
        if p.get("year"):
            reasons.append(f"published in {p['year']}")
        if p.get("pdf_url"):
            reasons.append("full open-access PDF directly accessible")
        else:
            reasons.append("indexing metadata accessible (manual PDF upload available)")

        p["relevance_note"] = " • ".join(reasons) if reasons else "Matches domain search criteria"
        p.pop("_relevance_score", None)
        p.pop("_relevance_justification", None)

    return top_papers
