"""Tests for the assistant's pure logic (no Ollama needed).

The model call itself isn't unit-tested (it needs a running daemon), but the
reply-parsing and the graceful-unavailable path are — those are what protect the
app when the model is off.

Run from the project root:  py -3 -m unittest discover -s tests
"""

import unittest

from imprint import assistant


class TestAssistantParsing(unittest.TestCase):
    def test_parses_labeled_reply(self):
        reply = (
            "Statement: The system shall let a user log in with email and password.\n"
            "Acceptance criteria: A valid email/password pair grants access; invalid is rejected."
        )
        out = assistant.parse_draft(reply)
        self.assertTrue(out["statement"].startswith("The system shall let a user log in"))
        self.assertIn("grants access", out["acceptance_criteria"])

    def test_tolerates_bullets_and_numbering(self):
        reply = "1. Statement: The system shall export an SRS as a .docx file."
        out = assistant.parse_draft(reply)
        self.assertEqual(out["statement"], "The system shall export an SRS as a .docx file.")

    def test_unlabeled_reply_becomes_statement(self):
        reply = "The system shall run fully offline."
        out = assistant.parse_draft(reply)
        self.assertEqual(out["statement"], "The system shall run fully offline.")
        self.assertEqual(out["acceptance_criteria"], "")

    def test_empty_reply(self):
        out = assistant.parse_draft("")
        self.assertEqual(out["statement"], "")

    def test_unavailable_assistant_returns_none(self):
        # Force the unavailable path — draft_requirement must degrade, not raise.
        a = assistant.RequirementAssistant.__new__(assistant.RequirementAssistant)
        a.available = False
        a.model = "x"
        self.assertIsNone(a.draft_requirement("some note"))


if __name__ == "__main__":
    unittest.main()
