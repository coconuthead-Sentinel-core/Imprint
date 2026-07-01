"""Tests for the SRS renderer — generates a real .docx and reads it back.

Run from the project root:  py -3 -m unittest discover -s tests
"""

import os
import tempfile
import unittest

from docx import Document

from imprint import db, srs


class TestSrsRender(unittest.TestCase):
    def setUp(self):
        fd, self.dbpath = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = db.connect(self.dbpath)
        db.init_schema(self.conn)
        self.pid = db.create_project(self.conn, "Imprint", "waterfall", "A local paperwork tool.")
        db.add_requirement(self.conn, self.pid, "Functional",
                           "The system shall store each requirement as a structured record.",
                           moscow="Must", acceptance_criteria="A saved requirement reloads intact.")
        db.add_requirement(self.conn, self.pid, "Non-Functional",
                           "The system shall run fully offline.", moscow="Must")
        self.out = tempfile.mktemp(suffix=".docx")

    def tearDown(self):
        self.conn.close()
        os.unlink(self.dbpath)
        if os.path.exists(self.out):
            os.unlink(self.out)

    def test_generates_a_file(self):
        project = db.get_project(self.conn, self.pid)
        reqs = db.list_requirements(self.conn, self.pid)
        path = srs.build_srs(project, reqs, self.out)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)

    def test_document_contains_expected_content(self):
        project = db.get_project(self.conn, self.pid)
        reqs = db.list_requirements(self.conn, self.pid)
        srs.build_srs(project, reqs, self.out)

        text = "\n".join(p.text for p in Document(self.out).paragraphs)
        self.assertIn("Imprint", text)
        self.assertIn("Software Requirements Specification", text)
        self.assertIn("REQ-0001", text)
        self.assertIn("store each requirement", text)
        self.assertIn("Functional Requirements", text)

    def test_empty_project_still_renders(self):
        empty = db.create_project(self.conn, "Empty", "agile")
        project = db.get_project(self.conn, empty)
        path = srs.build_srs(project, [], self.out)
        self.assertTrue(os.path.exists(path))

    def test_default_output_path_is_sanitized(self):
        p = srs.default_output_path("My Project: v2!")
        self.assertTrue(p.endswith(".docx"))
        self.assertNotIn(":", os.path.basename(p))
        self.assertNotIn("!", os.path.basename(p))


if __name__ == "__main__":
    unittest.main()
