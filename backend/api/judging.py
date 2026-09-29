import secrets
import csv
import io
from backend.services.audit import record_audit_event
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.services.assignment import assign_judges
from backend.api.auth import get_current_user
from backend.core.database import get_db
from backend.models.event import Event
from backend.models.project import Project
from backend.models.team import Team
from backend.models.judging import JudgeInvite
from backend.models.user import User
from backend.models.judging import (
    JudgeAssignment,
    JudgeInvite,
    Rubric,
    RubricCriterion,
    Score,
)
from backend.services.normalization import normalize_project_scores

router = APIRouter(
    prefix="/api/judging",
    tags=["Judging"],
)


class JudgeInviteCreate(BaseModel):
    event_id: int
    email: str


@router.post(
    "/invites",
    status_code=status.HTTP_201_CREATED,
)
def create_judge_invite(
    invite_data: JudgeInviteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can invite judges",
        )

    event = (
        db.query(Event)
        .filter(Event.id == invite_data.event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    token = secrets.token_urlsafe(32)

    invite = JudgeInvite(
        event_id=event.id,
        email=invite_data.email,
        token=token,
        created_by=current_user.id,
        status="pending",
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {
        "invite_id": invite.id,
        "event_id": invite.event_id,
        "email": invite.email,
        "token": invite.token,
        "status": invite.status,
    }
class AssignmentRequest(BaseModel):
    event_id: int
    judges_per_project: int = 3
@router.post("/invites/{token}/accept")
def accept_judge_invite(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "judge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only judges can accept judge invites",
        )

    invite = (
        db.query(JudgeInvite)
        .filter(
            JudgeInvite.token == token,
            JudgeInvite.status == "pending",
        )
        .first()
    )

    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or already accepted judge invite",
        )

    if invite.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invite was issued to a different judge",
        )

    invite.accepted_by = current_user.id
    invite.accepted_at = datetime.now(timezone.utc)
    invite.status = "accepted"

    db.commit()
    db.refresh(invite)

    return {
        "message": "Judge invite accepted",
        "invite_id": invite.id,
        "event_id": invite.event_id,
        "judge_id": current_user.id,
        "status": invite.status,
    }

class RubricCriterionCreate(BaseModel):
    name: str
    description: str | None = None
    weight: float
    max_score: float = 100.0


class RubricCreate(BaseModel):
    event_id: int
    name: str
    criteria: list[RubricCriterionCreate]


@router.post(
    "/rubrics",
    status_code=status.HTTP_201_CREATED,
)
def create_rubric(
    rubric_data: RubricCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can create rubrics",
        )

    event = (
        db.query(Event)
        .filter(Event.id == rubric_data.event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    if not rubric_data.criteria:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one rubric criterion is required",
        )

    total_weight = sum(
        criterion.weight
        for criterion in rubric_data.criteria
    )

    if abs(total_weight - 100.0) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rubric criteria weights must total 100",
        )

    for criterion in rubric_data.criteria:
        if criterion.weight <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Criterion weights must be greater than 0",
            )

        if criterion.max_score <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Criterion max_score must be greater than 0",
            )

    rubric = Rubric(
        event_id=event.id,
        name=rubric_data.name,
    )

    db.add(rubric)
    db.flush()

    for criterion_data in rubric_data.criteria:
        criterion = RubricCriterion(
            rubric_id=rubric.id,
            name=criterion_data.name,
            description=criterion_data.description,
            weight=criterion_data.weight,
            max_score=criterion_data.max_score,
        )

        db.add(criterion)

    db.commit()
    db.refresh(rubric)

    return {
        "id": rubric.id,
        "event_id": rubric.event_id,
        "name": rubric.name,
        "criteria": [
            {
                "id": criterion.id,
                "name": criterion.name,
                "description": criterion.description,
                "weight": criterion.weight,
                "max_score": criterion.max_score,
            }
            for criterion in rubric.criteria
        ],
    }
