"""Courses, lessons, completion tracking and quiz grading."""
from fastapi import APIRouter, status

from .. import db
from ..errors import AppError
from ..schemas import LessonCompleteIn, QuizSubmitIn, sanitize_quiz
from ..services.progress import ensure_user, log_activity, recommended_lesson

router = APIRouter(tags=["courses"])


@router.get("/courses")
def list_courses():
    user = ensure_user()
    courses = db.query("SELECT * FROM courses ORDER BY order_index")
    out = []
    for c in courses:
        lesson_count = db.query_one(
            "SELECT COUNT(*) AS n FROM lessons WHERE course_id = ?", (c["id"],)
        )["n"]
        completed = db.query_one(
            "SELECT COUNT(*) AS n FROM lesson_completions lc "
            "JOIN lessons l ON l.id = lc.lesson_id "
            "WHERE lc.user_id = ? AND l.course_id = ?",
            (user["id"], c["id"]),
        )["n"]
        out.append({
            "id": c["id"],
            "slug": c["slug"],
            "title": c["title"],
            "description": c["description"],
            "language": c["language"],
            "level": c["level"],
            "status": c["status"],
            "overview": c["overview"],
            "prerequisites": c["prerequisites"],
            "outline": c["outline"],
            "lessons_total": lesson_count,
            "lessons_completed": completed,
            "percent": round(100.0 * completed / lesson_count, 1) if lesson_count else 0.0,
        })
    return {"courses": out, "recommended_lesson": recommended_lesson(user["id"])}


@router.get("/courses/{course_slug}")
def course_detail(course_slug: str):
    user = ensure_user()
    course = db.query_one("SELECT * FROM courses WHERE slug = ?", (course_slug,))
    if course is None:
        raise AppError(404, "not_found", "Course not found.")

    lessons = db.query(
        "SELECT * FROM lessons WHERE course_id = ? ORDER BY order_index",
        (course["id"],),
    )
    items = []
    for l in lessons:
        done = db.query_one(
            "SELECT * FROM lesson_completions WHERE user_id = ? AND lesson_id = ?",
            (user["id"], l["id"]),
        )
        best = db.query_one(
            "SELECT MAX(score * 100 / MAX(total, 1)) AS best FROM quiz_results "
            "WHERE user_id = ? AND lesson_id = ?",
            (user["id"], l["id"]),
        )
        items.append({
            "id": l["id"],
            "slug": l["slug"],
            "title": l["title"],
            "summary": l["summary"],
            "order_index": l["order_index"],
            "completed": done is not None,
            "quiz_best": best["best"] if best and best["best"] is not None else None,
        })
    return {
        "id": course["id"],
        "slug": course["slug"],
        "title": course["title"],
        "description": course["description"],
        "language": course["language"],
        "level": course["level"],
        "status": course["status"],
        "overview": course["overview"],
        "prerequisites": course["prerequisites"],
        "outline": course["outline"],
        "lessons": items,
    }


