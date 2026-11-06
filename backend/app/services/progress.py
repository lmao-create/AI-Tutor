"""Learning progress computation.

Every number here is derived from persisted data - nothing is hardcoded:
lesson completions, quiz results, exercise attempts, activity log days,
project milestones.
"""
import datetime as dt
from typing import Optional

from .. import db


def log_activity(user_id: int, kind: str, ref: str = "",
                 detail: Optional[dict] = None) -> None:
    import json
    db.execute(
        "INSERT INTO activity_log (user_id, kind, ref, detail) VALUES (?, ?, ?, ?)",
        (user_id, kind, ref, json.dumps(detail or {})),
    )


def ensure_user(user_id: int = 1) -> dict:
    """Single local user for now; structured so real auth can replace this."""
    user = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if user is None:
        db.execute(
            "INSERT OR IGNORE INTO users (id, username, display_name) "
            "VALUES (?, ?, ?)",
            (user_id, "local", "Learner"),
        )
        db.execute(
            "INSERT OR IGNORE INTO preferences (user_id) VALUES (?)", (user_id,)
        )
        user = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return user


def _parse_day(value: str) -> dt.date:
    return dt.date.fromisoformat(str(value)[:10])


def compute_streak(user_id: int) -> dict:
    """Current streak of consecutive activity days (UTC), and best streak."""
    rows = db.query(
        "SELECT DISTINCT substr(created_at, 1, 10) AS day FROM activity_log "
        "WHERE user_id = ? ORDER BY day DESC LIMIT 400",
        (user_id,),
    )
    days = {_parse_day(r["day"]) for r in rows}
    if not days:
        return {"current": 0, "best": 0, "active_today": False}

    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    current = 0
    if today in days or yesterday in days:
        cursor = today if today in days else yesterday
        while cursor in days:
            current += 1
            cursor -= dt.timedelta(days=1)

    best = 0
    run = 0
    prev: Optional[dt.date] = None
    for d in sorted(days):
        if prev is not None and d == prev + dt.timedelta(days=1):
            run += 1
        else:
            run = 1
        best = max(best, run)
        prev = d
    return {"current": current, "best": best, "active_today": today in days}


def overall_progress(user_id: int) -> dict:
    total = db.query_one(
        "SELECT COUNT(*) AS n FROM lessons WHERE course_id IN "
        "(SELECT id FROM courses WHERE status = 'complete')"
    )["n"]
    done = db.query_one(
        "SELECT COUNT(*) AS n FROM lesson_completions WHERE user_id = ?",
        (user_id,),
    )["n"]
    quizzes = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(AVG(score * 1.0 / MAX(total, 1)) * 100, 0) "
        "AS avg FROM quiz_results WHERE user_id = ?",
        (user_id,),
    )
    passed_ex = db.query_one(
        "SELECT COUNT(DISTINCT exercise_id) AS n FROM exercise_attempts "
        "WHERE user_id = ? AND passed = 1",
        (user_id,),
    )["n"]
    time_row = db.query_one(
        "SELECT COALESCE(SUM(time_spent_seconds), 0) AS t FROM lesson_completions "
        "WHERE user_id = ?",
        (user_id,),
    )
    completed_projects = 0
    rows = db.query(
        "SELECT p.id, "
        "(SELECT COUNT(*) FROM json_each(p.milestones)) AS total_ms "
        "FROM projects p"
    )
    for r in rows:
        done_ms = db.query_one(
            "SELECT COUNT(DISTINCT milestone_index) AS n FROM project_progress "
            "WHERE user_id = ? AND project_id = ?",
            (user_id, r["id"]),
        )["n"]
        if r["total_ms"] > 0 and done_ms >= r["total_ms"]:
            completed_projects += 1

    return {
        "lessons_total": total,
        "lessons_completed": done,
        "percent": round(100.0 * done / total, 1) if total else 0.0,
        "quizzes_taken": quizzes["n"],
        "quiz_average": round(quizzes["avg"], 1),
        "exercises_passed": passed_ex,
        "tracked_time_seconds": time_row["t"],
        "projects_completed": completed_projects,
    }


