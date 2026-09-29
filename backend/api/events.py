from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.core.database import get_db
from backend.models.event import Event, Prize, Track
from backend.models.user import User


router = APIRouter(
    prefix="/api/events",
    tags=["Events"],
)


class EventCreate(BaseModel):
    name: str
    description: str | None = None
    start_time: datetime
    end_time: datetime


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_event(
    event_data: EventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can create events",
        )

    if event_data.end_time <= event_data.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event end time must be after start time",
        )

    event = Event(
        name=event_data.name,
        description=event_data.description,
        owner_id=current_user.id,
        start_time=event_data.start_time,
        end_time=event_data.end_time,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "owner_id": event.owner_id,
        "start_time": event.start_time,
        "end_time": event.end_time,
    }


@router.get("/")
def list_events(
    db: Session = Depends(get_db),
):
    events = (
        db.query(Event)
        .order_by(Event.start_time.asc())
        .all()
    )

    return [
        {
            "id": event.id,
            "name": event.name,
            "description": event.description,
            "owner_id": event.owner_id,
            "start_time": event.start_time,
            "end_time": event.end_time,
        }
        for event in events
    ]


@router.get("/{event_id}")
def get_event(
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

    return {
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "owner_id": event.owner_id,
        "start_time": event.start_time,
        "end_time": event.end_time,
    }

class TrackCreate(BaseModel):
    name: str
    description: str | None = None


class PrizeCreate(BaseModel):
    name: str
    amount: int | None = None


@router.post("/{event_id}/tracks", status_code=status.HTTP_201_CREATED)
def create_track(
    event_id: int,
    track_data: TrackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can manage tracks",
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

    track = Track(
        event_id=event.id,
        name=track_data.name,
        description=track_data.description,
    )

    db.add(track)
    db.commit()
    db.refresh(track)

    return {
        "id": track.id,
        "event_id": track.event_id,
        "name": track.name,
        "description": track.description,
    }


@router.get("/{event_id}/tracks")
def list_tracks(
    event_id: int,
    db: Session = Depends(get_db),
):
    tracks = (
        db.query(Track)
        .filter(Track.event_id == event_id)
        .order_by(Track.name.asc())
        .all()
    )

    return [
        {
            "id": track.id,
            "event_id": track.event_id,
            "name": track.name,
            "description": track.description,
        }
        for track in tracks
    ]


@router.post(
    "/{event_id}/tracks/{track_id}/prizes",
    status_code=status.HTTP_201_CREATED,
)
def create_prize(
    event_id: int,
    track_id: int,
    prize_data: PrizeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"organizer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can manage prizes",
        )

    track = (
        db.query(Track)
        .filter(
            Track.id == track_id,
            Track.event_id == event_id,
        )
        .first()
    )

    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if (
        current_user.role != "admin"
        and event.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )

    prize = Prize(
        track_id=track.id,
        name=prize_data.name,
        amount=prize_data.amount,
    )

    db.add(prize)
    db.commit()
    db.refresh(prize)

    return {
        "id": prize.id,
        "track_id": prize.track_id,
        "name": prize.name,
        "amount": prize.amount,
    }


@router.get("/{event_id}/tracks/{track_id}/prizes")
def list_prizes(
    event_id: int,
    track_id: int,
    db: Session = Depends(get_db),
):
    track = (
        db.query(Track)
        .filter(
            Track.id == track_id,
            Track.event_id == event_id,
        )
        .first()
    )

    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    return [
        {
            "id": prize.id,
            "track_id": prize.track_id,
            "name": prize.name,
            "amount": prize.amount,
        }
        for prize in track.prizes
    ]