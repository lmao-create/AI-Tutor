"""Guided projects: listing, detail and milestone completion."""
import json

from fastapi import APIRouter, status

from .. import db
from ..errors import AppError
from ..services.progress import ensure_user, log_activity

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects():
    user = ensure_user()
    rows = db.query("SELECT * FROM projects ORDER BY order_index")
    out = []
    for p in rows:
        milestones = p["milestones"] or []
        done = db.query_one(
            "SELECT COUNT(DISTINCT milestone_index) AS n FROM project_progress "
            "WHERE user_id = ? AND project_id = ?",
            (user["id"], p["id"]),
        )["n"]
        out.append({
            "id": p["id"],
            "slug": p["slug"],
            "title": p["title"],
            "description": p["description"],
            "difficulty": p["difficulty"],
            "language": p["language"],
            "skills": p["skills"],
            "milestones_total": len(milestones),
            "milestones_completed": done,
        })
    return {"projects": out}


@router.get("/{slug}")
def project_detail(slug: str):
    user = ensure_user()
    p = db.query_one("SELECT * FROM projects WHERE slug = ?", (slug,))
    if p is None:
        raise AppError(404, "not_found", "Project not found.")
    done_rows = db.query(
        "SELECT milestone_index FROM project_progress "
        "WHERE user_id = ? AND project_id = ?",
        (user["id"], p["id"]),
    )
    done = {r["milestone_index"] for r in done_rows}
    return {
        "id": p["id"],
        "slug": p["slug"],
        "title": p["title"],
        "description": p["description"],
        "difficulty": p["difficulty"],
        "language": p["language"],
        "skills": p["skills"],
        "requirements": p["requirements"],
        "milestones": p["milestones"] or [],
        "starter_code": p["starter_code"],
        "testing_instructions": p["testing_instructions"],
        "challenges": p["challenges"],
        "completed_milestones": sorted(done),
    }


@router.post("/{slug}/milestones/{index}/complete", status_code=201)
def complete_milestone(slug: str, index: int):
    user = ensure_user()
    p = db.query_one("SELECT * FROM projects WHERE slug = ?", (slug,))
    if p is None:
        raise AppError(404, "not_found", "Project not found.")
    milestones = p["milestones"] or []
    if not (0 <= index < len(milestones)):
        raise AppError(400, "bad_milestone", "No such milestone in this project.")
    db.execute(
        "INSERT OR IGNORE INTO project_progress (user_id, project_id, "
        "milestone_index) VALUES (?, ?, ?)",
        (user["id"], p["id"], index),
    )
    log_activity(user["id"], "milestone_completed", p["slug"],
                 {"index": index, "title": milestones[index].get("title", "")})
    done = db.query(
        "SELECT milestone_index FROM project_progress "
        "WHERE user_id = ? AND project_id = ?",
        (user["id"], p["id"]),
    )
    return {"milestones_completed": sorted(r["milestone_index"] for r in done)}


@router.delete("/{slug}/milestones/{index}/complete", status_code=204)
def uncomplete_milestone(slug: str, index: int):
    user = ensure_user()
    p = db.query_one("SELECT id FROM projects WHERE slug = ?", (slug,))
    if p is None:
        raise AppError(404, "not_found", "Project not found.")
    db.execute(
        "DELETE FROM project_progress WHERE user_id = ? AND project_id = ? "
        "AND milestone_index = ?",
        (user["id"], p["id"], index),
    )
    return None
