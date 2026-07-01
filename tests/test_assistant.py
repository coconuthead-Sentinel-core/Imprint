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
        # Force the unavailable path — draft_requirement/chat must degrade, not raise.
        a = assistant.RequirementAssistant.__new__(assistant.RequirementAssistant)
        a.available = False
        a.model = "x"
        self.assertIsNone(a.draft_requirement("some note"))
        self.assertIsNone(a.chat([{"role": "user", "content": "hi"}]))

    def test_extract_requirement_finds_canonical_line(self):
        reply = ("Good question. Here's one:\n"
                 "The system shall let a user reset their password by email\n"
                 "Want me to add it?")
        got = assistant.extract_requirement(reply)
        self.assertEqual(got, "The system shall let a user reset their password by email.")

    def test_extract_requirement_falls_back_to_first_line(self):
        self.assertEqual(assistant.extract_requirement("just some text"), "just some text")
        self.assertEqual(assistant.extract_requirement(""), "")

    def test_extract_requirements_captures_all(self):
        reply = (
            "Here's what I've got so far:\n"
            "The system shall automatically generate the SDLC paperwork.\n"
            "The system shall allow users to update the paperwork as needed.\n"
            "The system shall track progress across Agile and Waterfall.\n"
            "Anything else?"
        )
        got = assistant.extract_requirements(reply)
        self.assertEqual(len(got), 3)
        self.assertTrue(all(s.startswith("The system shall") and s.endswith(".") for s in got))

    def test_extract_requirements_dedupes(self):
        reply = ("The system shall log in users.\n"
                 "The system shall log in users\n")  # same, one has no period
        self.assertEqual(len(assistant.extract_requirements(reply)), 1)


if __name__ == "__main__":
    unittest.main()
