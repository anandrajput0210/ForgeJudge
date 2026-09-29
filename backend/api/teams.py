import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.core.database import get_db
from backend.models.event import Event
from backend.models.team import Team, TeamInvite
from backend.models.user import User


router = APIRouter(
    prefix="/api/teams",
    tags=["Teams"],
)


class TeamCreate(BaseModel):
    event_id: int
    name: str


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_team(
    team_data: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can create teams",
        )

    event = (
        db.query(Event)
        .filter(Event.id == team_data.event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    team = Team(
        event_id=event.id,
        name=team_data.name,
    )

    team.members.append(current_user)

    db.add(team)
    db.commit()
    db.refresh(team)

    return {
        "id": team.id,
        "event_id": team.event_id,
        "name": team.name,
        "member_ids": [member.id for member in team.members],
    }


@router.get("/{team_id}")
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
):
    team = (
        db.query(Team)
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    return {
        "id": team.id,
        "event_id": team.event_id,
        "name": team.name,
        "member_ids": [member.id for member in team.members],
    }


@router.post("/{team_id}/join")
def join_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can join teams",
        )

    team = (
        db.query(Team)
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if current_user in team.members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this team",
        )

    team.members.append(current_user)
    db.commit()

    return {
        "message": "Joined team successfully",
        "team_id": team.id,
        "user_id": current_user.id,
    }
@router.get("/")
def list_teams(
    event_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {
        "participant",
        "judge",
        "organizer",
        "admin",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view teams",
        )

    query = db.query(Team)

    if event_id is not None:
        query = query.filter(
            Team.event_id == event_id
        )

    teams = (
        query
        .order_by(Team.id.asc())
        .all()
    )

    return [
        {
            "id": team.id,
            "event_id": team.event_id,
            "name": team.name,
            "member_ids": [
                member.id
                for member in team.members
            ],
        }
        for team in teams
    ]
@router.post("/{team_id}/invites")
def create_team_invite(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can create team invites",
        )

    team = (
        db.query(Team)
        .filter(Team.id == team_id)
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

    if len(team.members) >= 4:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Team already has the maximum of 4 members",
        )

    token = secrets.token_urlsafe(32)

    invite = TeamInvite(
        team_id=team.id,
        token=token,
        created_by=current_user.id,
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {
        "invite_id": invite.id,
        "team_id": team.id,
        "token": invite.token,
    }


@router.post("/invites/{token}/accept")
def accept_team_invite(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "participant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can accept team invites",
        )

    invite = (
        db.query(TeamInvite)
        .filter(TeamInvite.token == token)
        .first()
    )

    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid team invite",
        )

    team = (
        db.query(Team)
        .filter(Team.id == invite.team_id)
        .first()
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if current_user in team.members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this team",
        )

    if len(team.members) >= 4:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Team already has the maximum of 4 members",
        )

    team.members.append(current_user)
    db.commit()

    return {
        "message": "Team invite accepted",
        "team_id": team.id,
        "user_id": current_user.id,
    }