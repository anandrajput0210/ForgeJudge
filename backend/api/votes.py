from datetime import datetime, timezone
from time import monotonic
from backend.models.voting import VotingConfig
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.models.comment import Comment
from backend.api.auth import get_current_user
from backend.core.database import get_db
from backend.models.event import Event
from backend.models.project import Project
from backend.models.team import Team
from backend.models.user import User
from backend.models.vote import Vote
from backend.services.audit import record_audit_event


router = APIRouter(
    prefix="/api/votes",
    tags=["Votes"],
)


_vote_attempts: dict[tuple[int, int], list[float]] = {}

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 10


def _check_rate_limit(user_id: int, event_id: int):
    key = (user_id, event_id)
    now = monotonic()

    recent_attempts = [
        timestamp
        for timestamp in _vote_attempts.get(key, [])
        if now - timestamp < RATE_LIMIT_WINDOW_SECONDS
    ]

    if len(recent_attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many voting attempts. Please try again later.",
        )

    recent_attempts.append(now)
    _vote_attempts[key] = recent_attempts


@router.post(
    "/{event_id}/{project_id}",
    status_code=status.HTTP_201_CREATED,
)
def cast_vote(
    event_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can vote",
        )

    _check_rate_limit(current_user.id, event_id)

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

    now = datetime.now(timezone.utc)

    voting_config = (
    db.query(VotingConfig)
    .filter(VotingConfig.event_id == event_id)
    .first()
)

    if voting_config is not None:
        start_time = voting_config.start_time
        end_time = voting_config.end_time

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        if not voting_config.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voting is disabled",
        )

    else:
        start_time = event.start_time
        end_time = event.end_time

    if now < start_time or now > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voting is not currently open",
    )
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.status == "submitted",
        )
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submitted project not found",
        )

    team = (
        db.query(Team)
        .filter(
            Team.id == project.team_id,
            Team.event_id == event_id,
        )
        .first()
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project does not belong to this event",
        )

    if current_user in team.members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot vote for your own team",
        )

    existing_vote = (
        db.query(Vote)
        .filter(
            Vote.event_id == event_id,
            Vote.voter_id == current_user.id,
        )
        .first()
    )

    if existing_vote is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already voted in this event",
        )

    vote = Vote(
        event_id=event_id,
        project_id=project_id,
        voter_id=current_user.id,
    )

    db.add(vote)

    try:
        db.flush()

        record_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="VOTE_CREATED",
            resource_type="vote",
            resource_id=vote.id,
            new_value={
                "event_id": event_id,
                "project_id": project_id,
            },
        )

        db.commit()
        db.refresh(vote)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already voted in this event",
        )

    return {
        "vote_id": vote.id,
        "event_id": vote.event_id,
        "project_id": vote.project_id,
        "voter_id": vote.voter_id,
        "status": "saved",
    }