@router.get("/courses/{course_slug}/lessons/{lesson_slug}")
def lesson_detail(course_slug: str, lesson_slug: str):
    user = ensure_user()
    lesson = db.query_one(
        "SELECT l.*, c.slug AS course_slug, c.title AS course_title "
        "FROM lessons l JOIN courses c ON c.id = l.course_id "
        "WHERE c.slug = ? AND l.slug = ?",
        (course_slug, lesson_slug),
    )
    if lesson is None:
        raise AppError(404, "not_found", "Lesson not found.")

    done = db.query_one(
        "SELECT * FROM lesson_completions WHERE user_id = ? AND lesson_id = ?",
        (user["id"], lesson["id"]),
    )
    best = db.query_one(
        "SELECT MAX(score * 100 / MAX(total, 1)) AS best FROM quiz_results "
        "WHERE user_id = ? AND lesson_id = ?",
        (user["id"], lesson["id"]),
    )
    siblings = db.query(
        "SELECT id, slug FROM lessons WHERE course_id = ? ORDER BY order_index",
        (lesson["course_id"],),
    )
    idx = next((i for i, s in enumerate(siblings) if s["id"] == lesson["id"]), None)
    prev_slug = siblings[idx - 1]["slug"] if idx and idx > 0 else None
    next_slug = siblings[idx + 1]["slug"] if idx is not None and idx + 1 < len(siblings) else None

    exercise = db.query_one(
        "SELECT * FROM exercises WHERE lesson_id = ? ORDER BY order_index LIMIT 1",
        (lesson["id"],),
    )
    from ..schemas import sanitize_exercise
    return {
        "id": lesson["id"],
        "slug": lesson["slug"],
        "title": lesson["title"],
        "summary": lesson["summary"],
        "objectives": lesson["objectives"],
        "sections": lesson["sections"],
        "example": lesson["example"],
        "quiz": sanitize_quiz(lesson["quiz"] or []),
        "course_slug": lesson["course_slug"],
        "course_title": lesson["course_title"],
        "completed": done is not None,
        "time_spent_seconds": done["time_spent_seconds"] if done else 0,
        "quiz_best": best["best"] if best and best["best"] is not None else None,
        "prev_lesson": prev_slug,
        "next_lesson": next_slug,
        "exercise": sanitize_exercise(exercise) if exercise else None,
    }


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: int, body: LessonCompleteIn):
    user = ensure_user()
    lesson = db.query_one("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
    if lesson is None:
        raise AppError(404, "not_found", "Lesson not found.")
    existing = db.query_one(
        "SELECT * FROM lesson_completions WHERE user_id = ? AND lesson_id = ?",
        (user["id"], lesson_id),
    )
    if existing is None:
        db.execute(
            "INSERT INTO lesson_completions (user_id, lesson_id, time_spent_seconds) "
            "VALUES (?, ?, ?)",
            (user["id"], lesson_id, body.time_spent_seconds),
        )
        log_activity(user["id"], "lesson_completed", lesson["slug"],
                     {"title": lesson["title"]})
    else:
        db.execute(
            "UPDATE lesson_completions SET time_spent_seconds = "
            "MIN(time_spent_seconds + ?, 86400) WHERE user_id = ? AND lesson_id = ?",
            (body.time_spent_seconds, user["id"], lesson_id),
        )
    return {"completed": True}


@router.delete("/lessons/{lesson_id}/complete", status_code=204)
def uncomplete_lesson(lesson_id: int):
    user = ensure_user()
    db.execute(
        "DELETE FROM lesson_completions WHERE user_id = ? AND lesson_id = ?",
        (user["id"], lesson_id),
    )
    return None


@router.post("/lessons/{lesson_id}/quiz")
def submit_quiz(lesson_id: int, body: QuizSubmitIn):
    """Grade a lesson quiz deterministically (server-side answers)."""
    user = ensure_user()
    lesson = db.query_one("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
    if lesson is None:
        raise AppError(404, "not_found", "Lesson not found.")
    quiz = lesson["quiz"] or []
    if not quiz:
        raise AppError(400, "no_quiz", "This lesson has no quiz.")

    per_question = []
    score = 0
    for q in quiz:
        chosen = body.answers.get(str(q["id"]))
        correct = chosen == q["answer"]
        if correct:
            score += 1
        per_question.append({
            "id": q["id"],
            "correct": correct,
            "chosen": chosen,
            "answer_index": q["answer"],
            "explanation": q["explanation"],
        })

    db.execute(
        "INSERT INTO quiz_results (user_id, lesson_id, score, total, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (user["id"], lesson_id, score, len(quiz),
         __import__("json").dumps({"answers": body.answers})),
    )
    log_activity(user["id"], "quiz_taken", lesson["slug"],
                 {"score": score, "total": len(quiz)})

    best = db.query_one(
        "SELECT MAX(score * 100 / MAX(total, 1)) AS best FROM quiz_results "
        "WHERE user_id = ? AND lesson_id = ?",
        (user["id"], lesson_id),
    )
    return {
        "score": score,
        "total": len(quiz),
        "per_question": per_question,
        "best": best["best"] if best else None,
    }
