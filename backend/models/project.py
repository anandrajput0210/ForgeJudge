from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    team_id = Column(
        Integer,
        ForeignKey("teams.id"),
        nullable=False,
    )
    track_id = Column(
        Integer,
        ForeignKey("tracks.id"),
        nullable=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    repository_url = Column(String(500), nullable=True)
    demo_url = Column(String(500), nullable=True)

    submitted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="draft",
    )

    team = relationship("Team")
    track = relationship("Track")