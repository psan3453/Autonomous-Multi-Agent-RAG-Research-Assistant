"""
SQLite Database module for metadata persistence:
- Research projects
- Discovered and selected papers
- Extracted chunks & indexing status
- Analysis results (Comparative matrix, gaps, proposals)
- Grounded RAG chat logs
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        topic TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        summary TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS papers (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        title TEXT NOT NULL,
        authors TEXT,
        abstract TEXT,
        year INTEGER,
        doi TEXT,
        arxiv_id TEXT,
        url TEXT,
        pdf_url TEXT,
        local_pdf_path TEXT,
        is_selected INTEGER DEFAULT 0,
        page_count INTEGER DEFAULT 0,
        chunk_count INTEGER DEFAULT 0,
        is_indexed INTEGER DEFAULT 0,
        relevance_note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analysis_results (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        paper_a_id TEXT NOT NULL,
        paper_b_id TEXT NOT NULL,
        comparative_matrix_json TEXT,
        gaps_json TEXT,
        proposals_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        citations_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """)

    conn.commit()
    conn.close()


def create_project(topic: str, name: Optional[str] = None) -> str:
    """Create a new research project and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    project_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    project_name = name or f"Research on: {topic[:50]}"

    cursor.execute(
        "INSERT INTO projects (id, name, topic, created_at, status) VALUES (?, ?, ?, ?, ?)",
        (project_id, project_name, topic, created_at, "created")
    )
    conn.commit()
    conn.close()
    return project_id


def get_projects() -> List[Dict[str, Any]]:
    """Retrieve all projects sorted by creation date descending."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Get a project by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_project_status(project_id: str, status: str, summary: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    if summary:
        cursor.execute("UPDATE projects SET status = ?, summary = ? WHERE id = ?", (status, summary, project_id))
    else:
        cursor.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
    conn.commit()
    conn.close()


def save_papers(project_id: str, papers: List[Dict[str, Any]]):
    """Save discovered papers for a project."""
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()

    for p in papers:
        raw_id = p.get("id") or str(uuid.uuid4())
        # Ensure paper ID is scoped to project to prevent cross-project collision and primary key overwrite
        if not str(raw_id).startswith(f"{project_id}_"):
            paper_id = f"{project_id}_{raw_id}"
        else:
            paper_id = str(raw_id)
        p["id"] = paper_id  # sync in-memory dict so callers and session state match

        cursor.execute("""
        INSERT OR REPLACE INTO papers 
        (id, project_id, title, authors, abstract, year, doi, arxiv_id, url, pdf_url, local_pdf_path, is_selected, relevance_note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper_id,
            project_id,
            p.get("title", "Untitled"),
            p.get("authors", ""),
            p.get("abstract", ""),
            p.get("year", None),
            p.get("doi", ""),
            p.get("arxiv_id", ""),
            p.get("url", ""),
            p.get("pdf_url", ""),
            p.get("local_pdf_path", ""),
            1 if p.get("is_selected") else 0,
            p.get("relevance_note", ""),
            created_at
        ))
    conn.commit()
    conn.close()


def get_papers(project_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM papers WHERE project_id = ? ORDER BY is_selected DESC, year DESC", (project_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def set_paper_selected(project_id: str, paper_id: str, selected: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE papers SET is_selected = ? WHERE id = ? AND project_id = ?", (1 if selected else 0, paper_id, project_id))
    conn.commit()
    conn.close()


def get_selected_papers(project_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM papers WHERE project_id = ? AND is_selected = 1", (project_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def update_paper_pdf_info(paper_id: str, local_pdf_path: str, page_count: int, chunk_count: int, is_indexed: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE papers 
    SET local_pdf_path = ?, page_count = ?, chunk_count = ?, is_indexed = ?
    WHERE id = ?
    """, (local_pdf_path, page_count, chunk_count, 1 if is_indexed else 0, paper_id))
    conn.commit()
    conn.close()


def save_analysis_results(project_id: str, paper_a_id: str, paper_b_id: str, matrix: Dict, gaps: List, proposals: List):
    conn = get_connection()
    cursor = conn.cursor()
    result_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()

    # Clear previous results for this pair if any
    cursor.execute("DELETE FROM analysis_results WHERE project_id = ?", (project_id,))

    cursor.execute("""
    INSERT INTO analysis_results (id, project_id, paper_a_id, paper_b_id, comparative_matrix_json, gaps_json, proposals_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result_id,
        project_id,
        paper_a_id,
        paper_b_id,
        json.dumps(matrix),
        json.dumps(gaps),
        json.dumps(proposals),
        created_at
    ))
    conn.commit()
    conn.close()


def get_analysis_results(project_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM analysis_results WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    return {
        "id": d["id"],
        "project_id": d["project_id"],
        "paper_a_id": d["paper_a_id"],
        "paper_b_id": d["paper_b_id"],
        "comparative_matrix": json.loads(d["comparative_matrix_json"]) if d["comparative_matrix_json"] else {},
        "gaps": json.loads(d["gaps_json"]) if d["gaps_json"] else [],
        "proposals": json.loads(d["proposals_json"]) if d["proposals_json"] else [],
        "created_at": d["created_at"]
    }


def save_chat_message(project_id: str, role: str, message: str, citations: Optional[List[Dict]] = None):
    conn = get_connection()
    cursor = conn.cursor()
    msg_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    cit_json = json.dumps(citations or [])

    cursor.execute("""
    INSERT INTO chat_history (id, project_id, role, message, citations_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (msg_id, project_id, role, message, cit_json, created_at))
    conn.commit()
    conn.close()


def get_chat_history(project_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_history WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["citations"] = json.loads(d["citations_json"]) if d["citations_json"] else []
        rows.append(d)
    conn.close()
    return rows


def get_dashboard_stats() -> Dict[str, int]:
    """Retrieve aggregate statistics for the home dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM projects")
    total_projects = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM papers")
    total_papers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM papers WHERE is_indexed = 1")
    processed_papers = cursor.fetchone()[0]

    cursor.execute("SELECT gaps_json FROM analysis_results")
    total_gaps = 0
    for row in cursor.fetchall():
        if row[0]:
            try:
                gaps = json.loads(row[0])
                total_gaps += len(gaps)
            except Exception:
                pass

    conn.close()
    return {
        "total_projects": total_projects,
        "total_papers": total_papers,
        "processed_papers": processed_papers,
        "total_gaps": total_gaps
    }