def per_course_progress(user_id: int) -> list[dict]:
    courses = db.query(
        "SELECT c.*, (SELECT COUNT(*) FROM lessons l WHERE l.course_id = c.id) "
        "AS lesson_count FROM courses c ORDER BY c.order_index"
    )
    out = []
    for c in courses:
        done = db.query_one(
            "SELECT COUNT(*) AS n FROM lesson_completions lc "
            "JOIN lessons l ON l.id = lc.lesson_id "
            "WHERE lc.user_id = ? AND l.course_id = ?",
            (user_id, c["id"]),
        )["n"]
        out.append({
            "slug": c["slug"],
            "title": c["title"],
            "status": c["status"],
            "lessons_total": c["lesson_count"],
            "lessons_completed": done,
            "percent": round(100.0 * done / c["lesson_count"], 1)
            if c["lesson_count"] else 0.0,
        })
    return out


def recommended_lesson(user_id: int) -> Optional[dict]:
    pref = db.query_one("SELECT active_course FROM preferences WHERE user_id = ?",
                        (user_id,))
    active = pref["active_course"] if pref else "python"
    lesson = _next_incomplete(user_id, active)
    if lesson is None:
        lesson = db.query_one(
            "SELECT l.*, c.slug AS course_slug, c.title AS course_title "
            "FROM lessons l JOIN courses c ON c.id = l.course_id "
            "WHERE c.status = 'complete' "
            "AND l.id NOT IN (SELECT lesson_id FROM lesson_completions "
            "                 WHERE user_id = ?) "
            "ORDER BY c.order_index, l.order_index LIMIT 1",
            (user_id,),
        )
    if lesson is None:
        return None
    return {
        "lesson_id": lesson["id"],
        "slug": lesson["slug"],
        "title": lesson["title"],
        "summary": lesson["summary"],
        "course_slug": lesson["course_slug"],
        "course_title": lesson["course_title"],
    }


def _next_incomplete(user_id: int, course_slug: str) -> Optional[dict]:
    return db.query_one(
        "SELECT l.*, c.slug AS course_slug, c.title AS course_title "
        "FROM lessons l JOIN courses c ON c.id = l.course_id "
        "WHERE c.slug = ? AND l.id NOT IN "
        "(SELECT lesson_id FROM lesson_completions WHERE user_id = ?) "
        "ORDER BY l.order_index LIMIT 1",
        (course_slug, user_id),
    )


def strengths_weaknesses(user_id: int) -> dict:
    """Topics grouped from real quiz scores and exercise pass rates."""
    rows = db.query(
        "SELECT l.id, l.title, l.slug, "
        "COALESCE(AVG(qr.score * 1.0 / MAX(qr.total, 1)) * 100, -1) AS quiz_avg, "
        "(SELECT COUNT(*) FROM exercise_attempts ea "
        " JOIN exercises e ON e.id = ea.exercise_id "
        " WHERE ea.user_id = ? AND e.lesson_id = l.id AND ea.passed = 1) AS ex_pass, "
        "(SELECT COUNT(*) FROM exercise_attempts ea "
        " JOIN exercises e ON e.id = ea.exercise_id "
        " WHERE ea.user_id = ? AND e.lesson_id = l.id) AS ex_total "
        "FROM lessons l "
        "LEFT JOIN quiz_results qr ON qr.lesson_id = l.id AND qr.user_id = ? "
        "WHERE l.id IN (SELECT lesson_id FROM lesson_completions WHERE user_id = ?) "
        "   OR l.id IN (SELECT lesson_id FROM quiz_results WHERE user_id = ?) "
        "   OR l.id IN (SELECT e2.lesson_id FROM exercise_attempts ea2 "
        "              JOIN exercises e2 ON e2.id = ea2.exercise_id "
        "              WHERE ea2.user_id = ?) "
        "GROUP BY l.id HAVING quiz_avg >= 0 OR ex_total > 0",
        (user_id, user_id, user_id, user_id, user_id, user_id),
    )
    strengths, weaknesses = [], []
    for r in rows:
        score = r["quiz_avg"] if r["quiz_avg"] >= 0 else None
        ex_acc = (100.0 * r["ex_pass"] / r["ex_total"]) if r["ex_total"] else None
        marks = [s for s in (score, ex_acc) if s is not None]
        if not marks:
            continue
        avg = sum(marks) / len(marks)
        entry = {
            "lesson_id": r["id"], "title": r["title"], "slug": r["slug"],
            "score": round(avg, 0),
        }
        if avg >= 80:
            strengths.append(entry)
        elif avg < 60:
            weaknesses.append(entry)
    strengths.sort(key=lambda e: -e["score"])
    weaknesses.sort(key=lambda e: e["score"])
    return {"strengths": strengths[:5], "weaknesses": weaknesses[:5]}


