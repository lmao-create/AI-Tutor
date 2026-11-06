"""Exercises: listing, deterministic grading, progressive hints and solutions.

Answers, hints and solutions NEVER leave this module ungraded - the client
only ever sees sanitized exercise rows and the results of its submissions.
"""
from fastapi import APIRouter, status

from .. import db
from ..errors import AppError
from ..schemas import ExerciseSubmitIn, sanitize_exercise
from ..services.grader import grade, hint_payload, solution_payload
from ..services.progress import ensure_user, log_activity

router = APIRouter(prefix="/exercises", tags=["exercises"])


def _get_exercise(exercise_id: int) -> dict:
    row = db.query_one("SELECT * FROM exercises WHERE id = ?", (exercise_id,))
    if row is None:
        raise AppError(404, "not_found", "Exercise not found.")
    return row


def _user_status(user_id: int, exercise_id: int) -> dict:
    attempts = db.query(
        "SELECT * FROM exercise_attempts WHERE user_id = ? AND exercise_id = ? "
        "ORDER BY id DESC",
        (user_id, exercise_id),
    )
    hints = db.query_one(
        "SELECT revealed FROM hint_reveals WHERE user_id = ? AND exercise_id = ?",
        (user_id, exercise_id),
    )
    return {
        "attempts": len(attempts),
        "passed": any(a["passed"] for a in attempts),
        "hints_revealed": hints["revealed"] if hints else 0,
    }


def _detailed(row: dict, user_id: int) -> dict:
    return {**sanitize_exercise(row), "status": _user_status(user_id, row["id"])}


@router.get("")
def list_exercises(course: str | None = None, kind: str | None = None,
                   difficulty: int | None = None, lesson_id: int | None = None):
    user = ensure_user()
    sql = ("SELECT e.* FROM exercises e JOIN courses c ON c.id = e.course_id "
           "WHERE 1=1")
    params: list = []
    if course:
        sql += " AND c.slug = ?"
        params.append(course)
    if kind:
        sql += " AND e.kind = ?"
        params.append(kind)
    if difficulty is not None:
        sql += " AND e.difficulty = ?"
        params.append(difficulty)
    if lesson_id is not None:
        sql += " AND e.lesson_id = ?"
        params.append(lesson_id)
    sql += " ORDER BY e.course_id, e.order_index, e.id"
    rows = db.query(sql, tuple(params))
    return {"exercises": [sanitize_exercise(r) for r in rows]}


@router.get("/{exercise_id}")
def get_exercise(exercise_id: int):
    user = ensure_user()
    row = _get_exercise(exercise_id)
    return _detailed(row, user["id"])


@router.post("/{exercise_id}/submit")
def submit_exercise(exercise_id: int, body: ExerciseSubmitIn):
    user = ensure_user()
    row = _get_exercise(exercise_id)

    submission = {k: v for k, v in body.model_dump().items() if v is not None}
    hints_used = db.query_one(
        "SELECT revealed FROM hint_reveals WHERE user_id = ? AND exercise_id = ?",
        (user["id"], exercise_id),
    )
    hints_used_n = hints_used["revealed"] if hints_used else 0

    result = grade(row, submission)
    passed = bool(result["passed"])

    db.execute(
        "INSERT INTO exercise_attempts (user_id, exercise_id, submission, passed, "
        "hints_used) VALUES (?, ?, ?, ?, ?)",
        (user["id"], exercise_id, __import__("json").dumps(submission)[:4000],
         1 if passed else 0, hints_used_n),
    )
    log_activity(user["id"], "exercise_submitted", row["slug"],
                 {"passed": passed, "kind": row["kind"]})

    # Reveal the correct choice once the answer is earned (i.e. on success).
    if passed and row["answer"]:
        ans = row["answer"]
        if row["kind"] == "mcq":
            result["feedback"]["answer_index"] = ans.get("index")
        elif row["kind"] == "find_bug":
            result["feedback"]["answer_line"] = ans.get("line")

    return {**result, "status": _user_status(user["id"], exercise_id)}


@router.post("/{exercise_id}/hint")
def next_hint(exercise_id: int):
    """Reveal hints ONE at a time, in order. Solution only after all hints."""
    user = ensure_user()
    row = _get_exercise(exercise_id)

    current = db.query_one(
        "SELECT revealed FROM hint_reveals WHERE user_id = ? AND exercise_id = ?",
        (user["id"], exercise_id),
    )
    revealed = current["revealed"] if current else 0
    total_hints = len(row.get("hints") or [])

    if revealed > total_hints:
        raise AppError(400, "all_revealed",
                       "All hints and the solution have already been revealed.")

    payload = hint_payload(row, revealed)

    if current:
        db.execute(
            "UPDATE hint_reveals SET revealed = revealed + 1, "
            "updated_at = datetime('now') "
            "WHERE user_id = ? AND exercise_id = ?",
            (user["id"], exercise_id),
        )
    else:
        db.execute(
            "INSERT INTO hint_reveals (user_id, exercise_id, revealed) "
            "VALUES (?, ?, 1)",
            (user["id"], exercise_id),
        )
    log_activity(user["id"], "hint_revealed", row["slug"],
                 {"level": payload.get("level"), "type": payload.get("type")})
    return payload


@router.get("/{exercise_id}/solution")
def get_solution(exercise_id: int):
    """Full solution - the client asks for confirmation before calling this."""
    user = ensure_user()
    row = _get_exercise(exercise_id)
    log_activity(user["id"], "solution_viewed", row["slug"], {})
    return solution_payload(row)
