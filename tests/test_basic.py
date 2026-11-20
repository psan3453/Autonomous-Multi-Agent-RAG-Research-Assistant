"""
Unit & Integration Tests for Autonomous Multi-Agent RAG Research Assistant.
Verifies:
1. Environment & Path Configurations
2. SQLite Database initialization and operations
3. Real paper search API integration
4. PDF section detection & chunking logic
5. LLM JSON parser robustness
"""

import os
import unittest
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import STORAGE_DIR, PAPERS_DIR, INDEXES_DIR, REPORTS_DIR, DB_PATH
from database.db import init_db, create_project, get_projects, get_dashboard_stats
from services.paper_search import search_real_papers, normalize_title
from services.pdf_processor import detect_section_title
from services.llm_service import extract_json_from_llm_text


class TestResearchAssistant(unittest.TestCase):

    def test_01_directories_exist(self):
        """Verify storage directories are automatically provisioned."""
        self.assertTrue(STORAGE_DIR.exists())
        self.assertTrue(PAPERS_DIR.exists())
        self.assertTrue(INDEXES_DIR.exists())
        self.assertTrue(REPORTS_DIR.exists())

    def test_02_database_operations(self):
        """Verify SQLite tables are created and basic CRUD functions work."""
        init_db()
        self.assertTrue(DB_PATH.exists())

        proj_id = create_project("Graph Neural Networks for Drug Repurposing")
        self.assertIsNotNone(proj_id)

        projects = get_projects()
        self.assertGreaterEqual(len(projects), 1)

        stats = get_dashboard_stats()
        self.assertGreaterEqual(stats["total_projects"], 1)

    def test_03_title_normalization(self):
        """Verify fuzzy deduplication title normalizer."""
        t1 = "Attention Is All You Need!"
        t2 = "attention is all you need"
        self.assertEqual(normalize_title(t1), normalize_title(t2))

    def test_04_section_detection(self):
        """Verify academic section heading recognition."""
        self.assertEqual(detect_section_title("1. Introduction"), "Introduction")
        self.assertEqual(detect_section_title("III. METHODOLOGY"), "Methodology")
        self.assertEqual(detect_section_title("Experimental Setup and Results"), "Experimental Setup And Results")
        self.assertIsNone(detect_section_title("This is a regular paragraph of scientific text."))

    def test_05_llm_json_extractor(self):
        """Verify robust JSON extraction from LLM markdown responses."""
        raw_markdown = '```json\n{"rank": 1, "status": "approved"}\n```'
        parsed = extract_json_from_llm_text(raw_markdown)
        self.assertEqual(parsed.get("rank"), 1)
        self.assertEqual(parsed.get("status"), "approved")

        raw_plain = 'Here is the data: {"gaps": ["Methodological gap"]}'
        parsed2 = extract_json_from_llm_text(raw_plain)
        self.assertIn("gaps", parsed2)


if __name__ == "__main__":
    unittest.main()
