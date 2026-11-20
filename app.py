"""
Autonomous Multi-Agent RAG Research Assistant
Final-Year Engineering Project Dashboard
Streamlit Frontend integrating LangGraph Agents, FAISS CPU, BGE Embeddings,
PyMuPDF, Semantic Scholar & arXiv APIs, Gemini & Groq LLMs, and python-docx.
"""

import os
import sys
import time
import uuid
import html
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import streamlit as st
import pandas as pd

# Ensure workspace root is first in sys.path
_WORKSPACE_ROOT = str(Path(__file__).resolve().parent)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)
elif sys.path[0] != _WORKSPACE_ROOT:
    sys.path.remove(_WORKSPACE_ROOT)
    sys.path.insert(0, _WORKSPACE_ROOT)

import config
from config import (
    GEMINI_API_KEY,
    GROQ_API_KEY,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GROQ_MODEL,
    EMBEDDING_MODEL_NAME,
    THEME_NAVY,
    THEME_ACCENT_BLUE,
)

# Resilient diagnostic log path resolution
DIAGNOSTIC_LOG_PATH = getattr(
    config,
    "DIAGNOSTIC_LOG_PATH",
    getattr(config, "LOGS_DIR", Path(_WORKSPACE_ROOT) / "storage" / "logs") / "diagnostics.log"
)
DIAGNOSTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
from database.db import (
    init_db,
    create_project,
    get_projects,
    get_project,
    update_project_status,
    save_papers,
    get_papers,
    set_paper_selected,
    get_selected_papers,
    update_paper_pdf_info,
    save_analysis_results,
    get_analysis_results,
    save_chat_message,
    get_chat_history,
    get_dashboard_stats,
)
from services.paper_search import search_real_papers, get_last_provider_status
from services.pdf_processor import download_paper_pdf, save_uploaded_pdf, extract_and_chunk_pdf
from services.embedding_service import get_embedder
from services.vector_store import FAISSVectorStore
from services.rag_service import RAGService
from services.llm_service import get_llm_service, log_diagnostic
from graph.workflow import execute_multi_agent_workflow
from reports.report_generator import generate_research_docx_report

# Initialize SQLite database on startup
init_db()


