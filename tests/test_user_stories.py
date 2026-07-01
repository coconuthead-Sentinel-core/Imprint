"""Tests for the Agile user-story renderer — pure transform + real .docx.

Run from the project root:  py -3 -m unittest discover -s tests
"""

import os
import tempfile
import unittest

from docx import Document

from imprint import db, user_stories


class TestToUserStory(unittest.TestCase):
    def test_rewrites_the_system_shall(self):
        s = user_stories.to_user_story("The system shall generate an SRS.")
        self.assertEqual(s, "As a user, I want to generate an SRS.")

    def test_includes_rationale_as_so_that(self):
        s = user_stories.to_user_story("The system shall run offline.", rationale="there is no cloud")
        self.assertEqual(s, "As a user, I want to run offline, so that there is no cloud.")

    def test_handles_non_canonical_statement(self):
        s = user_stories.to_user_story("Users can reset passwords")
        self.assertTrue(s.startswith("As a user, I want "))
        self.assertTrue(s.endswith("."))

    def test_empty(self):
        self.assertEqual(user_stories.to_user_story(""), "As a user, I want ...")


class TestBuildUserStories(unittest.TestCase):
    def setUp(self):
        fd, self.dbpath = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = db.connect(self.dbpath)
        db.init_schema(self.conn)
        self.pid = db.create_project(self.conn, "Imprint", "agile", "Agile project.")
        db.add_requirement(self.conn, self.pid, "Functional",
                           "The system shall generate an SRS.", moscow="Must")
        db.add_requirement(self.conn, self.pid, "Non-Functional",
                           "The system shall run fully offline.", moscow="Should")
        self.out = tempfile.mktemp(suffix=".docx")

    def tearDown(self):
        self.conn.close()
        os.unlink(self.dbpath)
        if os.path.exists(self.out):
            os.unlink(self.out)

    def test_document_contains_stories_grouped_by_priority(self):
        project = db.get_project(self.conn, self.pid)
        reqs = db.list_requirements(self.conn, self.pid)
        user_stories.build_user_stories(project, reqs, self.out)
        text = "\n".join(p.text for p in Document(self.out).paragraphs)
        self.assertIn("User Stories (Agile)", text)
        self.assertIn("As a user, I want to generate an SRS.", text)
        self.assertIn("Must have", text)   # MoSCoW grouping heading
        self.assertIn("Should have", text)


if __name__ == "__main__":
    unittest.main()
