"""Course, lesson, quiz and exercise API tests - including leak checks."""
import json


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["db_ok"] is True
    assert data["demo_mode"] is True  # no provider configured in tests
    assert data["provider_configured"] is False


def test_courses_listed_with_progress(client):
    r = client.get("/api/courses")
    assert r.status_code == 200
    courses = r.json()["courses"]
    assert len(courses) == 10
    python = next(c for c in courses if c["slug"] == "python")
    assert python["status"] == "complete"
    assert python["lessons_total"] == 22
    assert python["lessons_completed"] == 0
    # Planned courses are labelled honestly.
    js = next(c for c in courses if c["slug"] == "javascript")
    assert js["status"] == "planned"
    assert js["lessons_total"] == 0


def test_lesson_detail_sanitizes_quiz(client):
    r = client.get("/api/courses/python/lessons/print-and-comments")
    assert r.status_code == 200
    lesson = r.json()
    assert lesson["title"] == "print() and Comments"
    assert len(lesson["sections"]) >= 2
    # quiz questions carry only id/question/options - answers are graded
    # server-side and revealed only after submission
    for q in lesson["quiz"]:
        assert set(q.keys()) == {"id", "question", "options"}
        assert len(q["options"]) >= 3
    # the example's own explanation field is legitimate content
    assert "explanation" in lesson["example"]
    # the attached exercise is sanitized
    assert lesson["exercise"] is not None
    assert "answer" not in lesson["exercise"]
    assert "hints" not in lesson["exercise"]
    assert "test_spec" not in lesson["exercise"]
    assert lesson["exercise"]["hint_count"] >= 1


def test_lesson_not_found(client):
    r = client.get("/api/courses/python/lessons/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_exercise_list_never_leaks_answers(client):
    r = client.get("/api/exercises?course=python")
    assert r.status_code == 200
    body = r.text
    for secret in ('"answer"', '"hints"', '"solution"', '"test_spec"'):
        assert secret not in body, f"{secret} leaked in exercise list"
    exs = r.json()["exercises"]
    assert len(exs) == 34
    # every exercise has a hint_count field for the UI
    assert all("hint_count" in e for e in exs)


def test_quiz_grading_correct_and_best_score(client):
    # lesson 3 = print-and-comments; q1 answer 1, q2 answer 1
    r = client.post("/api/lessons/3/quiz", json={"answers": {"q1": 1, "q2": 1}})
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 2 and data["total"] == 2
    assert data["best"] == 100
    assert all(q["correct"] for q in data["per_question"])
    # explanations revealed after submission
    assert all("explanation" in q for q in data["per_question"])

    # A wrong attempt after doesn't lower the best score.
    r = client.post("/api/lessons/3/quiz", json={"answers": {"q1": 0, "q2": 0}})
    data = r.json()
    assert data["score"] == 0
    assert data["best"] == 100


def test_lesson_completion_flow(client):
    r = client.post("/api/lessons/3/complete", json={"time_spent_seconds": 120})
    assert r.status_code == 200
    r = client.get("/api/courses/python/lessons/print-and-comments")
    assert r.json()["completed"] is True
    assert r.json()["time_spent_seconds"] == 120

    # duplicate completion accumulates time instead of failing
    client.post("/api/lessons/3/complete", json={"time_spent_seconds": 60})
    r = client.get("/api/courses/python/lessons/print-and-comments")
    assert r.json()["time_spent_seconds"] == 180

    # uncomplete clears it
    r = client.delete("/api/lessons/3/complete")
    assert r.status_code == 204
    r = client.get("/api/courses/python/lessons/print-and-comments")
    assert r.json()["completed"] is False


def test_lesson_completion_bad_payload(client):
    r = client.post("/api/lessons/3/complete", json={"time_spent_seconds": -5})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


def test_lesson_prev_next_navigation(client):
    r = client.get("/api/courses/python/lessons/variables")
    data = r.json()
    assert data["prev_lesson"] == "print-and-comments"
    assert data["next_lesson"] == "user-input"


def test_hint_progression_is_sequential(client):
    # exercise 3 = print-and-comments-ex (write_program, 3 hints)
    for level in (1, 2, 3):
        r = client.post("/api/exercises/3/hint")
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "hint"
        assert data["level"] == level
        assert "content" in data
    # 4th call reveals the solution, 5th refuses
    r = client.post("/api/exercises/3/hint")
    data = r.json()
    assert data["type"] == "solution"
    assert "code" in data and "explanation" in data
    r = client.post("/api/exercises/3/hint")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "all_revealed"


def test_projects_listing_and_milestones(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()["projects"]
    assert len(projects) == 9
    guess = next(p for p in projects if p["slug"] == "number-guessing-game")
    assert guess["milestones_total"] == 4
    assert guess["milestones_completed"] == 0

    r = client.get("/api/projects/number-guessing-game")
    detail = r.json()
    assert len(detail["milestones"]) == 4
    assert all("guidance" in m for m in detail["milestones"])

    # complete milestone 1, then 2, then unmark 1
    r = client.post("/api/projects/number-guessing-game/milestones/1/complete")
    assert r.status_code == 201
    assert r.json()["milestones_completed"] == [1]
    r = client.post("/api/projects/number-guessing-game/milestones/0/complete")
    assert r.json()["milestones_completed"] == [0, 1]
    r = client.delete("/api/projects/number-guessing-game/milestones/0/complete")
    assert r.status_code == 204

    # invalid milestone index
    r = client.post("/api/projects/number-guessing-game/milestones/99/complete")
    assert r.status_code == 400


def test_tutor_modes_endpoint(client):
    r = client.get("/api/tutor/modes")
    assert r.status_code == 200
    modes = r.json()["modes"]
    ids = {m["id"] for m in modes}
    assert ids == {"learn", "practice", "debug", "project", "interview", "explain"}