def load_project_analysis_data(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Unified, fail-safe loader guaranteeing synchronized retrieval of:
    - Comparative matrix (with embedded Paper A & Paper B analyses)
    - Research gaps (with verification status & literature findings)
    - Research proposals (3 ranked directions)
    Synchronizes both SQLite database and Streamlit session_state across reruns.
    """
    if not project_id:
        return None

    # 1. Query SQLite database
    db_data = get_analysis_results(project_id)
    if (
        db_data and
        db_data.get("comparative_matrix") and
        bool(db_data.get("comparative_matrix", {}).get("table")) and
        db_data.get("gaps") and
        db_data.get("proposals") and
        "Analysis encountered an error" not in str(db_data.get("comparative_matrix"))
    ):
        st.session_state[f"analysis_data_{project_id}"] = db_data
        st.session_state["cached_analysis_data"] = db_data
        st.session_state["cached_project_id"] = project_id
        return db_data

    # 2. Check session_state cache if DB is transitional or during intermediate rerun
    cached = st.session_state.get(f"analysis_data_{project_id}")
    if cached and cached.get("comparative_matrix") and bool(cached.get("comparative_matrix", {}).get("table")):
        return cached

    if (
        st.session_state.get("cached_project_id") == project_id and
        st.session_state.get("cached_analysis_data") and
        st.session_state["cached_analysis_data"].get("comparative_matrix")
    ):
        return st.session_state["cached_analysis_data"]

    return db_data


def render_proposal_full_card(idx: int, prop: dict) -> str:
    is_rec = bool(prop.get("recommended_for_student"))
    card_cls = "proposal-card proposal-recommended" if is_rec else "proposal-card"
    rec_badge = '<span class="badge badge-green">⭐ RECOMMENDED CAPSTONE PROJECT</span>' if is_rec else ""
    pub_pot = html.escape(str(prop.get("publication_potential") or "IEEE/ACM Student Conference Track"))
    
    rank_val = prop.get("rank", idx + 1)
    feas_val = html.escape(str(prop.get("feasibility") or "High"))
    title_val = html.escape(str(prop.get("research_title") or prop.get("proposed_title") or "Untitled Proposal"))
    abstract_val = html.escape(str(prop.get("abstract") or "Abstract generated based on verified gap synthesis."))
    prob_val = html.escape(str(prop.get("problem_statement") or ""))
    mot_val = html.escape(str(prop.get("research_motivation") or prop.get("motivation") or ""))
    hyp_val = html.escape(str(prop.get("research_hypothesis") or ""))

    # 1. Top Proposal Card
    top_card = (
        f'<div class="{card_cls}">'
        f'<div style="float: right;">{rec_badge} <span class="badge badge-purple">{pub_pot}</span></div>'
        f'<div class="proposal-rank">Priority Rank #{rank_val} • Feasibility: {feas_val}</div>'
        f'<div class="proposal-title">{title_val}</div>'
        f'<p style="margin-top: 8px;"><strong>1. Abstract:</strong> {abstract_val}</p>'
        f'<p><strong>2. Problem Statement:</strong> {prob_val}</p>'
        f'<p><strong>3. Research Motivation:</strong> {mot_val}</p>'
        f'<p><strong>4. Formal Research Hypothesis:</strong> <em>{hyp_val}</em></p>'
        f'</div>'
    )

    # Capstone Rationale Alert (if recommended)
    capstone_alert = ""
    if is_rec and prop.get("capstone_recommendation_rationale"):
        cap_rationale = html.escape(str(prop.get("capstone_recommendation_rationale")))
        capstone_alert = (
            f'<div style="background-color: #ECFDF5; border-left: 4px solid #10B981; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; border-top: 1px solid #A7F3D0; border-right: 1px solid #A7F3D0; border-bottom: 1px solid #A7F3D0;">'
            f'<div style="color: #065F46; font-weight: 700; font-size: 14px; margin-bottom: 4px;">🎓 Capstone Recommendation Rationale:</div>'
            f'<div style="color: #047857; font-size: 13.5px; line-height: 1.5;">{cap_rationale}</div>'
            f'</div>'
        )

    # 2. Feasibility Assessment Card (6 metrics)
    ranking = prop.get("ranking_breakdown", {})
    r_items = [
        ("Student Feasibility", ranking.get("student_feasibility", "High")),
        ("Contribution", ranking.get("research_contribution", "High")),
        ("Complexity", ranking.get("technical_complexity", "Medium")),
        ("Datasets", ranking.get("dataset_availability", "High")),
        ("Hardware", ranking.get("hardware_feasibility", "High")),
        ("Evaluation", ranking.get("evaluation_possibility", "High"))
    ]
    metrics_cols = "".join([
        f'<div style="flex: 1; min-width: 120px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 10px; margin: 4px; text-align: center;">'
        f'<div style="font-size: 11px; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;">{html.escape(lbl)}</div>'
        f'<div style="font-size: 20px; font-weight: 700; color: #172554; margin-top: 5px;">{html.escape(str(val))}</div>'
        f'</div>'
        for lbl, val in r_items
    ])
    feasibility_card = (
        f'<div style="background-color: #FFFFFF; border-radius: 12px; padding: 22px; border: 1px solid #CBD5E1; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
        f'<div class="section-heading-blue" style="margin-top: 0; margin-bottom: 14px;">📊 Multi-Criteria Feasibility Assessment</div>'
        f'<div style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px;">{metrics_cols}</div>'
        f'</div>'
    )

    # 3. Technical Specifications Card (Sections 5 to 13)
    objs = prop.get("research_objectives", [])
    if isinstance(objs, list):
        objs_html = "".join([f'<li style="color: #1F2937; margin-bottom: 4px;">{html.escape(str(o))}</li>' for o in objs])
        objs_content = f'<ul style="margin-top: 4px; padding-left: 20px;">{objs_html}</ul>'
    else:
        objs_content = f'<p style="color: #1F2937;">{html.escape(str(objs))}</p>'

    method_val = html.escape(str(prop.get("proposed_methodology") or prop.get("proposed_solution") or ""))
    arch_val = html.escape(str(prop.get("system_architecture") or prop.get("technical_architecture") or ""))
    
    algos = prop.get("algorithms_and_models") or prop.get("algorithms") or []
    algos_str = html.escape(", ".join(algos) if isinstance(algos, list) else str(algos))
    
    dsets = prop.get("dataset_recommendations") or prop.get("dataset_suggestions") or []
    dsets_str = html.escape(", ".join(dsets) if isinstance(dsets, list) else str(dsets))
    
    setup_val = html.escape(str(prop.get("experimental_setup") or prop.get("experimental_plan") or ""))
    
    metrics = prop.get("evaluation_metrics") or []
    metrics_str = html.escape(", ".join(metrics) if isinstance(metrics, list) else str(metrics))
    
    baseline_val = html.escape(str(prop.get("baseline_comparisons") or prop.get("baseline_comparison") or "Compares against surveyed baselines."))
    contrib_val = html.escape(str(prop.get("expected_contribution") or "Novel synthesis resolving surveyed gap"))

    tech_card = (
        f'<div style="background-color: #FFFFFF; border-radius: 12px; padding: 22px; border: 1px solid #CBD5E1; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
        f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">'
        f'<div>'
        f'<div class="section-heading-blue" style="margin-top: 0;">🎯 5. Research Objectives</div>'
        f'{objs_content}'
        f'<div class="section-heading-blue">🏗️ 6. Proposed Methodology</div>'
        f'<p style="color: #1F2937; font-size: 13.5px; line-height: 1.5;">{method_val}</p>'
        f'<div class="section-heading-blue">📐 7. System Architecture Pipeline</div>'
        f'<div style="background: #F1F5F9; border-left: 3px solid #0284C7; padding: 10px 14px; border-radius: 6px; font-size: 13px; color: #0369A1; margin-top: 6px;">{arch_val}</div>'
        f'<div class="section-heading-blue">⚙️ 8. Algorithms & Models</div>'
        f'<p style="color: #1F2937; font-size: 13.5px;">{algos_str}</p>'
        f'</div>'
        f'<div>'
        f'<div class="section-heading-blue" style="margin-top: 0;">💾 9. Dataset Recommendations</div>'
        f'<p style="color: #1F2937; font-size: 13.5px;">{dsets_str}</p>'
        f'<div class="section-heading-blue">🧪 10. Experimental Setup</div>'
        f'<p style="color: #1F2937; font-size: 13.5px; line-height: 1.5;">{setup_val}</p>'
        f'<div class="section-heading-blue">📈 11. Evaluation Metrics</div>'
        f'<p style="color: #1F2937; font-size: 13.5px;">{metrics_str}</p>'
        f'<div class="section-heading-blue">🔬 12. Baseline Comparisons</div>'
        f'<p style="color: #475569; font-size: 13px;"><em>{baseline_val}</em></p>'
        f'<div class="section-heading-blue">🌟 13. Expected Contribution</div>'
        f'<div style="background: #ECFDF5; border-left: 3px solid #10B981; padding: 10px 14px; border-radius: 6px; font-size: 13px; color: #065F46;">{contrib_val}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    # 4. Roadmap & Constraints Card (Sections 14 to 16)
    steps = prop.get("implementation_roadmap") or prop.get("implementation_steps") or []
    if steps and isinstance(steps, list):
        steps_html = "".join([f'<div style="margin-bottom: 6px; font-size: 13.5px; color: #1F2937;"><strong>Phase {s_idx}:</strong> {html.escape(str(step))}</div>' for s_idx, step in enumerate(steps, 1)])
    else:
        steps_html = f'<div style="font-size: 13.5px; color: #1F2937;">{html.escape(str(steps))}</div>'

    hw_val = html.escape(str(prop.get("hardware_requirements") or "Standard laptop or Google Colab free tier"))
    risk_val = html.escape(str(prop.get("limitations_and_risks") or prop.get("risks_and_limitations") or "Standard variance."))

    roadmap_card = (
        f'<div style="background-color: #FFFFFF; border-radius: 12px; padding: 22px; border: 1px solid #CBD5E1; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.02);">'
        f'<div class="section-heading-blue" style="margin-top: 0; margin-bottom: 12px;">🗺️ 14. 4-Phase Implementation Roadmap</div>'
        f'{steps_html}'
        f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 18px; padding-top: 14px; border-top: 1px solid #E2E8F0;">'
        f'<div>'
        f'<div class="section-heading-blue" style="margin-top: 0;">💻 15. Hardware Requirements</div>'
        f'<p style="color: #1F2937; font-size: 13.5px;">{hw_val}</p>'
        f'</div>'
        f'<div>'
        f'<div class="section-heading-blue" style="margin-top: 0;">⚠️ 16. Limitations & Risks</div>'
        f'<div style="background: #FFFBEB; border-left: 3px solid #F59E0B; padding: 10px 14px; border-radius: 6px; font-size: 13px; color: #92400E;">{risk_val}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    return top_card + capstone_alert + feasibility_card + tech_card + roadmap_card

# Page configuration
st.set_page_config(
    page_title="Autonomous Multi-Agent RAG Research Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Academic Dark Navy & Crisp White CSS Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Academic Hero Header */
    .hero-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0369A1 100%);
        color: #FFFFFF;
        padding: 24px 30px;
        border-radius: 14px;
        margin-bottom: 22px;
        box-shadow: 0 4px 15px rgba(15, 23, 42, 0.12);
    }
    .hero-title {
        font-size: 25px;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-bottom: 4px;
        color: #F8FAFC;
    }
    .hero-subtitle {
        font-size: 13.5px;
        color: #94A3B8;
        font-weight: 400;
    }

    /* Metric Cards */
    .metric-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 18px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .metric-num {
        font-size: 28px;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Academic Paper Card */
    .paper-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
    }
    .paper-card-selected {
        background: #F0FDF4;
        border-left: 6px solid #16A34A;
        border: 1px solid #BBF7D0;
    }
    .paper-title {
        font-size: 16px;
        font-weight: 600;
        color: #0F172A;
        margin-bottom: 5px;
    }
    .paper-authors {
        font-size: 13px;
        color: #475569;
        margin-bottom: 8px;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 3px 9px;
        font-size: 11px;
        font-weight: 600;
        border-radius: 20px;
        margin-right: 5px;
        margin-bottom: 3px;
    }
    .badge-navy { background: #0F172A; color: #FFFFFF; }
    .badge-blue { background: #DBEAFE; color: #1D4ED8; }
    .badge-green { background: #DCFCE7; color: #15803D; }
    .badge-amber { background: #FEF3C7; color: #B45309; }
    .badge-red { background: #FEE2E2; color: #B91C1C; }
    .badge-purple { background: #F3E8FF; color: #7E22CE; }

    /* Gap Card */
    .gap-card {
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
        border-left: 5px solid #2563EB !important;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 18px;
        border-top: 1px solid #E2E8F0;
        border-right: 1px solid #E2E8F0;
        border-bottom: 1px solid #E2E8F0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }
    .gap-card-unverified {
        border-left: 5px solid #DC2626 !important;
        background-color: #FFFDFD !important;
    }
    .gap-title {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #172554 !important;
        margin-bottom: 8px !important;
    }
    .gap-evidence {
        background-color: #F8FAFC !important;
        border-radius: 6px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 13px !important;
        border-left: 3px solid #94A3B8;
        color: #1F2937 !important;
    }
    .gap-evidence strong {
        color: #0F172A !important;
    }
    .gap-evidence small {
        color: #475569 !important;
    }
    .gap-card p {
        color: #1F2937 !important;
        font-size: 14px;
        line-height: 1.5;
    }
    .gap-card strong {
        color: #0F172A !important;
    }

    /* Proposal Card & High-Contrast Typography */
    .proposal-card {
        background-color: #F8FAFC !important;
        color: #1F2937 !important;
        border-radius: 10px;
        padding: 22px;
        margin-bottom: 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    }
    .proposal-recommended {
        border-top: 5px solid #16A34A !important;
        background-color: #F0FDF4 !important;
        border-color: #BBF7D0 !important;
    }
    .proposal-title {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #172554 !important;
        margin-top: 8px !important;
        margin-bottom: 12px !important;
        line-height: 1.35;
    }
    .proposal-rank {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #475569 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .proposal-card p {
        color: #1F2937 !important;
        font-size: 14px !important;
        line-height: 1.6 !important;
        margin-bottom: 10px !important;
    }
    .proposal-card strong {
        color: #172554 !important;
        font-weight: 600 !important;
    }
    .proposal-card em {
        color: #334155 !important;
    }

    /* Entire Proposal Tab Panel Styled as High-Contrast White Card */
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
        border-radius: 12px !important;
        padding: 24px !important;
        border: 1px solid #CBD5E1 !important;
        margin-top: 10px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] p,
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] span,
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] div,
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] li {
        color: #1F2937;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] [data-testid="stMetricValue"] div {
        color: #172554 !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] [data-testid="stMetricLabel"] div {
        color: #475569 !important;
        font-weight: 600 !important;
    }

    /* Section Headings & Contrast Helpers */
    .section-heading-blue {
        color: #1D4ED8 !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        margin-top: 14px !important;
        margin-bottom: 6px !important;
    }
    .text-body-dark {
        color: #1F2937 !important;
        font-size: 14px !important;
        line-height: 1.6 !important;
    }
    .text-label-grey {
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    div[data-testid="stMetricValue"] > div {
        color: #172554 !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetricLabel"] > div {
        color: #475569 !important;
        font-weight: 600 !important;
    }

    /* Chat bubble */
    .chat-bubble-user {
        background: #2563EB;
        color: white;
        padding: 12px 18px;
        border-radius: 16px 16px 2px 16px;
        margin-bottom: 12px;
        max-width: 80%;
        margin-left: auto;
    }
    .chat-bubble-assistant {
        background: #F1F5F9;
        color: #0F172A;
        padding: 14px 20px;
        border-radius: 16px 16px 16px 2px;
        margin-bottom: 14px;
        max-width: 90%;
        border: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# Session state initialization
if "active_project_id" not in st.session_state:
    st.session_state.active_project_id = None
if "active_topic" not in st.session_state:
    st.session_state.active_topic = ""
if "navigation_page" not in st.session_state:
    st.session_state.navigation_page = "Home Dashboard"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_project_id" not in st.session_state:
    st.session_state.pending_project_id = None

# Sidebar Navigation
with st.sidebar:
    st.markdown("### 🎓 Academic Research System")
    st.markdown("**Autonomous Multi-Agent RAG**")
    st.markdown("---")

    # Project Selector or Creator
    projects = get_projects()
    project_options = {p["id"]: f"{p['name'][:35]}..." for p in projects}
    project_keys = list(project_options.keys())

    # 1. Process pending project activation if requested by page actions
    if st.session_state.get("pending_project_id"):
        pending = st.session_state.pop("pending_project_id")
        if pending in project_keys:
            st.session_state.active_project_id = pending
            st.session_state["sidebar_active_project_selector"] = pending

    # 2. Reconcile active_project_id and selector widget state BEFORE selectbox is instantiated
    current_selector = st.session_state.get("sidebar_active_project_selector")
    if current_selector and current_selector != "-- Create New Project --" and current_selector in project_keys:
        if st.session_state.active_project_id != current_selector:
            st.session_state.active_project_id = current_selector
            proj_data = get_project(current_selector)
            if proj_data:
                st.session_state.active_topic = proj_data["topic"]
                st.session_state.chat_history = get_chat_history(current_selector)
    elif st.session_state.active_project_id and st.session_state.active_project_id in project_keys:
        st.session_state["sidebar_active_project_selector"] = st.session_state.active_project_id
        if not st.session_state.active_topic:
            proj_data = get_project(st.session_state.active_project_id)
            if proj_data:
                st.session_state.active_topic = proj_data["topic"]
    else:
        st.session_state.active_project_id = None
        st.session_state.active_topic = ""
        st.session_state["sidebar_active_project_selector"] = "-- Create New Project --"

    def _on_project_selection_change():
        selected = st.session_state.get("sidebar_active_project_selector")
        if selected == "-- Create New Project --" or not selected:
            st.session_state.active_project_id = None
            st.session_state.active_topic = ""
            st.session_state.chat_history = []
            st.session_state.navigation_page = "Research Topic Search"
        else:
            st.session_state.active_project_id = selected
            proj_data = get_project(selected)
            if proj_data:
                st.session_state.active_topic = proj_data["topic"]
                st.session_state.chat_history = get_chat_history(selected)

    selector_options = ["-- Create New Project --"] + project_keys
    current_val = st.session_state.get("sidebar_active_project_selector", "-- Create New Project --")
    default_idx = selector_options.index(current_val) if current_val in selector_options else 0

    st.selectbox(
        "📁 Active Research Project",
        options=selector_options,
        index=default_idx,
        format_func=lambda x: "-- Create New Project --" if x == "-- Create New Project --" else project_options.get(x, x),
        key="sidebar_active_project_selector",
        on_change=_on_project_selection_change
    )

    if st.session_state.active_project_id:
        proj_obj = get_project(st.session_state.active_project_id)
        proj_title = proj_obj["name"] if proj_obj else st.session_state.active_topic
        st.caption(f"📌 Active: **{proj_title[:38]}**")
    else:
        st.caption("ℹ️ No active project. Search or select one above.")

    st.markdown("---")
    st.markdown("### 🧭 Workflow Navigation")

    nav_pages = [
        "Home Dashboard",
        "Research Topic Search",
        "Top Five Papers",
        "Paper Processing",
        "RAG Research Chat",
        "Paper Comparison",
        "Research Gap Discovery",
        "Research Idea Generation",
        "Report Generation"
    ]

    try:
        curr_idx = nav_pages.index(st.session_state.navigation_page)
    except ValueError:
        curr_idx = 0

    page_choice = st.radio(
        "Go to page:",
        options=nav_pages,
        index=curr_idx,
        label_visibility="collapsed"
    )
    if page_choice != st.session_state.navigation_page:
        st.session_state.navigation_page = page_choice
        st.rerun()

    st.markdown("---")
    # API & Diagnostics Drawer
    with st.expander("🔑 LLM & Model Engine", expanded=False):
        has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        has_groq = bool(os.getenv("GROQ_API_KEY"))

        st.markdown(f"**Gemini Model:** `{DEFAULT_GEMINI_MODEL}` ({'✅ Ready' if has_gemini else '⚠️ Missing'})")
        st.markdown(f"**Groq Model:** `{DEFAULT_GROQ_MODEL}` ({'✅ Ready' if has_groq else 'ℹ️ Not set'})")
        st.markdown(f"**Local Embedder:** `BAAI/bge-small-en-v1.5`")
        st.markdown(f"**Vector Store:** `FAISS CPU (Local)`")

        user_gem_key = st.text_input("Update Gemini Key", type="password", value="")
        user_groq_key = st.text_input("Update Groq Key", type="password", value="")
        if st.button("Apply API Keys"):
            if user_gem_key:
                get_llm_service().update_keys(gemini_key=user_gem_key)
            if user_groq_key:
                get_llm_service().update_keys(groq_key=user_groq_key)
            st.success("API keys updated!")
            st.rerun()

    # Diagnostics log expander
    with st.expander("🛠️ Diagnostics & Logs", expanded=False):
        if DIAGNOSTIC_LOG_PATH.exists():
            with open(DIAGNOSTIC_LOG_PATH, "r", encoding="utf-8") as lf:
                log_lines = lf.readlines()
            st.code("".join(log_lines[-20:]) if log_lines else "No diagnostic logs yet.", language="text")
        else:
            st.caption("No log entries.")

# Top Hero Banner
st.markdown("""
<div class="hero-header">
    <div class="hero-title">Autonomous Multi-Agent RAG Research Assistant</div>
    <div class="hero-subtitle">
        Systematic Literature Review • FAISS-Grounded RAG • LangGraph Multi-Agent Gap Discovery • Publication Roadmaps
    </div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# PAGE 1: HOME DASHBOARD
# ==============================================================================
if st.session_state.navigation_page == "Home Dashboard":
    stats = get_dashboard_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Research Projects</div>
            <div class="metric-num">{stats['total_projects']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Papers Discovered</div>
            <div class="metric-num">{stats['total_papers']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Processed & Indexed</div>
            <div class="metric-num">{stats['processed_papers']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Research Gaps Identified</div>
            <div class="metric-num">{stats['total_gaps']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    c_left, c_right = st.columns([1.6, 1.0])

    with c_left:
        st.markdown("### 📋 Recent Research Projects")
        all_projs = get_projects()
        if not all_projs:
            st.info("No research projects found yet. Start by entering a research topic on the next page!")
            if st.button("🚀 Start New Research Topic Search", type="primary"):
                st.session_state.navigation_page = "Research Topic Search"
                st.rerun()
        else:
            for p in all_projs[:5]:
                with st.container():
                    p_cols = st.columns([3, 1, 1])
                    with p_cols[0]:
                        st.markdown(f"**{p['name']}**")
                        st.caption(f"Topic: {p['topic']} • Created: {p['created_at'][:10]}")
                    with p_cols[1]:
                        st.caption(f"Status: `{p['status']}`")
                    with p_cols[2]:
                        if st.button("Open", key=f"open_proj_{p['id']}"):
                            st.session_state.active_project_id = p["id"]
                            st.session_state.active_topic = p["topic"]
                            st.session_state.pending_project_id = p["id"]
                            st.session_state.chat_history = get_chat_history(p["id"])
                            st.session_state.navigation_page = "Top Five Papers"
                            st.rerun()
                    st.divider()

    with c_right:
        st.markdown("### 🔬 Multi-Agent Research Workflow")
        st.markdown("""
        1. **Live Discovery**: Connects directly to Semantic Scholar & arXiv APIs for 5 real peer-reviewed studies.
        2. **PyMuPDF Ingestion**: Preserves exact page numbers, sections, and builds local FAISS CPU embeddings.
        3. **Dual RAG Engine**: Balanced cross-paper similarity retrieval enforcing strict provenance citations.
        4. **LangGraph Agent Swarm**:
           - **Analysis Agent**: 15-point extraction (datasets, models, results, explicit limitations).
           - **Gap Discovery Agent**: 7-category gap analysis enforcing the **Critical Evidence Rule**.
           - **Proposal Agent**: Formulates 3 prioritized directions with formal testable hypotheses.
        5. **Docx Report Engine**: One-click generation of academic Word reports.
        """)
        if st.button("Start Literature Review Now →", type="primary"):
            st.session_state.navigation_page = "Research Topic Search"
            st.rerun()


# ==============================================================================
# PAGE 2: RESEARCH TOPIC SEARCH
# ==============================================================================
elif st.session_state.navigation_page == "Research Topic Search":
    st.markdown("### 🔎 Research Topic Search")
    st.markdown("Enter your research topic. The system will search **Semantic Scholar** and **arXiv** for real papers.")

    st.caption("Quick Topic Presets:")
    presets = [
        "Agentic RAG for Medical Question Answering",
        "Parameter-Efficient Fine-Tuning LoRA vs Full Fine-Tuning",
        "Hallucination Mitigation in Retrieval-Augmented Generation",
        "Multimodal Large Language Models for Autonomous Robotics"
    ]
    p_cols = st.columns(len(presets))
    for i, p_text in enumerate(presets):
        if p_cols[i].button(p_text, key=f"preset_{i}"):
            st.session_state.active_topic = p_text

    topic_input = st.text_area(
        "Enter Research Topic / Inquiry:",
        value=st.session_state.active_topic,
        placeholder="e.g. Graph Neural Networks for Drug-Target Interaction Prediction",
        height=90
    )

    col_y, col_src = st.columns([1, 2])
    with col_y:
        year_filter = st.text_input("Optional Year Range / Filter (e.g. 2023-2025)", value="")
    with col_src:
        st.markdown("**Active Discovery Services:**")
        st.markdown("`Semantic Scholar API` • `arXiv Atom Feed` • `OpenAlex Open Access`")

    if st.button("🔍 Search Real Research Papers", type="primary"):
        if not topic_input.strip():
            st.error("Please enter a research topic to search.")
        else:
            with st.spinner("Connecting to Semantic Scholar, arXiv & OpenAlex APIs... Fetching real papers..."):
                query_topic = topic_input.strip()
                papers = search_real_papers(query_topic, year_filter=year_filter, max_results=5)
                provider_status = get_last_provider_status()

                if not papers:
                    st.warning("No papers were returned by the academic APIs for this inquiry.")
                    st.markdown("#### 📡 Discovery Provider Diagnostics:")
                    for prov, stat in provider_status.items():
                        st.write(f"- **{prov}:** {stat.get('status')} — {stat.get('message')}")
                    st.info("Tip: Try adjusting query terms or removing punctuation/year filters.")
                else:
                    proj_id = create_project(query_topic)
                    st.session_state.active_project_id = proj_id
                    st.session_state.active_topic = query_topic
                    st.session_state.pending_project_id = proj_id
                    st.session_state[f"discovered_papers_{proj_id}"] = papers
                    save_papers(proj_id, papers)

                    prov_summary = []
                    for prov, stat in provider_status.items():
                        c = stat.get("count", 0)
                        if c > 0:
                            prov_summary.append(f"{prov}: {c}")
                        elif "Rate" in stat.get("status", ""):
                            prov_summary.append(f"{prov}: Rate-Limited (fallback active)")
                    st.session_state.last_search_summary = ", ".join(prov_summary) if prov_summary else "Real academic APIs"

                    st.success(f"Discovered {len(papers)} real research papers! ({st.session_state.last_search_summary})")
                    st.session_state.navigation_page = "Top Five Papers"
                    st.rerun()


# ==============================================================================
# PAGE 3: TOP FIVE PAPERS
# ==============================================================================
elif st.session_state.navigation_page == "Top Five Papers":
    if not st.session_state.active_project_id:
        st.warning("Please search for a research topic or select an active project first.")
        if st.button("Go to Search Page"):
            st.session_state.navigation_page = "Research Topic Search"
            st.rerun()
    else:
        st.markdown(f"### 📚 Top Five Discovered Papers for: *{st.session_state.active_topic}*")
        st.markdown("Review the discovered real papers below. **Select exactly TWO papers** for in-depth comparative review and RAG analysis.")

        papers = get_papers(st.session_state.active_project_id)
        if not papers and st.session_state.get(f"discovered_papers_{st.session_state.active_project_id}"):
            save_papers(st.session_state.active_project_id, st.session_state[f"discovered_papers_{st.session_state.active_project_id}"])
            papers = get_papers(st.session_state.active_project_id)

        if not papers:
            st.info("No papers recorded for this project yet. Please initiate an academic search below.")
            if st.button("🔎 Run Search for Current Topic", type="primary"):
                with st.spinner("Searching Semantic Scholar, arXiv & OpenAlex..."):
                    discovered = search_real_papers(st.session_state.active_topic or "Machine Learning", max_results=5)
                    if discovered:
                        save_papers(st.session_state.active_project_id, discovered)
                        st.session_state[f"discovered_papers_{st.session_state.active_project_id}"] = discovered
                        st.rerun()
                    else:
                        st.error("No papers discovered. Please go to the Search page to refine keywords.")
        else:
            selected_count = sum(1 for p in papers if p.get("is_selected"))
            
            status_col1, status_col2 = st.columns([2, 1])
            with status_col1:
                if selected_count == 2:
                    st.success("✅ Exactly 2 papers selected! You can now proceed to PDF Ingestion & Processing.")
                elif selected_count < 2:
                    st.warning(f"⚠️ Selected {selected_count} / 2 papers. Please select {2 - selected_count} more paper(s).")
                else:
                    st.error(f"❌ You have selected {selected_count} papers. Please select exactly 2 papers.")

            with status_col2:
                proceed_btn = st.button(
                    "Proceed to Paper Processing →",
                    type="primary",
                    disabled=(selected_count != 2)
                )
                if proceed_btn:
                    st.session_state.navigation_page = "Paper Processing"
                    st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

            for p in papers:
                is_sel = bool(p.get("is_selected"))
                card_class = "paper-card paper-card-selected" if is_sel else "paper-card"
                
                with st.container():
                    c_check, c_body = st.columns([0.08, 0.92])
                    with c_check:
                        new_checked = st.checkbox(
                            "Select",
                            value=is_sel,
                            key=f"check_p_{p['id']}",
                            label_visibility="collapsed"
                        )
                        if new_checked != is_sel:
                            set_paper_selected(st.session_state.active_project_id, p["id"], new_checked)
                            st.rerun()

                    with c_body:
                        badges_html = ""
                        rel_class = p.get("relevance_classification", "Relevant")
                        if rel_class == "Relevant":
                            badges_html += '<span class="badge badge-green">🎯 Relevant</span>'
                        elif rel_class == "Partially Relevant":
                            badges_html += '<span class="badge badge-amber">⚠️ Partially Relevant</span>'
                        elif rel_class == "Irrelevant":
                            badges_html += '<span class="badge badge-rose">❌ Irrelevant</span>'

                        if p.get("year"):
                            badges_html += f'<span class="badge badge-navy">{p["year"]}</span>'
                        source = p.get("source", "arXiv" if "arxiv" in p.get("id", "") else "Semantic Scholar")
                        badges_html += f'<span class="badge badge-blue">{source}</span>'
                        if p.get("pdf_url"):
                            badges_html += '<span class="badge badge-green">Open PDF Accessible</span>'
                        else:
                            badges_html += '<span class="badge badge-amber">Manual PDF Upload Supported</span>'
                        if p.get("doi"):
                            badges_html += f'<span class="badge badge-purple">DOI: {p["doi"]}</span>'

                        st.markdown(f"""
                        <div class="{card_class}">
                            <div class="paper-title">{p['title']}</div>
                            <div class="paper-authors">👤 {p['authors']}</div>
                            <div style="margin-bottom: 8px;">{badges_html}</div>
                            <div style="font-size: 12.5px; color: #1E293B; margin-top: 6px;">
                                <strong>Relevance Justification:</strong> {p.get('relevance_note', 'Matches topic criteria')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        with st.expander("📄 View Abstract & Metadata"):
                            st.write(p.get("abstract", "No abstract available."))
                            if p.get("url"):
                                st.markdown(f"**Publication URL:** [{p['url']}]({p['url']})")
                            if p.get("pdf_url"):
                                st.markdown(f"**Direct PDF Link:** [{p['pdf_url']}]({p['pdf_url']})")


# ==============================================================================
# PAGE 4: PAPER PROCESSING
# ==============================================================================
elif st.session_state.navigation_page == "Paper Processing":
    if not st.session_state.active_project_id:
        st.warning("Please select a project first.")
    else:
        selected_papers = get_selected_papers(st.session_state.active_project_id)
        if len(selected_papers) != 2:
            st.error("Please select exactly TWO papers on the 'Top Five Papers' page first.")
            if st.button("← Back to Paper Selection"):
                st.session_state.navigation_page = "Top Five Papers"
                st.rerun()
        else:
            paper_a, paper_b = selected_papers[0], selected_papers[1]
            st.markdown("### ⚙️ PDF Ingestion, PyMuPDF Extraction & FAISS Indexing")
            st.markdown("Extracts text page-by-page preserving provenance metadata, and constructs a FAISS CPU vector index.")

            col_a, col_b = st.columns(2)

            for col, paper, label in [(col_a, paper_a, "Paper A"), (col_b, paper_b, "Paper B")]:
                with col:
                    st.markdown(f"#### 📖 {label}: {paper['title'][:50]}...")
                    st.caption(f"Authors: {paper['authors'][:40]} • Year: {paper.get('year', 'N/A')}")

                    has_pdf = bool(paper.get("local_pdf_path") and os.path.exists(paper.get("local_pdf_path")))
                    m1, m2, m3 = st.columns(3)
                    m1.metric("PDF Status", "Downloaded" if has_pdf else "Pending")
                    m2.metric("Pages", paper.get("page_count", 0))
                    m3.metric("Chunks", paper.get("chunk_count", 0))

                    if not has_pdf:
                        if paper.get("pdf_url"):
                            if st.button(f"📥 Download PDF from Web ({label})", key=f"dl_{paper['id']}"):
                                with st.spinner(f"Downloading PDF for {label}..."):
                                    ok, res = download_paper_pdf(paper["pdf_url"], paper["id"])
                                    if ok:
                                        st.success("Download complete!")
                                        update_paper_pdf_info(paper["id"], res, 0, 0, False)
                                        st.rerun()
                                    else:
                                        st.error(f"Download failed: {res}. Please upload manually below.")

                        st.markdown("**Manual PDF Upload Fallback:**")
                        uploaded_file = st.file_uploader(
                            f"Upload PDF for {label}",
                            type=["pdf"],
                            key=f"upload_{paper['id']}"
                        )
                        if uploaded_file is not None:
                            local_path = save_uploaded_pdf(uploaded_file.read(), paper["id"], uploaded_file.name)
                            st.success(f"Uploaded and saved: {uploaded_file.name}")
                            update_paper_pdf_info(paper["id"], local_path, 0, 0, False)
                            st.rerun()
                    else:
                        st.success(f"PDF stored locally: `{Path(paper['local_pdf_path']).name}`")
                        re_up = st.file_uploader(f"Replace PDF ({label})", type=["pdf"], key=f"reup_{paper['id']}")
                        if re_up is not None:
                            local_path = save_uploaded_pdf(re_up.read(), paper["id"], re_up.name)
                            st.success(f"Replaced with: {re_up.name}")
                            update_paper_pdf_info(paper["id"], local_path, 0, 0, False)
                            st.rerun()

            st.markdown("---")

            all_pdfs_ready = bool(
                paper_a.get("local_pdf_path") and os.path.exists(paper_a.get("local_pdf_path")) and
                paper_b.get("local_pdf_path") and os.path.exists(paper_b.get("local_pdf_path"))
            )

            vs = FAISSVectorStore(st.session_state.active_project_id)
            is_indexed = vs.exists()

            c_idx1, c_idx2 = st.columns([2, 1])
            with c_idx1:
                if is_indexed:
                    st.success("🎯 FAISS Vector Index is active and ready for RAG & Multi-Agent reasoning!")
                elif not all_pdfs_ready:
                    st.info("Please ensure both PDFs are downloaded or uploaded above to begin indexing.")
                else:
                    st.info("Both PDFs are stored locally. Ready to extract pages and build FAISS index.")

            with c_idx2:
                btn_index = st.button(
                    "⚡ Extract & Build FAISS Index",
                    type="primary",
                    disabled=not all_pdfs_ready
                )

            if btn_index:
                with st.spinner("Extracting text via PyMuPDF and computing BGE embeddings..."):
                    progress_bar = st.progress(0.1, text="Parsing Paper A with PyMuPDF...")
                    
                    chunks_a, pages_a, err_a = extract_and_chunk_pdf(
                        paper_a["local_pdf_path"], paper_a["id"], paper_a["title"]
                    )
                    if err_a:
                        st.error(f"Paper A Error: {err_a}")
                        st.stop()

                    progress_bar.progress(0.3, text="Parsing Paper B with PyMuPDF...")
                    chunks_b, pages_b, err_b = extract_and_chunk_pdf(
                        paper_b["local_pdf_path"], paper_b["id"], paper_b["title"]
                    )
                    if err_b:
                        st.error(f"Paper B Error: {err_b}")
                        st.stop()

                    all_chunks = chunks_a + chunks_b
                    progress_bar.progress(0.6, text=f"Computing BGE Embeddings for {len(all_chunks)} chunks on CPU...")

                    if not all_chunks:
                        st.error("No extractable chunks found across the selected papers. Unable to build vector index.")
                        st.stop()

                    embedder = get_embedder()
                    texts = [c["content"] for c in all_chunks]
                    embeddings = embedder.embed_texts(texts)

                    if embeddings.shape[0] == 0:
                        st.error("Failed to generate embeddings for document chunks.")
                        st.stop()

                    progress_bar.progress(0.85, text="Building FAISS CPU vector index...")
                    save_ok = vs.build_and_save(all_chunks, embeddings)

                    if not save_ok or not vs.exists():
                        st.error("FAISS vector index creation failed. Index file was not persisted to disk.")
                        st.stop()

                    update_paper_pdf_info(paper_a["id"], paper_a["local_pdf_path"], pages_a, len(chunks_a), True)
                    update_paper_pdf_info(paper_b["id"], paper_b["local_pdf_path"], pages_b, len(chunks_b), True)

                    progress_bar.progress(1.0, text="Indexing complete!")
                    st.success(f"Successfully indexed {len(all_chunks)} chunks across {pages_a + pages_b} pages!")
                    time.sleep(1)
                    st.rerun()

            if is_indexed:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Proceed to RAG Research Chat →", type="primary"):
                    st.session_state.navigation_page = "RAG Research Chat"
                    st.rerun()


# ==============================================================================
# PAGE 5: RAG RESEARCH CHAT
# ==============================================================================
elif st.session_state.navigation_page == "RAG Research Chat":
    if not st.session_state.active_project_id:
        st.warning("Please select a project first.")
    else:
        selected_papers = get_selected_papers(st.session_state.active_project_id)
        if len(selected_papers) != 2:
            st.warning("Please ensure exactly 2 papers are selected and processed.")
        else:
            paper_a, paper_b = selected_papers[0], selected_papers[1]
            st.markdown("### 💬 Grounded RAG Research Assistant Chat")
            st.markdown(
                f"Inquire about **Paper A** (*{paper_a['title'][:40]}...*) and "
                f"**Paper B** (*{paper_b['title'][:40]}...*). Answers cite exact pages and sections."
            )

            # Paper Filter Control
            c_filter1, c_filter2 = st.columns([2, 1])
            with c_filter1:
                rag_paper_filter = st.selectbox(
                    "Target Retrieval Scope:",
                    options=["both", paper_a["id"], paper_b["id"]],
                    format_func=lambda x: "Both Papers (Balanced Dual-Paper RAG)" if x == "both" else (
                        f"Paper A: {paper_a['title'][:35]}..." if x == paper_a["id"] else f"Paper B: {paper_b['title'][:35]}..."
                    )
                )

            # Quick Inquiries
            st.caption("Quick Inquiries:")
            quick_queries = [
                "What methodology does Paper A use?",
                "What are the limitations of Paper B?",
                "Compare the datasets used by both papers.",
                "What research problem remains unresolved?"
            ]
            q_cols = st.columns(len(quick_queries))
            chosen_quick_query = None
            for i, q in enumerate(quick_queries):
                if q_cols[i].button(q, key=f"quick_q_{i}"):
                    chosen_quick_query = q

            # Display Chat History
            chat_container = st.container()
            with chat_container:
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        st.markdown(f'<div class="chat-bubble-user">👤 <strong>You:</strong><br>{msg["message"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="chat-bubble-assistant">🤖 <strong>Research Assistant:</strong><br>{msg["message"]}</div>', unsafe_allow_html=True)
                        if msg.get("citations"):
                            with st.expander("📚 Supporting Citations & Excerpts", expanded=False):
                                for cit in msg["citations"]:
                                    st.markdown(
                                        f"• **{cit.get('paper_title')}** (Page {cit.get('page_number')}, Section: *{cit.get('section')}*) "
                                        f"— *Score: {cit.get('score')}*"
                                    )
                                    st.caption(f"\"{cit.get('snippet')}\"")

            with st.form("chat_form", clear_on_submit=True):
                user_msg = st.text_input(
                    "Ask a grounded research question:",
                    value=chosen_quick_query or "",
                    placeholder="e.g. Compare the training setup and evaluation metrics between Paper A and Paper B."
                )
                submitted = st.form_submit_button("Send Query 🚀")

            if submitted and user_msg.strip():
                st.session_state.chat_history.append({"role": "user", "message": user_msg.strip(), "citations": []})
                save_chat_message(st.session_state.active_project_id, "user", user_msg.strip(), [])

                with st.spinner("Retrieving balanced FAISS evidence and formulating grounded answer..."):
                    rag = RAGService(st.session_state.active_project_id)
                    result = rag.answer_question(
                        user_msg.strip(),
                        paper_a_id=paper_a["id"],
                        paper_b_id=paper_b["id"],
                        paper_a_title=paper_a["title"],
                        paper_b_title=paper_b["title"],
                        paper_filter=rag_paper_filter
                    )

                    answer = result.get("answer", "No response generated.")
                    citations = result.get("citations", [])

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "message": answer,
                        "citations": citations
                    })
                    save_chat_message(st.session_state.active_project_id, "assistant", answer, citations)

                st.rerun()


# ==============================================================================
# PAGE 6: PAPER COMPARISON (Phase 3 & Priority 1 Enhanced)
# ==============================================================================
elif st.session_state.navigation_page == "Paper Comparison":
    if not st.session_state.active_project_id:
        st.warning("Please select a project first.")
    else:
        selected_papers = get_selected_papers(st.session_state.active_project_id)
        if len(selected_papers) != 2:
            st.error("Please select exactly 2 papers to compare.")
        else:
            paper_a, paper_b = selected_papers[0], selected_papers[1]
            st.markdown("### ⚖️ Side-by-Side Scientific Comparative Analysis")
            st.markdown(f"Contrasting **{paper_a['title']}** vs **{paper_b['title']}**")

            analysis_data = load_project_analysis_data(st.session_state.active_project_id)

            # Check if analysis has been run
            has_analysis = (
                analysis_data is not None and
                analysis_data.get("comparative_matrix") and
                bool(analysis_data.get("comparative_matrix", {}).get("table")) and
                "Analysis encountered an error" not in str(analysis_data.get("comparative_matrix"))
            )

            if not has_analysis:
                st.info("Comprehensive scientific comparison has not been executed yet for this project.")
                if st.button("🚀 Run LangGraph Multi-Agent Analysis Pipeline", type="primary"):
                    progress_bar = st.progress(0.0)
                    status_text = st.empty()

                    def update_progress(msg, pct):
                        status_text.info(msg)
                        progress_bar.progress(pct)

                    try:
                        state = execute_multi_agent_workflow(
                            st.session_state.active_project_id,
                            st.session_state.active_topic,
                            paper_a,
                            paper_b,
                            progress_callback=update_progress
                        )

                        # Step 5: Strict Output Validation
                        analysis_a = state.get("analysis_a", {})
                        analysis_b = state.get("analysis_b", {})
                        matrix = state.get("comparative_matrix", {})
                        gaps = state.get("gaps", [])
                        proposals = state.get("proposals", [])

                        if not analysis_a:
                            raise RuntimeError("Agent 1 Error: Paper A analysis is missing or empty.")
                        if not analysis_b:
                            raise RuntimeError("Agent 1 Error: Paper B analysis is missing or empty.")
                        if not matrix or not matrix.get("table"):
                            raise RuntimeError("Agent 1 Error: Comparative matrix table is empty.")
                        if not gaps or len(gaps) < 1:
                            raise RuntimeError("Agent 2 Error: Research gap discovery produced 0 gaps.")
                        if not proposals or len(proposals) < 1:
                            raise RuntimeError("Agent 3 Error: Proposal agent produced 0 proposals.")

                        # Ensure analyses are embedded
                        full_matrix = dict(matrix)
                        full_matrix["analysis_a"] = analysis_a
                        full_matrix["analysis_b"] = analysis_b

                        # Double persistence guarantee to SQLite
                        save_analysis_results(
                            st.session_state.active_project_id,
                            paper_a["id"],
                            paper_b["id"],
                            full_matrix,
                            gaps,
                            proposals
                        )
                        try:
                            update_project_status(st.session_state.active_project_id, "analyzed")
                        except Exception as st_err:
                            log_diagnostic("WARNING", f"Failed to update project status in DB: {st_err}")

                        # Cache into Streamlit session state
                        payload = {
                            "id": str(uuid.uuid4()),
                            "project_id": st.session_state.active_project_id,
                            "paper_a_id": paper_a["id"],
                            "paper_b_id": paper_b["id"],
                            "comparative_matrix": full_matrix,
                            "gaps": gaps,
                            "proposals": proposals,
                            "created_at": datetime.now().isoformat()
                        }
                        st.session_state[f"analysis_data_{st.session_state.active_project_id}"] = payload
                        st.session_state["cached_analysis_data"] = payload
                        st.session_state["cached_project_id"] = st.session_state.active_project_id

                        st.success("✅ Multi-agent analysis, gap discovery, and idea generation completed and persisted successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Multi-Agent Execution Error: {str(e)}")
                        with st.expander("View Diagnostic Traceback"):
                            if DIAGNOSTIC_LOG_PATH.exists():
                                with open(DIAGNOSTIC_LOG_PATH, "r", encoding="utf-8") as lf:
                                    st.code(lf.read()[-1200:], language="text")
            else:
                matrix = analysis_data["comparative_matrix"]
                analysis_a = matrix.get("analysis_a", {})
                analysis_b = matrix.get("analysis_b", {})

                # Scope Disparity Warning Banner
                if matrix.get("are_problems_related") is False or matrix.get("scope_disparity_warning"):
                    compat = matrix.get("problem_compatibility_score", 0.5)
                    st.warning(
                        f"⚠️ **Scope Disparity Warning (Domain Compatibility: {compat*100:.0f}%):** "
                        f"{matrix.get('scope_disparity_warning', 'These two papers investigate significantly divergent problem domains or modalities.')}"
                    )

                comp_tabs = st.tabs([
                    "📊 Comparative Matrix",
                    f"📖 Paper A ({paper_a['title'][:25]}...)",
                    f"📖 Paper B ({paper_b['title'][:25]}...)",
                    "⚖️ Methodological Synthesis & Tradeoffs"
                ])

                with comp_tabs[0]:
                    table_rows = matrix.get("table", [])
                    if table_rows:
                        formatted_rows = []
                        for r in table_rows:
                            analysis_parts = []
                            if r.get("comparative_interpretation"):
                                analysis_parts.append(f"Interpretation: {r.get('comparative_interpretation')}")
                            if r.get("similarities") and r.get("similarities") != "None reported":
                                analysis_parts.append(f"Similarities: {r.get('similarities')}")
                            if r.get("differences") and r.get("differences") != "None reported":
                                analysis_parts.append(f"Differences: {r.get('differences')}")
                            if r.get("supporting_evidence"):
                                analysis_parts.append(f"Evidence: {r.get('supporting_evidence')}")
                            comp_analysis = " \n\n• ".join(analysis_parts) if analysis_parts else (r.get("comparative_interpretation") or "Comparative evaluation")

                            formatted_rows.append({
                                "Dimension": r.get("dimension", ""),
                                "Paper A": r.get("paper_a_findings", r.get("paper_a_evidence", "Not reported in the paper")),
                                "Paper B": r.get("paper_b_findings", r.get("paper_b_evidence", "Not reported in the paper")),
                                "Comparative Analysis": comp_analysis,
                                "Page References": r.get("exact_page_references", r.get("source_page_references", "N/A"))
                            })
                        df = pd.DataFrame(formatted_rows)
                        st.dataframe(df, use_container_width=True, height=480)

                        # Individual Dimension Evidence Expanders
                        st.markdown("#### 🔍 Granular Dimension Evidence & Source Excerpts")
                        for idx, r in enumerate(table_rows, 1):
                            with st.expander(f"Dimension #{idx}: {r.get('dimension', 'Dimension')}"):
                                c_d1, c_d2 = st.columns(2)
                                with c_d1:
                                    st.markdown(f"**Paper A Evidence:**")
                                    st.write(r.get("paper_a_findings", r.get("paper_a_evidence", "Not reported")))
                                with c_d2:
                                    st.markdown(f"**Paper B Evidence:**")
                                    st.write(r.get("paper_b_findings", r.get("paper_b_evidence", "Not reported")))
                                st.info(f"**Comparative Interpretation:** {r.get('comparative_interpretation', 'N/A')}")
                                if r.get("supporting_evidence"):
                                    st.caption(f"Supporting Text: \"{r.get('supporting_evidence')}\"")
                    else:
                        st.info("No comparative table entries generated.")

                # Independent Paper A Analysis Tab (All 15 Fields)
                with comp_tabs[1]:
                    st.markdown(f"#### 📄 Comprehensive 15-Point Extraction: *{paper_a['title']}*")
                    if analysis_a:
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("**1. Research Objective:**")
                            st.write(analysis_a.get("research_objective", "Not reported in the paper"))
                            st.markdown("**2. Problem Statement:**")
                            st.write(analysis_a.get("problem_statement", analysis_a.get("research_problem", "Not reported in the paper")))
                            st.markdown("**3. Research Questions:**")
                            st.write(analysis_a.get("research_questions", "Not reported in the paper"))
                            st.markdown("**4. Proposed Methodology:**")
                            st.write(analysis_a.get("proposed_methodology", analysis_a.get("methodology", "Not reported in the paper")))
                            st.markdown("**5. Model Architecture:**")
                            st.write(analysis_a.get("model_architecture", "Not reported in the paper"))
                            st.markdown("**6. Algorithms:**")
                            st.write(analysis_a.get("algorithms", "Not reported in the paper"))
                            st.markdown("**7. Datasets:**")
                            st.write(analysis_a.get("dataset_names", "Not reported in the paper"))
                            st.markdown("**8. Dataset Sizes:**")
                            st.write(analysis_a.get("dataset_sizes", "Not reported in the paper"))

                        with c2:
                            st.markdown("**9. Experimental Setup & Hardware:**")
                            st.write(analysis_a.get("experimental_setup", analysis_a.get("training_testing_setup", "Not reported in the paper")))
                            st.markdown("**10. Evaluation Metrics:**")
                            st.write(analysis_a.get("evaluation_metrics", "Not reported in the paper"))
                            st.markdown("**11. Actual Experimental Results:**")
                            st.write(analysis_a.get("actual_experimental_results", analysis_a.get("experimental_results", "Not reported in the paper")))
                            st.markdown("**12. Baseline Methods:**")
                            st.write(analysis_a.get("baseline_methods", "Not reported in the paper"))
                            st.markdown("**13. Strengths:**")
                            st.write(analysis_a.get("strengths", ["Not reported in the paper"]))
                            st.markdown("**14. Explicit Limitations:**")
                            st.write(analysis_a.get("explicit_limitations", ["Not reported in the paper"]))
                            st.markdown("**15. Future Research Directions:**")
                            st.write(analysis_a.get("future_research_directions", ["Not reported in the paper"]))

                # Independent Paper B Analysis Tab (All 15 Fields)
                with comp_tabs[2]:
                    st.markdown(f"#### 📄 Comprehensive 15-Point Extraction: *{paper_b['title']}*")
                    if analysis_b:
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("**1. Research Objective:**")
                            st.write(analysis_b.get("research_objective", "Not reported in the paper"))
                            st.markdown("**2. Problem Statement:**")
                            st.write(analysis_b.get("problem_statement", analysis_b.get("research_problem", "Not reported in the paper")))
                            st.markdown("**3. Research Questions:**")
                            st.write(analysis_b.get("research_questions", "Not reported in the paper"))
                            st.markdown("**4. Proposed Methodology:**")
                            st.write(analysis_b.get("proposed_methodology", analysis_b.get("methodology", "Not reported in the paper")))
                            st.markdown("**5. Model Architecture:**")
                            st.write(analysis_b.get("model_architecture", "Not reported in the paper"))
                            st.markdown("**6. Algorithms:**")
                            st.write(analysis_b.get("algorithms", "Not reported in the paper"))
                            st.markdown("**7. Datasets:**")
                            st.write(analysis_b.get("dataset_names", "Not reported in the paper"))
                            st.markdown("**8. Dataset Sizes:**")
                            st.write(analysis_b.get("dataset_sizes", "Not reported in the paper"))

                        with c2:
                            st.markdown("**9. Experimental Setup & Hardware:**")
                            st.write(analysis_b.get("experimental_setup", analysis_b.get("training_testing_setup", "Not reported in the paper")))
                            st.markdown("**10. Evaluation Metrics:**")
                            st.write(analysis_b.get("evaluation_metrics", "Not reported in the paper"))
                            st.markdown("**11. Actual Experimental Results:**")
                            st.write(analysis_b.get("actual_experimental_results", analysis_b.get("experimental_results", "Not reported in the paper")))
                            st.markdown("**12. Baseline Methods:**")
                            st.write(analysis_b.get("baseline_methods", "Not reported in the paper"))
                            st.markdown("**13. Strengths:**")
                            st.write(analysis_b.get("strengths", ["Not reported in the paper"]))
                            st.markdown("**14. Explicit Limitations:**")
                            st.write(analysis_b.get("explicit_limitations", ["Not reported in the paper"]))
                            st.markdown("**15. Future Research Directions:**")
                            st.write(analysis_b.get("future_research_directions", ["Not reported in the paper"]))

                # Synthesis & Tradeoffs Tab
                with comp_tabs[3]:
                    st.markdown("#### 🏆 Methodological Strengths & Operating Conditions")
                    st.info(matrix.get("stronger_methodology_and_conditions", "Evaluation of methodology strengths."))

                    st.markdown("#### ⚖️ Architectural & Performance Trade-offs")
                    st.warning(matrix.get("methodological_tradeoffs", matrix.get("winner_or_tradeoff_verdict", "Tradeoff analysis established.")))

                    st.markdown("#### ⚡ Computational Efficiency Comparison")
                    st.write(matrix.get("computational_efficiency_comparison", "Not reported in the paper"))

                    st.markdown("#### 🌌 Unexplored Research Frontiers")
                    st.write(matrix.get("unexplored_frontiers", "Unaddressed intersections between both paradigms."))

                    st.markdown("#### 📋 Executive Comparative Summary")
                    st.write(matrix.get("comparative_summary", "Comparative summary generated."))

                st.markdown("<br>", unsafe_allow_html=True)
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Re-run Multi-Agent Analysis Pipeline"):
                        progress_bar = st.progress(0.0)
                        status_text = st.empty()

                        def update_progress_rerun(msg, pct):
                            status_text.info(msg)
                            progress_bar.progress(pct)

                        try:
                            state = execute_multi_agent_workflow(
                                st.session_state.active_project_id,
                                st.session_state.active_topic,
                                paper_a,
                                paper_b,
                                progress_callback=update_progress_rerun
                            )

                            analysis_a = state.get("analysis_a", {})
                            analysis_b = state.get("analysis_b", {})
                            matrix = state.get("comparative_matrix", {})
                            gaps = state.get("gaps", [])
                            proposals = state.get("proposals", [])

                            if not analysis_a:
                                raise RuntimeError("Validation Error: Paper A analysis is missing.")
                            if not analysis_b:
                                raise RuntimeError("Validation Error: Paper B analysis is missing.")
                            if not matrix or not matrix.get("table"):
                                raise RuntimeError("Validation Error: Comparative matrix table is empty.")
                            if not gaps:
                                raise RuntimeError("Validation Error: Gaps list is empty.")
                            if not proposals:
                                raise RuntimeError("Validation Error: Proposals list is empty.")

                            full_matrix = dict(matrix)
                            full_matrix["analysis_a"] = analysis_a
                            full_matrix["analysis_b"] = analysis_b

                            save_analysis_results(
                                st.session_state.active_project_id,
                                paper_a["id"],
                                paper_b["id"],
                                full_matrix,
                                gaps,
                                proposals
                            )
                            try:
                                update_project_status(st.session_state.active_project_id, "analyzed")
                            except Exception as st_err:
                                log_diagnostic("WARNING", f"Failed to update project status in DB: {st_err}")

                            payload = {
                                "id": str(uuid.uuid4()),
                                "project_id": st.session_state.active_project_id,
                                "paper_a_id": paper_a["id"],
                                "paper_b_id": paper_b["id"],
                                "comparative_matrix": full_matrix,
                                "gaps": gaps,
                                "proposals": proposals,
                                "created_at": datetime.now().isoformat()
                            }
                            st.session_state[f"analysis_data_{st.session_state.active_project_id}"] = payload
                            st.session_state["cached_analysis_data"] = payload
                            st.session_state["cached_project_id"] = st.session_state.active_project_id

                            st.success("✅ Re-analysis complete and verified!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Re-analysis failed: {str(e)}")
                with col_btn2:
                    if st.button("Proceed to Research Gap Discovery →", type="primary"):
                        st.session_state.navigation_page = "Research Gap Discovery"
                        st.rerun()


# ==============================================================================
# PAGE 7: RESEARCH GAP DISCOVERY (Phase 4 & Priority 2 Enhanced)
# ==============================================================================
elif st.session_state.navigation_page == "Research Gap Discovery":
    if not st.session_state.active_project_id:
        st.warning("Please select a project first.")
    else:
        analysis_data = load_project_analysis_data(st.session_state.active_project_id)
        if not analysis_data or not analysis_data.get("gaps"):
            st.info("Research gaps have not been generated yet. Please run the analysis first.")
            if st.button("Go to Paper Comparison to Run Analysis"):
                st.session_state.navigation_page = "Paper Comparison"
                st.rerun()
        else:
            gaps = analysis_data["gaps"]
            st.markdown(f"### 🔍 Discovered Research Gaps ({len(gaps)} Evaluated)")
            st.markdown(
                "Rigorous gap analysis systematically covering **7 mandatory academic dimensions** under the **Critical Evidence Rule**. "
                "Gaps lacking dual-paper verification are marked **UNVERIFIED**."
            )

            # Filter by Category
            categories = list(set(g.get("category", "General") for g in gaps))
            selected_cat = st.multiselect("Filter by Gap Category:", options=categories, default=categories)

            # Scope Disclaimer
            st.caption(
                "ℹ️ *Note on Research Novelty: These research gaps reflect the comparative boundary between the two analyzed manuscripts "
                "and supplementary indexes; they do not assert exhaustive global novelty without wider meta-analysis.*"
            )

            for i, gap in enumerate(gaps, 1):
                if gap.get("category", "General") not in selected_cat:
                    continue

                is_verified = (gap.get("verification_status") == "VERIFIED")
                card_class = "gap-card" if is_verified else "gap-card gap-card-unverified"

                verif_badge = (
                    '<span class="badge badge-green">VERIFIED</span>'
                    if is_verified else
                    '<span class="badge badge-red">UNVERIFIED</span>'
                )

                classif = gap.get("classification", "Gap inferred from comparison")
                if "author" in classif.lower() or "explicit" in classif.lower():
                    classif_badge = '<span class="badge badge-purple">Explicit Author-Stated Gap</span>'
                elif "supplementary" in classif.lower() or "literature" in classif.lower():
                    classif_badge = '<span class="badge badge-navy">Supported by Supplementary Literature</span>'
                elif "inferred" in classif.lower():
                    classif_badge = '<span class="badge badge-blue">Inferred Comparative Gap</span>'
                else:
                    classif_badge = '<span class="badge badge-amber">Unverified Candidate Gap</span>'

                conf_lvl = gap.get("confidence_level", "Medium")
                conf_score = float(gap.get("confidence_score", 0.5))
                conf_badge = f'<span class="badge badge-navy">Confidence: {conf_lvl} ({conf_score*100:.0f}%)</span>'

                missing_alert = ""
                if not is_verified:
                    missing_text = html.escape(str(gap.get("missing_evidence_explanation") or gap.get("verification_note") or "Insufficient direct textual evidence."))
                    missing_alert = (
                        f'<div style="background-color: #FEF2F2; border-left: 3px solid #EF4444; padding: 8px 12px; margin: 8px 0; font-size: 13px; color: #991B1B;">'
                        f'<strong>⚠️ Missing Evidence Alert:</strong> {missing_text}'
                        f'</div>'
                    )

                cat_escaped = html.escape(str(gap.get("category", "General")))
                title_escaped = html.escape(str(gap.get("gap_title", "Untitled Gap")))
                desc_escaped = html.escape(str(gap.get("gap_explanation") or gap.get("description") or ""))
                ev_a_escaped = html.escape(str(gap.get("evidence_paper_a") or "No direct evidence reported in Paper A"))
                ev_b_escaped = html.escape(str(gap.get("evidence_paper_b") or "No direct evidence reported in Paper B"))
                pg_a_escaped = html.escape(str(gap.get("exact_page_numbers") or gap.get("exact_page_refs_a") or "N/A"))
                pg_b_escaped = html.escape(str(gap.get("exact_page_numbers") or gap.get("exact_page_refs_b") or "N/A"))
                why_escaped = html.escape(str(gap.get("why_it_matters") or "N/A"))
                rq_escaped = html.escape(str(gap.get("proposed_research_question") or "N/A"))
                sol_escaped = html.escape(str(gap.get("possible_solution") or "N/A"))
                just_escaped = html.escape(str(gap.get("confidence_justification") or gap.get("confidence_explanation") or "N/A"))

                gap_card_html = (
                    f'<div class="{card_class}">'
                    f'<div style="float: right;">{verif_badge} {classif_badge} {conf_badge}</div>'
                    f'<div class="gap-title">#{i} [{cat_escaped}] {title_escaped}</div>'
                    f'<p style="font-size: 14px; color: #1F2937; margin-top: 6px; line-height: 1.5;">{desc_escaped}</p>'
                    f'{missing_alert}'
                    f'<div class="gap-evidence">'
                    f'<strong>Evidence Paper A:</strong> {ev_a_escaped}<br>'
                    f'<small><em>Exact Page / Section: {pg_a_escaped}</em></small>'
                    f'</div>'
                    f'<div class="gap-evidence">'
                    f'<strong>Evidence Paper B:</strong> {ev_b_escaped}<br>'
                    f'<small><em>Exact Page / Section: {pg_b_escaped}</em></small>'
                    f'</div>'
                    f'<div style="font-size: 13px; color: #0F172A; margin-top: 8px;"><strong>🎯 Why this gap matters:</strong> {why_escaped}</div>'
                    f'<div style="font-size: 13px; color: #1D4ED8; margin-top: 4px;"><strong>❓ Proposed Research Question:</strong> {rq_escaped}</div>'
                    f'<div style="font-size: 13px; color: #059669; margin-top: 4px;"><strong>💡 Proposed Solution Strategy:</strong> {sol_escaped}</div>'
                    f'<div style="font-size: 12px; color: #64748B; margin-top: 4px;"><em>Confidence Justification: {just_escaped}</em></div>'
                    f'</div>'
                )
                st.markdown(gap_card_html, unsafe_allow_html=True)

                # Supplementary literature verification expander
                lit_ver = gap.get("literature_verification")
                if lit_ver:
                    with st.expander(f"🔎 Supplementary Literature Verification Check for Gap #{i}"):
                        st.caption(f"Search Query Dispatched to Semantic Scholar & arXiv: *{lit_ver.get('searched_query')}*")
                        addressed_status = "Precedent found in external literature" if lit_ver.get("addressed_in_literature") else "Novel / Unresolved in external literature"
                        st.write(f"**Verification Outcome:** {addressed_status}")
                        st.write(lit_ver.get("synthesis", ""))
                        if lit_ver.get("related_papers"):
                            st.markdown("**Related External Works Discovered:**")
                            for rp in lit_ver["related_papers"]:
                                st.markdown(f"- **{rp['title']}** ({rp.get('year', 'N/A')}) by {rp.get('authors', 'Unknown')} — [Link]({rp.get('url')})")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Proceed to Research Idea Generation →", type="primary"):
                st.session_state.navigation_page = "Research Idea Generation"
                st.rerun()


# ==============================================================================
# PAGE 8: RESEARCH IDEA GENERATION (Phase 5 & Priority 3 Enhanced)
# ==============================================================================
elif st.session_state.navigation_page == "Research Idea Generation":
    if not st.session_state.active_project_id:
        st.warning("Please select a project first.")
    else:
        analysis_data = load_project_analysis_data(st.session_state.active_project_id)
        if not analysis_data or not analysis_data.get("proposals"):
            st.info("Research ideas have not been generated yet. Please run the multi-agent pipeline first.")
            if st.button("Go to Paper Comparison"):
                st.session_state.navigation_page = "Paper Comparison"
                st.rerun()
        else:
            proposals = analysis_data["proposals"]
            st.markdown('<h3 style="color: #172554; font-weight: 700; margin-bottom: 6px;">💡 AI-Driven Research Ideas and Future Research Directions</h3>', unsafe_allow_html=True)
            st.markdown(
                '<p style="color: #1F2937; font-size: 14px; margin-bottom: 16px;">'
                'Three prioritized, publication-grade research proposals formulated to resolve the identified research gaps. '
                'Each proposal includes all <strong>18 academic components</strong> and a multi-criteria feasibility ranking.'
                '</p>',
                unsafe_allow_html=True
            )

            tab_titles = [f"Rank #{p.get('rank', i+1)}: {p.get('research_title', p.get('proposed_title', ''))[:35]}..." for i, p in enumerate(proposals)]
            tabs = st.tabs(tab_titles)

            for idx, tab in enumerate(tabs):
                if idx < len(proposals):
                    prop = proposals[idx]
                    with tab:
                        proposal_full_html = render_proposal_full_card(idx, prop)
                        st.markdown(proposal_full_html, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Proceed to Generate Downloadable Report →", type="primary"):
                st.session_state.navigation_page = "Report Generation"
                st.rerun()


# ==============================================================================
# PAGE 9: REPORT GENERATION
# ==============================================================================
elif st.session_state.navigation_page == "Report Generation":
    if not st.session_state.active_project_id:
        st.warning("Please select a project first.")
    else:
        selected_papers = get_selected_papers(st.session_state.active_project_id)
        analysis_data = load_project_analysis_data(st.session_state.active_project_id)

        if len(selected_papers) != 2 or not analysis_data:
            st.error("Incomplete project state. Please ensure 2 papers are selected and analyzed.")
        else:
            paper_a, paper_b = selected_papers[0], selected_papers[1]
            st.markdown("### 📑 Generate & Download Final Research Report")
            st.markdown("Produces an academic Word document (`.docx`) with literature review, comparative tables, verified gaps, and research proposals.")

            report_filename = f"Research_Report_{st.session_state.active_project_id[:8]}.docx"
            
            c_doc1, c_doc2 = st.columns([2, 1])
            with c_doc1:
                st.markdown(f"""
                **Report Contents Included:**
                - Executive Summary & Scope (`{st.session_state.active_topic}`)
                - Baseline Literature Review (`{paper_a['title'][:30]}...` & `{paper_b['title'][:30]}...`)
                - Side-by-Side Comparative Analysis Table
                - {len(analysis_data.get('gaps', []))} Categorized & Evidence-Grounded Research Gaps
                - 3 Feasible Final-Year Engineering Research Proposals
                - Formal Bibliographic References with DOIs
                """)

            with c_doc2:
                if st.button("📄 Build Document (.docx)", type="primary"):
                    with st.spinner("Generating styled academic Word report..."):
                        matrix_data = analysis_data.get("comparative_matrix", {})
                        doc_path = generate_research_docx_report(
                            project_title=f"Autonomous RAG Research Report: {st.session_state.active_topic}",
                            topic=st.session_state.active_topic,
                            paper_a=paper_a,
                            paper_b=paper_b,
                            analysis_a=matrix_data.get("analysis_a", {}),
                            analysis_b=matrix_data.get("analysis_b", {}),
                            comparative_matrix=matrix_data,
                            gaps=analysis_data.get("gaps", []),
                            proposals=analysis_data.get("proposals", []),
                            output_filename=report_filename
                        )
                        st.session_state["generated_doc_path"] = doc_path
                        st.success("Document built successfully!")

                if "generated_doc_path" in st.session_state and os.path.exists(st.session_state["generated_doc_path"]):
                    with open(st.session_state["generated_doc_path"], "rb") as f:
                        file_bytes = f.read()

                    st.download_button(
                        label="⬇️ Download Word Report (.docx)",
                        data=file_bytes,
                        file_name=report_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary"
                    )

            st.markdown("---")
            st.markdown("#### 📖 Live Document Preview")
            with st.expander("Preview Executive Summary & Scope", expanded=True):
                st.write(
                    f"This research investigation examines **{st.session_state.active_topic}** "
                    f"through the empirical lens of two selected scientific publications: "
                    f"**{paper_a['title']}** and **{paper_b['title']}**. "
                    f"Through vector-grounded FAISS retrieval and LangGraph multi-agent discovery, "
                    f"we identified critical research gaps and developed three prioritized capstone trajectories."
                )

            with st.expander("Preview Bibliography & DOIs", expanded=True):
                st.markdown(f"1. **{paper_a['authors']}** ({paper_a.get('year', 'N/A')}). *{paper_a['title']}*. DOI: `{paper_a.get('doi', 'N/A')}`")
                st.markdown(f"2. **{paper_b['authors']}** ({paper_b.get('year', 'N/A')}). *{paper_b['title']}*. DOI: `{paper_b.get('doi', 'N/A')}`")
