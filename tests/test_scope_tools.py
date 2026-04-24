import sqlite3
import unittest
from unittest import mock

import memory_server


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


class ScopeToolTests(unittest.TestCase):
    def test_remember_persists_scope(self) -> None:
        fake_conn = mock.MagicMock()
        fake_cursor = mock.MagicMock()
        fake_cursor.lastrowid = 7
        fake_conn.execute.side_effect = [fake_cursor, None]

        with mock.patch.object(memory_server, "db", return_value=fake_conn), mock.patch.object(
            memory_server, "embed", return_value=[0.1, 0.2]
        ), mock.patch.object(memory_server, "serialize", return_value=b"vec"):
            result = memory_server.remember("hello", scope="proj-a")

        insert_sql, insert_params = fake_conn.execute.call_args_list[0][0]
        self.assertIn("scope", insert_sql)
        self.assertEqual(insert_params[3], "proj-a")
        self.assertEqual(result["scope"], "proj-a")

    def test_recall_uses_scope_filter(self) -> None:
        fake_conn = mock.MagicMock()
        query_result = mock.MagicMock()
        query_result.fetchall.return_value = [
            {
                "id": "m1",
                "content": "hello",
                "tier": "warm",
                "scope": "proj-a",
                "importance": 0.8,
                "last_accessed": 0.0,
                "rowid": 1,
                "distance": 0.1,
            }
        ]
        fake_conn.execute.side_effect = [query_result, None]

        with mock.patch.object(memory_server, "db", return_value=fake_conn), mock.patch.object(
            memory_server, "embed", return_value=[0.1, 0.2]
        ), mock.patch.object(memory_server, "serialize", return_value=b"vec"), mock.patch.object(
            memory_server, "_decay_score", return_value=0.5
        ):
            result = memory_server.recall("hello", scope="proj-a")

        select_sql, select_params = fake_conn.execute.call_args_list[0][0]
        self.assertIn("m.scope = ?", select_sql)
        self.assertEqual(select_params[2], "proj-a")
        self.assertEqual(result[0]["scope"], "proj-a")

    def test_memories_defaults_to_global_scope(self) -> None:
        conn = _conn()
        conn.execute(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tier TEXT NOT NULL,
                scope TEXT NOT NULL,
                importance REAL NOT NULL,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO memories (id, content, tier, scope, importance, created_at, last_accessed)"
            " VALUES ('g1', 'global note', 'warm', 'global', 0.8, 1, 1)"
        )
        conn.execute(
            "INSERT INTO memories (id, content, tier, scope, importance, created_at, last_accessed)"
            " VALUES ('p1', 'proj note', 'warm', 'proj-a', 0.8, 1, 1)"
        )
        conn.commit()

        with mock.patch.object(memory_server, "db", return_value=conn):
            default_scope = memory_server.memories()
            project_scope = memory_server.memories(scope="proj-a")

        self.assertEqual([m["id"] for m in default_scope], ["g1"])
        self.assertEqual([m["id"] for m in project_scope], ["p1"])


if __name__ == "__main__":
    unittest.main()
