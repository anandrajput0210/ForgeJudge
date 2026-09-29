from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from backend.core.database import Base


team_members = Table(
    "team_members",
    Base.metadata,
    Column(
        "team_id",
        ForeignKey("teams.id"),
        primary_key=True,
    ),
    Column(
        "user_id",
        ForeignKey("users.id"),
        primary_key=True,
    ),
)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id"),
        nullable=False,
    )

    name = Column(String(255), nullable=False)

    members = relationship(
        "User",
        secondary=team_members,
        backref="teams",
    )

    event = relationship("Event")
class TeamInvite(Base):
    __tablename__ = "team_invites"

    id = Column(Integer, primary_key=True, index=True)

    team_id = Column(
        Integer,
        ForeignKey("teams.id"),
        nullable=False,
    )

    token = Column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    team = relationship("Team")
    creator = relationship("User")