def achievements(user_id: int) -> list[dict]:
    o = overall_progress(user_id)
    streak = compute_streak(user_id)
    lessons = o["lessons_completed"]
    quizzes_perfect = db.query_one(
        "SELECT COUNT(*) AS n FROM quiz_results "
        "WHERE user_id = ? AND score = total AND total > 0", (user_id,)
    )["n"]
    runs = db.query_one(
        "SELECT COUNT(*) AS n FROM activity_log "
        "WHERE user_id = ? AND kind = 'playground_run'", (user_id,)
    )["n"]
    chats = db.query_one(
        "SELECT COUNT(*) AS n FROM messages WHERE role = 'user' "
        "AND conversation_id IN "
        "(SELECT id FROM conversations WHERE user_id = ?)", (user_id,)
    )["n"]

    defs = [
        ("first_lesson", "First Steps", "Complete your first lesson",
         lessons >= 1, lessons >= 1),
        ("five_lessons", "Getting Serious", "Complete 5 lessons",
         lessons >= 5, min(lessons / 5, 1)),
        ("half_python", "Halfway There", "Complete 11 Python lessons",
         lessons >= 11, min(lessons / 11, 1)),
        ("python_graduate", "Python Graduate", "Complete every Python lesson",
         lessons >= o["lessons_total"] and o["lessons_total"] > 0,
         min(lessons / max(o["lessons_total"], 1), 1)),
        ("quiz_ace", "Quiz Ace", "Score 100% on any quiz",
         quizzes_perfect >= 1, min(quizzes_perfect, 1)),
        ("exercise_solver", "Exercise Solver", "Pass 10 exercises",
         o["exercises_passed"] >= 10, min(o["exercises_passed"] / 10, 1)),
        ("streak_3", "Consistent", "3-day learning streak",
         streak["best"] >= 3, min(streak["best"] / 3, 1)),
        ("streak_7", "Unstoppable", "7-day learning streak",
         streak["best"] >= 7, min(streak["best"] / 7, 1)),
        ("project_builder", "Project Builder", "Finish a guided project",
         o["projects_completed"] >= 1, min(o["projects_completed"], 1)),
        ("explorer", "Code Explorer", "Run code in the playground 5 times",
         runs >= 5, min(runs / 5, 1)),
        ("curious", "Curious Mind", "Ask the tutor 5 questions",
         chats >= 5, min(chats / 5, 1)),
    ]
    return [
        {"id": i, "label": label, "description": desc, "earned": bool(earned),
         "progress": round(min(float(p), 1.0), 2)}
        for i, label, desc, earned, p in defs
    ]


def dashboard(user_id: int) -> dict:
    recent = db.query(
        "SELECT * FROM activity_log WHERE user_id = ? "
        "ORDER BY id DESC LIMIT 12", (user_id,)
    )
    streak = compute_streak(user_id)
    rec = recommended_lesson(user_id)
    return {
        "overall": overall_progress(user_id),
        "per_course": per_course_progress(user_id),
        "streak": streak,
        "recommended_lesson": rec,
        "topics": strengths_weaknesses(user_id),
        "achievements": achievements(user_id),
        "recent_activity": [
            {"id": r["id"], "kind": r["kind"], "ref": r["ref"],
             "detail": r["detail"], "created_at": r["created_at"]}
            for r in recent
        ],
    }


def reset_progress(user_id: int) -> None:
    """Erase all learning data for the user. Settings and chats are kept."""
    for table in ("lesson_completions", "quiz_results", "exercise_attempts",
                  "project_progress", "activity_log", "hint_reveals"):
        db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