@router.post("/assign")
def run_judge_assignment(
    assignment_data: AssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can assign judges",
        )

    event = (
        db.query(Event)
        .filter(Event.id == assignment_data.event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    if assignment_data.judges_per_project < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="judges_per_project must be at least 1",
        )

    return assign_judges(
    event_id=assignment_data.event_id,
    judges_per_project=assignment_data.judges_per_project,
    db=db,
    actor_user_id=current_user.id,
)

from datetime import datetime, timezone


class CriterionScoreCreate(BaseModel):
    criterion_id: int
    score: float


class EvaluationCreate(BaseModel):
    scores: list[CriterionScoreCreate]


@router.post(
    "/evaluations/{assignment_id}",
)
def submit_evaluation(
    assignment_id: int,
    evaluation_data: EvaluationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "judge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only judges can submit evaluations",
        )

    assignment = (
        db.query(JudgeAssignment)
        .filter(
            JudgeAssignment.id == assignment_id,
            JudgeAssignment.judge_id == current_user.id,
            JudgeAssignment.status == "assigned",
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if not evaluation_data.scores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one criterion score is required",
        )

    assignment_score_ids = set()

    for score_data in evaluation_data.scores:
        criterion = (
            db.query(RubricCriterion)
            .filter(
                RubricCriterion.id == score_data.criterion_id
            )
            .first()
        )

        if criterion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Criterion {score_data.criterion_id} not found"
                ),
            )

        if score_data.score < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Score cannot be negative",
            )

        if score_data.score > criterion.max_score:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Score cannot exceed "
                    f"{criterion.max_score} for "
                    f"criterion {criterion.id}"
                ),
            )

        existing_score = (
            db.query(Score)
            .filter(
                Score.assignment_id == assignment.id,
                Score.criterion_id == criterion.id,
            )
            .first()
        )

        now = datetime.now(timezone.utc)

        if existing_score is None:
            existing_score = Score(
                assignment_id=assignment.id,
                criterion_id=criterion.id,
                score_value=score_data.score,
                scored_at=now,
            )

            db.add(existing_score)
            db.flush()

            record_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="SCORE_CREATED",
                resource_type="score",
                resource_id=existing_score.id,
                new_value={
                    "assignment_id": assignment.id,
                    "criterion_id": criterion.id,
                    "score": score_data.score,
                },
            )

        else:
            old_score = existing_score.score_value

            existing_score.score_value = score_data.score
            existing_score.scored_at = now

            record_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="SCORE_UPDATED",
                resource_type="score",
                resource_id=existing_score.id,
                old_value={
                    "score": old_score,
                },
                new_value={
                    "score": score_data.score,
                },
            )

        assignment_score_ids.add(criterion.id)

    db.commit()

    return {
        "assignment_id": assignment.id,
        "judge_id": current_user.id,
        "scores": [
            {
                "criterion_id": criterion_id,
            }
            for criterion_id in sorted(assignment_score_ids)
        ],
        "status": "saved",
    }

@router.get("/my-assignments")
def get_my_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "judge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only judges can access judge assignments",
        )

    assignments = (
        db.query(JudgeAssignment)
        .filter(
            JudgeAssignment.judge_id == current_user.id,
            JudgeAssignment.status == "assigned",
        )
        .order_by(JudgeAssignment.id.asc())
        .all()
    )

    results = []

    for assignment in assignments:
        scores = (
            db.query(Score)
            .filter(
                Score.assignment_id == assignment.id,
            )
            .order_by(Score.criterion_id.asc())
            .all()
        )

        project = assignment.project

        results.append(
            {
                "assignment_id": assignment.id,
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "track_id": project.track_id,
                },
                "scores": [
                    {
                        "criterion_id": score.criterion_id,
                        "score": score.score_value,
                        "scored_at": score.scored_at,
                    }
                    for score in scores
                ],
            }
        )

    return results

@router.post("/normalize/{project_id}")
def normalize_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can normalize scores",
        )

    project = (
        db.query(Project)
        .filter(Project.id == project_id)
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    team = (
        db.query(Team)
        .filter(Team.id == project.team_id)
        .first()
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project team not found",
        )

    event = (
        db.query(Event)
        .filter(Event.id == team.event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    return normalize_project_scores(
        project_id=project_id,
        db=db,
    )

@router.get("/my-progress")
def get_my_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "judge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only judges can access judging progress",
        )

    assignments = (
        db.query(JudgeAssignment)
        .filter(
            JudgeAssignment.judge_id == current_user.id,
            JudgeAssignment.status == "assigned",
        )
        .order_by(JudgeAssignment.id.asc())
        .all()
    )

    results = []

    for assignment in assignments:
        score_count = (
            db.query(Score)
            .filter(
                Score.assignment_id == assignment.id,
            )
            .count()
        )

        project = assignment.project

        event = (
            db.query(Event)
            .join(Team, Team.event_id == Event.id)
            .filter(
                Team.id == project.team_id
            )
            .first()
        )

        required_scores = 0

        if event is not None:
            rubric = (
                db.query(Rubric)
                .filter(
                    Rubric.event_id == event.id
                )
                .first()
            )

            if rubric is not None:
                required_scores = len(
                    rubric.criteria
                )

        if score_count == 0:
            status_value = "not_started"
        elif (
            required_scores > 0
            and score_count >= required_scores
        ):
            status_value = "completed"
        else:
            status_value = "in_progress"
        results.append(
            {
                "assignment_id": assignment.id,
                "project_id": assignment.project_id,
                "score_count": score_count,
                "status": status_value,
            }
        )

    total = len(results)
    completed = sum(
        1
        for item in results
        if item["status"] == "completed"
    )

    return {
        "judge_id": current_user.id,
        "total_assignments": total,
        "completed_assignments": completed,
        "progress_percent": (
            round((completed / total) * 100, 2)
            if total
            else 0.0
        ),
        "assignments": results,
    }

@router.get("/assignments/{assignment_id}")
def get_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "judge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only judges can access assignments",
        )

    assignment = (
        db.query(JudgeAssignment)
        .filter(
            JudgeAssignment.id == assignment_id,
            JudgeAssignment.status == "assigned",
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if assignment.judge_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this assignment",
        )

    scores = (
        db.query(Score)
        .filter(
            Score.assignment_id == assignment.id,
        )
        .order_by(Score.criterion_id.asc())
        .all()
    )

    return {
        "assignment_id": assignment.id,
        "project_id": assignment.project_id,
        "judge_id": assignment.judge_id,
        "scores": [
            {
                "criterion_id": score.criterion_id,
                "score": score.score_value,
                "scored_at": score.scored_at,
            }
            for score in scores
        ],
    }

@router.get("/export.csv")
def export_judging_csv(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can export judging data",
        )

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    assignments = (
        db.query(JudgeAssignment)
        .join(
            Project,
            Project.id == JudgeAssignment.project_id,
        )
        .join(
            Team,
            Team.id == Project.team_id,
        )
        .filter(
            Team.event_id == event_id,
        )
        .order_by(
            Project.id.asc(),
            JudgeAssignment.id.asc(),
        )
        .all()
    )

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow(
        [
            "assignment_id",
            "project_id",
            "project_name",
            "judge_id",
            "criterion_id",
            "score",
            "scored_at",
        ]
    )

    for assignment in assignments:
        scores = (
            db.query(Score)
            .filter(
                Score.assignment_id == assignment.id,
            )
            .order_by(Score.criterion_id.asc())
            .all()
        )

        if not scores:
            writer.writerow(
                [
                    assignment.id,
                    assignment.project_id,
                    assignment.project.name,
                    assignment.judge_id,
                    "",
                    "",
                    "",
                ]
            )
            continue

        for score in scores:
            writer.writerow(
                [
                    assignment.id,
                    assignment.project_id,
                    assignment.project.name,
                    assignment.judge_id,
                    score.criterion_id,
                    score.score_value,
                    score.scored_at.isoformat(),
                ]
            )

    from fastapi.responses import Response

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="judging-event-{event_id}.csv"'
            )
        },
    )

