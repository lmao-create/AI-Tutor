"""Progress computation tests: streaks, dashboard, achievements, reset."""
import datetime as dt


def test_empty_dashboard_is_clean(seeded, fresh_db):
    from app.services.progress import dashboard
    d = dashboard(1)
    assert d["overall"]["lessons_completed"] == 0
    assert d["overall"]["lessons_total"] == 22
    assert d["overall"]["percent"] == 0.0
    assert d["streak"]["current"] == 0
    assert d["recommended_lesson"]["slug"] == "what-is-programming"
    assert d["topics"] == {"strengths": [], "weaknesses": []}
    earned = [a["id"] for a in d["achievements"] if a["earned"]]
    assert earned == []


def test_streak_calculation(fresh_db):
    from app.services.progress import compute_streak, ensure_user
    ensure_user()
    today = dt.date.today()
    days = [(today - dt.timedelta(days=n)).isoformat() for n in range(3)]
    for d in days:
        fresh_db.execute(
            "INSERT INTO activity_log (user_id, kind, ref, created_at) "
            "VALUES (1, 'x', '', ?)", (d,))
    s = compute_streak(1)
    assert s["current"] == 3
    assert s["best"] == 3
    assert s["active_today"] is True


def test_streak_broken_by_gap(fresh_db):
    from app.services.progress import compute_streak, ensure_user
    ensure_user()
    today = dt.date.today()
    for n in (0, 1, 3, 4):  # gap at day 2
        fresh_db.execute(
            "INSERT INTO activity_log (user_id, kind, ref, created_at) "
            "VALUES (1, 'x', '', ?)",
            ((today - dt.timedelta(days=n)).isoformat(),))
    s = compute_streak(1)
    assert s["current"] == 2
    assert s["best"] == 2


def test_achievements_earned_from_real_data(seeded, fresh_db, client):
    # complete 1 lesson + pass 1 exercise -> two achievements
    client.post("/api/lessons/1/complete", json={"time_spent_seconds": 30})
    client.post("/api/exercises/1/submit", json={"choice": 1})  # correct mcq
    r = client.get("/api/progress")
    d = r.json()
    earned = {a["id"] for a in d["achievements"] if a["earned"]}
    assert "first_lesson" in earned
    assert "exercise_solver" not in earned  # 1 < 10
    assert d["overall"]["lessons_completed"] == 1
    assert d["overall"]["percent"] == 4.5


def test_recommended_next_lesson_follows_order(client):
    client.post("/api/lessons/1/complete", json={"time_spent_seconds": 10})
    r = client.get("/api/progress")
    rec = r.json()["recommended_lesson"]
    assert rec["slug"] == "installing-python"


def test_strengths_and_weaknesses_from_attempts(client):
    # Pass the mcq exercise (1) -> lesson 1 strength via exercise accuracy
    client.post("/api/exercises/1/submit", json={"choice": 2})
    # Resolve the loops exercise by slug (ids shift if content is re-seeded)
    all_ex = client.get("/api/exercises?course=python").json()["exercises"]
    loops_id = next(e["id"] for e in all_ex if e["slug"] == "loops-ex")
    # Fail the loops exercise repeatedly -> weakness
    for _ in range(3):
        client.post(f"/api/exercises/{loops_id}/submit",
                    json={"code": "print('wrong')"})
    r = client.get("/api/progress")
    topics = r.json()["topics"]
    assert any(t["slug"] == "what-is-programming"
               for t in topics["strengths"])
    assert any(t["slug"] == "loops" for t in topics["weaknesses"])


def test_reset_progress_requires_confirmation(client):
    client.post("/api/lessons/1/complete", json={"time_spent_seconds": 10})
    r = client.post("/api/progress/reset", json={"confirm": False})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "confirm_required"
    # data still there
    assert client.get("/api/progress").json()["overall"]["lessons_completed"] == 1


def test_reset_progress_wipes_learning_data(client):
    client.post("/api/lessons/1/complete", json={"time_spent_seconds": 10})
    client.post("/api/lessons/3/quiz", json={"answers": {"q1": 1, "q2": 1}})
    client.post("/api/exercises/1/submit", json={"choice": 1})
    client.post("/api/projects/number-guessing-game/milestones/0/complete")

    r = client.post("/api/progress/reset", json={"confirm": True})
    assert r.status_code == 200
    d = client.get("/api/progress").json()
    assert d["overall"]["lessons_completed"] == 0
    assert d["overall"]["quizzes_taken"] == 0
    assert d["overall"]["exercises_passed"] == 0
    assert d["overall"]["projects_completed"] == 0
    assert d["recent_activity"] == []
    earned = [a for a in d["achievements"] if a["earned"]]
    assert earned == []


def test_recent_activity_log(client):
    client.post("/api/lessons/1/complete", json={"time_spent_seconds": 5})
    client.post("/api/execution/run", json={"language": "python",
                                            "code": "print('hi')"})
    d = client.get("/api/progress").json()
    kinds = {a["kind"] for a in d["recent_activity"]}
    assert "lesson_completed" in kinds
    assert "playground_run" in kinds
