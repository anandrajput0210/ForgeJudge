from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    owner = relationship("User")
    tracks = relationship(
        "Track",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id"),
        nullable=False,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    event = relationship(
        "Event",
        back_populates="tracks",
    )

    prizes = relationship(
        "Prize",
        back_populates="track",
        cascade="all, delete-orphan",
    )


class Prize(Base):
    __tablename__ = "prizes"

    id = Column(Integer, primary_key=True, index=True)

    track_id = Column(
        Integer,
        ForeignKey("tracks.id"),
        nullable=False,
    )

    name = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=True)

    track = relationship(
        "Track",
        back_populates="prizes",
    )