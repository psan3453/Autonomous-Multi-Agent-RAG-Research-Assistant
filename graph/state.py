"""
LangGraph state definitions for Multi-Agent Literature Review, Gap Analysis & Proposal Generation.
"""

from typing import TypedDict, List, Dict, Any, Optional


class ResearchState(TypedDict):
    """Global state shared across the LangGraph research agents."""
    project_id: str
    topic: str
    
    # Selected paper metadata
    paper_a: Dict[str, Any]
    paper_b: Dict[str, Any]
    
    # Retrieved textual contexts
    context_a: str
    context_b: str
    
    # Node 1: Independent Analysis
    analysis_a: Dict[str, Any]
    analysis_b: Dict[str, Any]
    
    # Node 2: Comparative Matrix & Scope Alignment
    comparative_matrix: Dict[str, Any]
    
    # Node 3 & 4 & 5: Research Gap Discovery & Verification
    raw_gaps: List[Dict[str, Any]]
    gaps: List[Dict[str, Any]]
    gaps_summary: str
    
    # Node 6: Research Proposals
    proposals: List[Dict[str, Any]]
    ranking_rationale: str
    
    # Execution tracking & diagnostics
    current_step: str
    errors: List[str]
    diagnostics: Dict[str, Any]
