"""Database layer tests: migrations, CRUD, JSON decoding, transactions."""
import sqlite3


def test_migrations_apply_and_are_idempotent(fresh_db):
    from app.db import migrate
    conn = fresh_db.get_conn()
    applied = conn.execute("SELECT version FROM schema_migrations").fetchall()
    versions = {r["version"] for r in applied}
    assert versions >= {1, 2}
    # Running migrate again changes nothing and does not fail.
    before = conn.execute("SELECT COUNT(*) AS n FROM lessons").fetchone()["n"]
    migrate(conn)
    after = conn.execute("SELECT COUNT(*) AS n FROM lessons").fetchone()["n"]
    assert before == after


def test_seeding_creates_expected_content(fresh_db):
    from app.seed import seed_all
    stats = seed_all()
    assert stats["courses"] == 10
    assert stats["lessons"] == 22
    assert stats["projects"] == 9
    assert stats["exercises"] == 22 + 12  # 22 lesson exercises + 12 practice
    # Idempotent: reseed updates in place, no duplicates.
    seed_all()
    n = fresh_db.query_one("SELECT COUNT(*) AS n FROM lessons")["n"]
    assert n == 22
    n = fresh_db.query_one("SELECT COUNT(*) AS n FROM exercises")["n"]
    assert n == 34


def test_json_columns_decode_on_read(fresh_db):
    fresh_db.execute(
        "INSERT INTO courses (slug, title, description, language, prerequisites) "
        "VALUES ('t', 'T', 'd', 'x', '[\"a\", \"b\"]')"
    )
    row = fresh_db.query_one("SELECT * FROM courses WHERE slug = 't'")
    assert row["prerequisites"] == ["a", "b"]


def test_bad_json_does_not_crash_reads(fresh_db):
    fresh_db.execute(
        "INSERT INTO courses (slug, title, description, language, prerequisites) "
        "VALUES ('t', 'T', 'd', 'x', 'not json at all')"
    )
    row = fresh_db.query_one("SELECT * FROM courses WHERE slug = 't'")
    assert row["prerequisites"] == "not json at all"


def test_transaction_rolls_back_on_error(fresh_db):
    from app.db import tx
    fresh_db.execute(
        "INSERT INTO users (username, display_name) VALUES ('u1', 'U1')"
    )
    try:
        with tx() as conn:
            conn.execute(
                "INSERT INTO users (username, display_name) VALUES ('u2', 'U2')"
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    names = [r["username"] for r in fresh_db.query("SELECT username FROM users")]
    assert "u1" in names and "u2" not in names


def test_foreign_keys_enforced(fresh_db):
    fresh_db.execute("INSERT INTO users (username, display_name) VALUES ('u', 'U')")
    try:
        fresh_db.execute(
            "INSERT INTO conversations (user_id, title) VALUES (999, 'x')")
        assert False, "FK violation should raise"
    except sqlite3.IntegrityError:
        pass
