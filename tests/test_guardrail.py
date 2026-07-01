"""Tests for scope-drift detection (pure) and baseline snapshots (db).

Run from the project root:  py -3 -m unittest discover -s tests
"""

import os
import tempfile
import unittest

from imprint import db, guardrail


def _rows(pairs):
    return [{"req_key": k, "statement": s} for k, s in pairs]


class TestCheckDrift(unittest.TestCase):
    def test_green_when_identical(self):
        cur = base = _rows([("REQ-0001", "shall A"), ("REQ-0002", "shall B")])
        r = guardrail.check_drift(cur, base)
        self.assertEqual(r["zone"], "GREEN")
        self.assertEqual(len(r["stable"]), 2)

    def test_yellow_on_addition(self):
        base = _rows([("REQ-0001", "shall A")])
        cur = _rows([("REQ-0001", "shall A"), ("REQ-0002", "shall B")])
        r = guardrail.check_drift(cur, base)
        self.assertEqual(r["zone"], "YELLOW")
        self.assertEqual(r["added"], ["REQ-0002"])

    def test_yellow_on_change(self):
        base = _rows([("REQ-0001", "shall A")])
        cur = _rows([("REQ-0001", "shall A, revised")])
        r = guardrail.check_drift(cur, base)
        self.assertEqual(r["zone"], "YELLOW")
        self.assertEqual(r["changed"], ["REQ-0001"])

    def test_red_on_removal(self):
        base = _rows([("REQ-0001", "shall A"), ("REQ-0002", "shall B")])
        cur = _rows([("REQ-0001", "shall A")])
        r = guardrail.check_drift(cur, base)
        self.assertEqual(r["zone"], "RED")
        self.assertEqual(r["removed"], ["REQ-0002"])

    def test_summary_mentions_zone(self):
        r = guardrail.check_drift(_rows([("REQ-0001", "x")]), _rows([("REQ-0001", "x")]))
        self.assertIn("GREEN", guardrail.summarize(r))


class TestBaselineSnapshot(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = db.connect(self.path)
        db.init_schema(self.conn)
        self.pid = db.create_project(self.conn, "P", "waterfall")
        db.add_requirement(self.conn, self.pid, "Functional", "The system shall A.")
        db.add_requirement(self.conn, self.pid, "Functional", "The system shall B.")

    def tearDown(self):
        self.conn.close()
        os.unlink(self.path)

    def test_lock_snapshots_current_requirements(self):
        bid = db.lock_baseline(self.conn, self.pid)
        base = db.get_latest_baseline(self.conn, self.pid)
        self.assertIsNotNone(base)
        self.assertEqual(base["id"], bid)
        items = db.list_baseline_items(self.conn, bid)
        self.assertEqual(len(items), 2)

    def test_end_to_end_drift_detected_after_add(self):
        db.lock_baseline(self.conn, self.pid)
        db.add_requirement(self.conn, self.pid, "Functional", "The system shall C (new scope).")
        base = db.get_latest_baseline(self.conn, self.pid)
        report = guardrail.check_drift(
            db.list_requirements(self.conn, self.pid),
            db.list_baseline_items(self.conn, base["id"]))
        self.assertEqual(report["zone"], "YELLOW")
        self.assertEqual(report["added"], ["REQ-0003"])


if __name__ == "__main__":
    unittest.main()
