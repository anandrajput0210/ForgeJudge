from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.core.database import get_db
from backend.models.event import Event, Track
from backend.models.project import Project
from backend.models.team import Team
from backend.models.user import User
from backend.services.audit import record_audit_event

router = APIRouter(
    prefix="/api/projects",
    tags=["Projects"],
)


class ProjectCreate(BaseModel):
    team_id: int
    track_id: int
    name: str
    description: str | None = None
    repository_url: str | None = None
    demo_url: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    demo_url: str | None = None
    track_id: int | None = None


def get_project_or_404(
    project_id: int,
    db: Session,
):
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

    return project


def ensure_team_member(
    project: Project,
    current_user: User,
    db: Session,
):
    team = (
        db.query(Team)
        .filter(Team.id == project.team_id)
        .first()
    )

    if team is None or current_user not in team.members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this project's team",
        )

    return team


def ensure_before_deadline(
    event: Event,
):
    now = datetime.now(timezone.utc)

    end_time = event.end_time

    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    if now > end_time:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The event submission deadline has passed",
        )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can create projects",
        )

    team = (
        db.query(Team)
        .filter(Team.id == project_data.team_id)
        .first()
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if current_user not in team.members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this team",
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

    ensure_before_deadline(event)

    track = (
        db.query(Track)
        .filter(
            Track.id == project_data.track_id,
            Track.event_id == event.id,
        )
        .first()
    )

    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track does not belong to this event",
        )

    project = Project(
        team_id=team.id,
        track_id=track.id,
        name=project_data.name,
        description=project_data.description,
        repository_url=project_data.repository_url,
        demo_url=project_data.demo_url,
        status="draft",
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return {
        "id": project.id,
        "team_id": project.team_id,
        "track_id": project.track_id,
        "name": project.name,
        "description": project.description,
        "repository_url": project.repository_url,
        "demo_url": project.demo_url,
        "status": project.status,
        "submitted_at": project.submitted_at,
    }


@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, db)

    return {
        "id": project.id,
        "team_id": project.team_id,
        "track_id": project.track_id,
        "name": project.name,
        "description": project.description,
        "repository_url": project.repository_url,
        "demo_url": project.demo_url,
        "status": project.status,
        "submitted_at": project.submitted_at,
    }


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can edit projects",
        )

    project = get_project_or_404(project_id, db)

    if project.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submitted projects cannot be edited",
        )

    team = ensure_team_member(
        project,
        current_user,
        db,
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

    ensure_before_deadline(event)

    if project_data.track_id is not None:
        track = (
            db.query(Track)
            .filter(
                Track.id == project_data.track_id,
                Track.event_id == event.id,
            )
            .first()
        )

        if track is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track does not belong to this event",
            )

        project.track_id = track.id

    if project_data.name is not None:
        project.name = project_data.name

    if project_data.description is not None:
        project.description = project_data.description

    if project_data.repository_url is not None:
        project.repository_url = project_data.repository_url

    if project_data.demo_url is not None:
        project.demo_url = project_data.demo_url

    db.commit()
    db.refresh(project)

    return {
        "id": project.id,
        "team_id": project.team_id,
        "track_id": project.track_id,
        "name": project.name,
        "description": project.description,
        "repository_url": project.repository_url,
        "demo_url": project.demo_url,
        "status": project.status,
        "submitted_at": project.submitted_at,
    }


@router.post("/{project_id}/submit")
def submit_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can submit projects",
        )

    project = get_project_or_404(project_id, db)

    if project.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project has already been submitted",
        )

    team = ensure_team_member(
        project,
        current_user,
        db,
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

    ensure_before_deadline(event)

    project.status = "submitted"
    project.submitted_at = datetime.now(timezone.utc)

    record_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="SUBMISSION_SUBMITTED",
        resource_type="project",
        resource_id=project.id,
        old_value={
            "status": "draft",
        },
        new_value={
            "status": "submitted",
            "submitted_at": project.submitted_at.isoformat(),
        },
    )

    db.commit()
    db.refresh(project)

    return {
        "message": "Project submitted successfully",
        "project_id": project.id,
        "status": project.status,
        "submitted_at": project.submitted_at,
    }
@router.get("/")
def public_gallery(
    search: str | None = None,
    track_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(Project)
        .filter(Project.status == "submitted")
    )

    if search:
        query = query.filter(
            Project.name.ilike(f"%{search}%")
        )

    if track_id is not None:
        query = query.filter(
            Project.track_id == track_id
        )

    projects = (
        query
        .order_by(Project.submitted_at.desc())
        .all()
    )

    return [
        {
            "id": project.id,
            "team_id": project.team_id,
            "track_id": project.track_id,
            "name": project.name,
            "description": project.description,
            "repository_url": project.repository_url,
            "demo_url": project.demo_url,
            "submitted_at": project.submitted_at,
        }
        for project in projects
    ]