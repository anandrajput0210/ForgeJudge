from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from backend.core.database import Base


class VotingConfig(Base):
    __tablename__ = "voting_configs"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id"),
        nullable=False,
        unique=True,
    )

    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    start_time = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_time = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    event = relationship("Event")