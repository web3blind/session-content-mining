from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inventory.py"
ZONE = ZoneInfo("Europe/Moscow")


def make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL, archived INTEGER DEFAULT 0);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp REAL,
            role TEXT,
            content TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO sessions (id, started_at) VALUES (?, ?)",
        [("s-active", 1720000000), ("s-archived", 1719000000)],
    )
    conn.execute("UPDATE sessions SET archived=1 WHERE id=?", ("s-archived",))
    rows = [
        # inside the window (2024-07-01 .. 2024-07-05 Europe/Moscow)
        ("s-active", datetime(2024, 7, 1, 0, 0, tzinfo=ZONE).timestamp(), "user", "alpha-secret"),
        ("s-active", datetime(2024, 7, 3, 12, 0, tzinfo=ZONE).timestamp(), "assistant", "beta-secret"),
        # boundary: exactly at start (inclusive) and at end (exclusive)
        ("s-archived", datetime(2024, 7, 1, 0, 0, tzinfo=ZONE).timestamp(), "user", "gamma-secret"),
        ("s-archived", datetime(2024, 7, 5, 0, 0, tzinfo=ZONE).timestamp(), "assistant", "delta-secret"),
        # outside the window
        ("s-active", datetime(2024, 6, 30, 23, 59, tzinfo=ZONE).timestamp(), "user", "epsilon-secret"),
        # a session whose start is outside the window but a message is inside:
        # the archived session started long before the window.
        ("s-archived", datetime(2024, 7, 4, 6, 0, tzinfo=ZONE).timestamp(), "user", "zeta-secret"),
        # message in a session with no sessions row
        ("s-lost", datetime(2024, 7, 2, 9, 0, tzinfo=ZONE).timestamp(), "assistant", "eta-secret"),
        ("s-tools", datetime(2024, 7, 2, tzinfo=ZONE).timestamp(), "tool", "tool-secret"),
        ("s-tools", datetime(2024, 7, 2, tzinfo=ZONE).timestamp(), "system", "system-secret"),
        # message with a missing timestamp
        ("s-active", None, "user", "theta-secret"),
        # message with a non-numeric timestamp
        ("s-active", "not-a-time", "user", "iota-secret"),
    ]
    conn.executemany(
        "INSERT INTO messages (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)", rows
    )
    conn.commit()
    conn.close()


def db_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InventoryCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "state.db"
        make_db(self.db)
        self.manifest = self.root / "manifest-default.json"

    def run_cli(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--db",
                str(self.db),
                "--profile",
                "default",
                "--start",
                "2024-07-01",
                "--end-exclusive",
                "2024-07-05",
                "--timezone",
                "Europe/Moscow",
                "--out",
                str(self.manifest),
            ],
            capture_output=True,
            text=True,
        )

    def load_manifest(self) -> dict:
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def test_inclusive_start_exclusive_end(self) -> None:
        self.run_cli().check_returncode()
        m = self.load_manifest()
        by_session = {s["session_id"]: s for s in m["sessions"]}
        # boundary message at start is in, at end is out
        archived = by_session["s-archived"]["messages"]
        roles = {(x["role"], x["id"]) for x in archived}
        self.assertTrue(any(r == "user" for r, _ in roles), "start edge included")
        self.assertEqual(len(archived), 2)  # edge-in + late-msg, edge-out excluded
        active = by_session["s-active"]["messages"]
        self.assertEqual(len(active), 2)  # first + mid; before-window excluded

    def test_all_roles_and_orphan_session(self) -> None:
        self.run_cli().check_returncode()
        m = self.load_manifest()
        by_session = {s["session_id"]: s for s in m["sessions"]}
        self.assertEqual(
            sorted({x["role"] for s in m["sessions"] for x in s["messages"]}),
            ["assistant", "system", "tool", "user"],
        )
        self.assertFalse(by_session["s-lost"]["session_record_exists"])
        self.assertTrue(by_session["s-active"]["session_record_exists"])
        for s in m["sessions"]:
            self.assertEqual(s["review_status"], "pending")

    def test_unplaced_timestamp_rows_reported(self) -> None:
        self.run_cli().check_returncode()
        m = self.load_manifest()
        self.assertEqual(m["unplaced_timestamp_rows"], 2)

    def test_no_transcript_text_in_manifest(self) -> None:
        self.run_cli().check_returncode()
        text = self.manifest.read_text(encoding="utf-8")
        for secret in ("alpha-secret", "beta-secret", "gamma-secret", "delta-secret",
                       "epsilon-secret", "zeta-secret", "eta-secret", "theta-secret",
                       "iota-secret", "not-a-time"):
            self.assertNotIn(secret, text)
        self.assertNotIn("content", json.loads(text)["sessions"][0]["messages"][0])

    def test_database_unchanged(self) -> None:
        before = db_file_hash(self.db)
        self.run_cli().check_returncode()
        self.assertEqual(before, db_file_hash(self.db))

    def test_manifest_owner_only_and_no_overwrite(self) -> None:
        self.run_cli().check_returncode()
        self.assertEqual(os.stat(self.manifest).st_mode & 0o777, 0o600)
        second = self.run_cli()
        self.assertNotEqual(second.returncode, 0)

    def test_invalid_interval_rejected(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--db",
                str(self.db),
                "--profile",
                "default",
                "--start",
                "2024-07-05",
                "--end-exclusive",
                "2024-07-01",
                "--timezone",
                "Europe/Moscow",
                "--out",
                str(self.root / "bad.json"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.root / "bad.json").exists())

    def test_counts_and_summary(self) -> None:
        result = self.run_cli()
        result.check_returncode()
        summary = json.loads(result.stdout)
        self.assertEqual(summary["inventory_only"], True)
        m = self.load_manifest()
        self.assertEqual(summary["session_count"], m["session_count"])
        self.assertEqual(summary["message_count"], m["message_count"])
        self.assertEqual(m["session_count"], 4)
        self.assertEqual(m["message_count"], 7)  # includes tool-only session
        self.assertTrue(m["sessions"][0]["link"].startswith("@session:default/"))


if __name__ == "__main__":
    unittest.main()