@router.get("/{event_id}/results")
def get_vote_results(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can view voting results",
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

    now = datetime.now(timezone.utc)

    voting_config = (
        db.query(VotingConfig)
        .filter(VotingConfig.event_id == event_id)
        .first()
)

    if voting_config is not None:
        end_time = voting_config.end_time

        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        if now <= end_time:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voting results are hidden while voting is open",
        )
    else:
        if now <= event.end_time:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voting results are hidden while voting is open",
        )

    results = {}

    votes = (
        db.query(Vote)
        .filter(Vote.event_id == event_id)
        .all()
    )

    for vote in votes:
        results[vote.project_id] = results.get(vote.project_id, 0) + 1

    return {
        "event_id": event_id,
        "results": [
            {
                "project_id": project_id,
                "vote_count": vote_count,
            }
            for project_id, vote_count in sorted(
                results.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
    }

@router.get("/event/{event_id}/projects")
def get_randomized_voting_projects(
    event_id: int,
    db: Session = Depends(get_db),
):
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

    projects = (
        db.query(Project)
        .join(Team, Project.team_id == Team.id)
        .filter(
            Team.event_id == event_id,
            Project.status == "submitted",
        )
        .all()
    )

    import random

    random.shuffle(projects)

    return [
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "track_id": project.track_id,
            "repository_url": project.repository_url,
            "demo_url": project.demo_url,
            "submitted_at": project.submitted_at,
        }
        for project in projects
    ]

class CommentCreate(BaseModel):
    content: str


@router.post(
    "/{event_id}/{project_id}/comments",
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    event_id: int,
    project_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can comment",
        )

    content = comment_data.content.strip()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment cannot be empty",
        )

    if len(content) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment cannot exceed 1000 characters",
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

    project = (
        db.query(Project)
        .join(Team, Project.team_id == Team.id)
        .filter(
            Project.id == project_id,
            Project.status == "submitted",
            Team.event_id == event_id,
        )
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submitted project not found",
        )

    comment = Comment(
        event_id=event_id,
        project_id=project_id,
        author_id=current_user.id,
        content=content,
    )

    db.add(comment)
    db.flush()

    record_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="COMMENT_CREATED",
        resource_type="comment",
        resource_id=comment.id,
        new_value={
            "event_id": event_id,
            "project_id": project_id,
        },
    )

    db.commit()
    db.refresh(comment)

    return {
        "comment_id": comment.id,
        "event_id": comment.event_id,
        "project_id": comment.project_id,
        "author_id": comment.author_id,
        "content": comment.content,
        "created_at": comment.created_at,
        "status": "saved",
    }


@router.get("/{event_id}/{project_id}/comments")
def get_project_comments(
    event_id: int,
    project_id: int,
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .join(Team, Project.team_id == Team.id)
        .filter(
            Project.id == project_id,
            Project.status == "submitted",
            Team.event_id == event_id,
        )
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submitted project not found",
        )

    comments = (
        db.query(Comment)
        .filter(
            Comment.event_id == event_id,
            Comment.project_id == project_id,
        )
        .order_by(Comment.created_at.asc())
        .all()
    )

    return [
        {
            "comment_id": comment.id,
            "author_id": comment.author_id,
            "content": comment.content,
            "created_at": comment.created_at,
        }
        for comment in comments
    ]

class VotingConfigCreate(BaseModel):
    enabled: bool = True
    start_time: datetime
    end_time: datetime


@router.put("/event/{event_id}/config")
def update_voting_config(
    event_id: int,
    config_data: VotingConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can configure voting",
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

    if config_data.end_time <= config_data.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voting end time must be after start time",
        )

    config = (
        db.query(VotingConfig)
        .filter(VotingConfig.event_id == event_id)
        .first()
    )

    if config is None:
        config = VotingConfig(
            event_id=event_id,
            enabled=config_data.enabled,
            start_time=config_data.start_time,
            end_time=config_data.end_time,
        )
        db.add(config)
    else:
        config.enabled = config_data.enabled
        config.start_time = config_data.start_time
        config.end_time = config_data.end_time

    record_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="VOTING_CONFIG_UPDATED",
        resource_type="voting_config",
        resource_id=config.id,
        new_value={
            "event_id": event_id,
            "enabled": config_data.enabled,
            "start_time": config_data.start_time.isoformat(),
            "end_time": config_data.end_time.isoformat(),
        },
    )

    db.commit()
    db.refresh(config)

    return {
        "id": config.id,
        "event_id": config.event_id,
        "enabled": config.enabled,
        "start_time": config.start_time,
        "end_time": config.end_time,
    }


@router.get("/event/{event_id}/config")
def get_voting_config(
    event_id: int,
    db: Session = Depends(get_db),
):
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

    config = (
        db.query(VotingConfig)
        .filter(VotingConfig.event_id == event_id)
        .first()
    )

    if config is None:
        return {
            "event_id": event_id,
            "enabled": False,
            "start_time": None,
            "end_time": None,
            "configured": False,
        }

    return {
        "id": config.id,
        "event_id": config.event_id,
        "enabled": config.enabled,
        "start_time": config.start_time,
        "end_time": config.end_time,
        "configured": True,
    }