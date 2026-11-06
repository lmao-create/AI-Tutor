"""Idempotent seeding of courses, lessons, exercises and projects.

Content lives as JSON files under app/content so the app works fully
offline. Seeding upserts by natural keys (slug, course+lesson slug), so it
is safe to run on every startup and never destroys student progress: rows
are updated in place, never deleted.
"""
import json
from pathlib import Path
from typing import Any, Optional

from . import db

CONTENT_DIR = Path(__file__).parent / "content"


def _load(name: str) -> Any:
    return json.loads((CONTENT_DIR / name).read_text(encoding="utf-8"))


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _upsert_course(c: dict) -> None:
    db.execute(
        """
        INSERT INTO courses (slug, title, description, language, level, status,
                             overview, prerequisites, outline, order_index,
                             content_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            language = excluded.language,
            level = excluded.level,
            status = excluded.status,
            overview = excluded.overview,
            prerequisites = excluded.prerequisites,
            outline = excluded.outline,
            order_index = excluded.order_index,
            content_version = excluded.content_version
        """,
        (
            c["slug"], c["title"], c["description"], c["language"],
            c.get("level", "beginner"), c.get("status", "planned"),
            c.get("overview", ""), _j(c.get("prerequisites", [])),
            _j(c.get("outline", [])), c.get("order_index", 0),
            c.get("content_version", "1"),
        ),
    )


def _upsert_lesson(course_id: int, index: int, l: dict) -> int:
    return db.execute(
        """
        INSERT INTO lessons (course_id, slug, title, order_index, summary,
                              objectives, sections, example, quiz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(course_id, slug) DO UPDATE SET
            title = excluded.title,
            order_index = excluded.order_index,
            summary = excluded.summary,
            objectives = excluded.objectives,
            sections = excluded.sections,
            example = excluded.example,
            quiz = excluded.quiz
        """,
        (
            course_id, l["slug"], l["title"], index, l.get("summary", ""),
            _j(l.get("objectives", [])), _j(l.get("sections", [])),
            _j(l.get("example", {})), _j(l.get("quiz", [])),
        ),
    )


def _upsert_exercise(e: dict) -> None:
    db.execute(
        """
        INSERT INTO exercises (slug, course_id, lesson_id, kind, title, prompt,
                               difficulty, language, starter_code, test_spec,
                               answer, options, hints, solution, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            course_id = excluded.course_id,
            lesson_id = excluded.lesson_id,
            kind = excluded.kind,
            title = excluded.title,
            prompt = excluded.prompt,
            difficulty = excluded.difficulty,
            language = excluded.language,
            starter_code = excluded.starter_code,
            test_spec = excluded.test_spec,
            answer = excluded.answer,
            options = excluded.options,
            hints = excluded.hints,
            solution = excluded.solution,
            order_index = excluded.order_index
        """,
        (
            e["slug"], e.get("course_id"), e.get("lesson_id"), e["kind"],
            e["title"], e["prompt"], e.get("difficulty", 1),
            e.get("language", "python"), e.get("starter_code", ""),
            _j(e["test_spec"]) if e.get("test_spec") else None,
            _j(e["answer"]) if e.get("answer") else None,
            _j(e["options"]) if e.get("options") else None,
            _j(e.get("hints", [])), _j(e.get("solution", {})),
            e.get("order_index", 0),
        ),
    )


def _upsert_project(p: dict) -> None:
    db.execute(
        """
        INSERT INTO projects (slug, title, description, difficulty, language,
                              skills, requirements, milestones, starter_code,
                              testing_instructions, challenges, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            difficulty = excluded.difficulty,
            language = excluded.language,
            skills = excluded.skills,
            requirements = excluded.requirements,
            milestones = excluded.milestones,
            starter_code = excluded.starter_code,
            testing_instructions = excluded.testing_instructions,
            challenges = excluded.challenges,
            order_index = excluded.order_index
        """,
        (
            p["slug"], p["title"], p["description"], p.get("difficulty", 1),
            p.get("language", "python"), _j(p.get("skills", [])),
            _j(p.get("requirements", [])), _j(p.get("milestones", [])),
            p.get("starter_code", ""), p.get("testing_instructions", ""),
            _j(p.get("challenges", [])), p.get("order_index", 0),
        ),
    )


def seed_all() -> dict:
    stats = {"courses": 0, "lessons": 0, "exercises": 0, "projects": 0}

    course_data = _load("courses.json")
    version = course_data.get("content_version", "1")
    for c in course_data["courses"]:
        _upsert_course({**c, "content_version": version})
        stats["courses"] += 1

    for lesson_file in sorted(CONTENT_DIR.glob("python_lessons_*.json")):
        data = _load(lesson_file.name)
        course = db.query_one(
            "SELECT id FROM courses WHERE slug = ?", (data["course_slug"],)
        )
        if course is None:
            continue
        lesson_ids: dict[str, int] = {}
        course_row = db.query_one(
            "SELECT COUNT(*) AS n FROM lessons WHERE course_id = ?",
            (course["id"],),
        )
        order_offset = course_row["n"] if course_row else 0
        for i, lesson in enumerate(data["lessons"]):
            _upsert_lesson(course["id"], order_offset + i, lesson)
            row = db.query_one(
                "SELECT id FROM lessons WHERE course_id = ? AND slug = ?",
                (course["id"], lesson["slug"]),
            )
            if row is not None:
                lesson_ids[lesson["slug"]] = row["id"]
            stats["lessons"] += 1
        for lesson in data["lessons"]:
            ex = lesson.get("exercise")
            if ex and lesson["slug"] in lesson_ids:
                _upsert_exercise({
                    **ex,
                    "slug": f"{lesson['slug']}-ex",
                    "course_id": course["id"],
                    "lesson_id": lesson_ids[lesson["slug"]],
                    "order_index": 0,
                })
                stats["exercises"] += 1

    extra = _load("extra_exercises.json")
    course = db.query_one(
        "SELECT id FROM courses WHERE slug = ?", (extra["course_slug"],)
    )
    if course:
        for i, ex in enumerate(extra["exercises"]):
            _upsert_exercise({**ex, "course_id": course["id"],
                              "lesson_id": None, "order_index": i})
            stats["exercises"] += 1

    project_data = _load("projects.json")
    for i, p in enumerate(project_data["projects"]):
        _upsert_project({**p, "order_index": i})
        stats["projects"] += 1

    db.execute(
        "INSERT INTO app_settings (key, value) VALUES ('content_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (version,),
    )
    return stats
