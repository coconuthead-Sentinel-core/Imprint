"""Unit tests for the Imprint data core — no GUI required.

Run from the project root:  py -3 -m unittest discover -s tests
"""

import os
import sqlite3
import tempfile
import unittest

from imprint import db, models


class TestImprintDb(unittest.TestCase):
    def setUp(self):
        # Each test gets its own throwaway database file.
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = db.connect(self.path)
        db.init_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.path)

    def test_create_and_list_project(self):
        pid = db.create_project(self.conn, "Imprint", "waterfall", "test project")
        self.assertIsInstance(pid, int)
        projects = db.list_projects(self.conn)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Imprint")
        self.assertEqual(projects[0]["methodology"], "waterfall")

    def test_blank_name_rejected(self):
        with self.assertRaises(ValueError):
            db.create_project(self.conn, "   ", "agile")

    def test_bad_methodology_rejected(self):
        with self.assertRaises(ValueError):
            db.create_project(self.conn, "X", "kanban")  # not one of the three

    def test_requirement_key_sequence(self):
        pid = db.create_project(self.conn, "P", "waterfall")
        r1 = db.add_requirement(self.conn, pid, "Functional", "The system shall log in users.")
        r2 = db.add_requirement(self.conn, pid, "Functional", "The system shall log out users.")
        self.assertEqual(r1["req_key"], "REQ-0001")
        self.assertEqual(r2["req_key"], "REQ-0002")

    def test_keys_are_per_project(self):
        a = db.create_project(self.conn, "A", "agile")
        b = db.create_project(self.conn, "B", "vmodel")
        ra = db.add_requirement(self.conn, a, "Functional", "A requirement.")
        rb = db.add_requirement(self.conn, b, "Functional", "B requirement.")
        # Both projects start their own REQ-0001 sequence.
        self.assertEqual(ra["req_key"], "REQ-0001")
        self.assertEqual(rb["req_key"], "REQ-0001")

    def test_blank_statement_rejected(self):
        pid = db.create_project(self.conn, "P", "waterfall")
        with self.assertRaises(ValueError):
            db.add_requirement(self.conn, pid, "Functional", "   ")

    def test_requirement_needs_real_project(self):
        with self.assertRaises(ValueError):
            db.add_requirement(self.conn, 999, "Functional", "Orphan requirement.")

    def test_transaction_rolls_back_on_error(self):
        pid = db.create_project(self.conn, "P", "waterfall")
        before = len(db.list_requirements(self.conn, pid))
        # Force a failure *inside* a transaction and confirm nothing persisted.
        with self.assertRaises(sqlite3.IntegrityError):
            with db.transaction(self.conn):
                self.conn.execute(
                    "INSERT INTO requirements "
                    "(project_id, req_key, req_type, statement, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (pid, "REQ-0001", "Functional", "ok", "now", "now"),
                )
                # Duplicate req_key for the same project violates UNIQUE -> rollback.
                self.conn.execute(
                    "INSERT INTO requirements "
                    "(project_id, req_key, req_type, statement, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (pid, "REQ-0001", "Functional", "dup", "now", "now"),
                )
        after = len(db.list_requirements(self.conn, pid))
        self.assertEqual(before, after)  # both inserts rolled back together

    def test_update_requirement(self):
        pid = db.create_project(self.conn, "P", "waterfall")
        r = db.add_requirement(self.conn, pid, "Functional", "The system shall do X.", moscow="Could")
        updated = db.update_requirement(self.conn, r["id"], "Non-Functional",
                                        "The system shall do X better.", "Must", "criteria here")
        self.assertEqual(updated["statement"], "The system shall do X better.")
        self.assertEqual(updated["req_type"], "Non-Functional")
        self.assertEqual(updated["moscow"], "Must")
        self.assertEqual(updated["req_key"], r["req_key"])  # key preserved on edit

    def test_update_requirement_rejects_blank(self):
        pid = db.create_project(self.conn, "P", "agile")
        r = db.add_requirement(self.conn, pid, "Functional", "The system shall exist.")
        with self.assertRaises(ValueError):
            db.update_requirement(self.conn, r["id"], "Functional", "   ", "Must")

    def test_delete_requirement(self):
        pid = db.create_project(self.conn, "P", "vmodel")
        r = db.add_requirement(self.conn, pid, "Functional", "The system shall vanish.")
        db.delete_requirement(self.conn, r["id"])
        self.assertEqual(len(db.list_requirements(self.conn, pid)), 0)

    def test_delete_project_cascades(self):
        pid = db.create_project(self.conn, "Doomed", "agile")
        db.add_requirement(self.conn, pid, "Functional", "The system shall be deleted.")
        db.add_chat_message(self.conn, pid, "user", "hi")
        db.lock_baseline(self.conn, pid)
        db.delete_project(self.conn, pid)
        self.assertIsNone(db.get_project(self.conn, pid))
        # children gone too (ON DELETE CASCADE + foreign_keys ON)
        self.assertEqual(len(db.list_requirements(self.conn, pid)), 0)
        self.assertEqual(len(db.list_chat_messages(self.conn, pid)), 0)
        self.assertIsNone(db.get_latest_baseline(self.conn, pid))

    def test_set_requirement_status(self):
        pid = db.create_project(self.conn, "P", "waterfall")
        r = db.add_requirement(self.conn, pid, "Functional", "The system shall do a thing.")
        self.assertEqual(r["status"], "draft")
        db.set_requirement_status(self.conn, r["id"], "baselined")
        again = db.list_requirements(self.conn, pid)[0]
        self.assertEqual(again["status"], "baselined")

    def test_set_requirement_status_rejects_bad_value(self):
        pid = db.create_project(self.conn, "P", "agile")
        r = db.add_requirement(self.conn, pid, "Functional", "The system shall exist.")
        with self.assertRaises(ValueError):
            db.set_requirement_status(self.conn, r["id"], "done-ish")

    def test_chat_messages_persist_and_scope_per_project(self):
        a = db.create_project(self.conn, "A", "agile")
        b = db.create_project(self.conn, "B", "waterfall")
        db.add_chat_message(self.conn, a, "user", "what does it do?")
        db.add_chat_message(self.conn, a, "assistant", "The system shall save conversations.")
        db.add_chat_message(self.conn, b, "user", "different project")
        msgs_a = db.list_chat_messages(self.conn, a)
        self.assertEqual([m["role"] for m in msgs_a], ["user", "assistant"])
        self.assertEqual(msgs_a[1]["content"], "The system shall save conversations.")
        self.assertEqual(len(db.list_chat_messages(self.conn, b)), 1)  # not bunched together

    def test_chat_survives_reconnect(self):
        # Simulate close + reopen: same file, new connection, history still there.
        pid = db.create_project(self.conn, "P", "agile")
        db.add_chat_message(self.conn, pid, "user", "remember this")
        self.conn.close()
        conn2 = db.connect(self.path)
        db.init_schema(conn2)
        self.assertEqual(db.list_chat_messages(conn2, pid)[0]["content"], "remember this")
        self.conn = conn2  # so tearDown closes it

    def test_clear_chat_messages(self):
        pid = db.create_project(self.conn, "P", "vmodel")
        db.add_chat_message(self.conn, pid, "user", "x")
        db.clear_chat_messages(self.conn, pid)
        self.assertEqual(len(db.list_chat_messages(self.conn, pid)), 0)

    def test_models_vocabulary(self):
        self.assertTrue(models.is_valid_methodology("agile"))
        self.assertFalse(models.is_valid_methodology("scrumban"))
        self.assertIn("Must", models.MOSCOW)


if __name__ == "__main__":
    unittest.main()