@router.get("/progress")
def get_event_judging_progress(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can view judging progress",
        )

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    assignments = (
        db.query(JudgeAssignment)
        .join(Project, Project.id == JudgeAssignment.project_id)
        .join(Team, Team.id == Project.team_id)
        .filter(
            Team.event_id == event_id,
            JudgeAssignment.status == "assigned",
        )
        .order_by(
            JudgeAssignment.judge_id.asc(),
            JudgeAssignment.project_id.asc(),
        )
        .all()
    )

    judge_progress = {}

    for assignment in assignments:
        judge_id = assignment.judge_id

        if judge_id not in judge_progress:
            judge_progress[judge_id] = {
                "judge_id": judge_id,
                "total_assignments": 0,
                "completed_assignments": 0,
                "in_progress_assignments": 0,
                "not_started_assignments": 0,
            }

        score_count = (
            db.query(Score)
            .filter(
                Score.assignment_id == assignment.id,
            )
            .count()
        )

        rubric = (
            db.query(Rubric)
            .filter(
                Rubric.event_id == event_id,
            )
            .first()
        )

        required_scores = (
            len(rubric.criteria)
            if rubric is not None
            else 0
        )

        if score_count == 0:
            assignment_status = "not_started"
        elif (
            required_scores > 0
            and score_count >= required_scores
        ):
            assignment_status = "completed"
        else:
            assignment_status = "in_progress"

        judge_progress[judge_id]["total_assignments"] += 1

        if assignment_status == "completed":
            judge_progress[judge_id]["completed_assignments"] += 1
        elif assignment_status == "in_progress":
            judge_progress[judge_id]["in_progress_assignments"] += 1
        else:
            judge_progress[judge_id]["not_started_assignments"] += 1

    results = []

    for progress in judge_progress.values():
        total = progress["total_assignments"]
        completed = progress["completed_assignments"]

        progress["progress_percent"] = (
            round((completed / total) * 100, 2)
            if total
            else 0.0
        )

        results.append(progress)

    return {
        "event_id": event_id,
        "judges": results,
    }

@router.get("/leaderboard")
def get_leaderboard(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can view the judging leaderboard",
        )

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    projects = (
        db.query(Project)
        .join(
            Team,
            Team.id == Project.team_id,
        )
        .filter(
            Team.event_id == event_id,
            Project.status == "submitted",
        )
        .order_by(Project.id.asc())
        .all()
    )

    leaderboard = []

    for project in projects:
        result = normalize_project_scores(
            project_id=project.id,
            db=db,
        )

        leaderboard.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "track_id": project.track_id,
                "final_score": result["final_score"],
                "normalization_status": result["status"],
            }
        )

    ranked_projects = [
        item
        for item in leaderboard
        if item["final_score"] is not None
    ]

    pending_projects = [
        item
        for item in leaderboard
        if item["final_score"] is None
    ]

    ranked_projects.sort(
        key=lambda item: (
            -item["final_score"],
            item["project_id"],
        )
    )

    for position, item in enumerate(
        ranked_projects,
        start=1,
    ):
        item["rank"] = position

    for item in pending_projects:
        item["rank"] = None
        item["result_status"] = "pending"

    leaderboard = ranked_projects + pending_projects
    return {
        "event_id": event_id,
        "projects": leaderboard,
    }