import sqlite3
import unittest
from unittest import mock

import memory_server


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


class MigrationTests(unittest.TestCase):
    def test_get_schema_version_defaults_to_zero(self) -> None:
        conn = _conn()
        memory_server._ensure_migrations_table(conn)
        self.assertEqual(memory_server._get_schema_version(conn), 0)

    def test_apply_migrations_is_idempotent(self) -> None:
        conn = _conn()
        calls: list[int] = []

        def migration_1(c: sqlite3.Connection) -> None:
            calls.append(1)
            c.execute("CREATE TABLE IF NOT EXISTS m1 (id INTEGER)")

        def migration_2(c: sqlite3.Connection) -> None:
            calls.append(2)
            c.execute("CREATE TABLE IF NOT EXISTS m2 (id INTEGER)")

        with mock.patch.object(memory_server, "MIGRATIONS", {1: migration_1, 2: migration_2}), mock.patch.object(
            memory_server, "CURRENT_SCHEMA_VERSION", 2
        ):
            memory_server._apply_migrations(conn)
            memory_server._apply_migrations(conn)

        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        self.assertEqual([row["version"] for row in rows], [1, 2])
        self.assertEqual(calls, [1, 2])

    def test_apply_migrations_raises_on_missing_version(self) -> None:
        conn = _conn()

        with mock.patch.object(memory_server, "MIGRATIONS", {1: lambda c: None}), mock.patch.object(
            memory_server, "CURRENT_SCHEMA_VERSION", 2
        ):
            with self.assertRaisesRegex(RuntimeError, "missing migration for schema version 2"):
                memory_server._apply_migrations(conn)

    def test_initial_migration_works_with_preexisting_schema(self) -> None:
        conn = _conn()
        conn.execute(
            """
            CREATE TABLE memories (
                id            TEXT PRIMARY KEY,
                content       TEXT NOT NULL,
                tier          TEXT NOT NULL,
                importance    REAL NOT NULL DEFAULT 0.5,
                created_at    REAL NOT NULL,
                last_accessed REAL NOT NULL
            )
            """
        )
        conn.commit()

        def migration_1(c: sqlite3.Connection) -> None:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id            TEXT PRIMARY KEY,
                    content       TEXT NOT NULL,
                    tier          TEXT NOT NULL,
                    importance    REAL NOT NULL DEFAULT 0.5,
                    created_at    REAL NOT NULL,
                    last_accessed REAL NOT NULL
                )
                """
            )

        with mock.patch.object(memory_server, "MIGRATIONS", {1: migration_1}), mock.patch.object(
            memory_server, "CURRENT_SCHEMA_VERSION", 1
        ):
            memory_server._apply_migrations(conn)

        versions = conn.execute("SELECT COUNT(*) AS c FROM schema_migrations WHERE version = 1").fetchone()["c"]
        self.assertEqual(versions, 1)


if __name__ == "__main__":
    unittest.main()
