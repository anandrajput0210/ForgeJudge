from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.core.database import Base


class JudgeAssignment(Base):
    __tablename__ = "judge_assignments"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
    )

    judge_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    status = Column(
        String(30),
        nullable=False,
        default="assigned",
    )

    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    project = relationship("Project")
    judge = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "judge_id",
            name="uq_project_judge",
        ),
    )


class Rubric(Base):
    __tablename__ = "rubrics"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id"),
        nullable=False,
    )

    name = Column(String(255), nullable=False)

    event = relationship("Event")
    criteria = relationship(
        "RubricCriterion",
        cascade="all, delete-orphan",
    )


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"

    id = Column(Integer, primary_key=True, index=True)

    rubric_id = Column(
        Integer,
        ForeignKey("rubrics.id"),
        nullable=False,
    )

    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)

    weight = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False, default=100.0)

    rubric = relationship("Rubric")


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)

    assignment_id = Column(
        Integer,
        ForeignKey("judge_assignments.id"),
        nullable=False,
    )

    criterion_id = Column(
        Integer,
        ForeignKey("rubric_criteria.id"),
        nullable=False,
    )

    score_value = Column(Float, nullable=False)

    scored_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    assignment = relationship("JudgeAssignment")
    criterion = relationship("RubricCriterion")

    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "criterion_id",
            name="uq_assignment_criterion",
        ),
    )
class JudgeInvite(Base):
    __tablename__ = "judge_invites"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id"),
        nullable=False,
    )

    email = Column(
        String(255),
        nullable=False,
        index=True,
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

    accepted_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    accepted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="pending",
    )

    event = relationship("Event")
    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )
    accepted_user = relationship(
        "User",
        foreign_keys=[accepted_by],
    )

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)

    actor_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    action = Column(
        String(100),
        nullable=False,
    )

    resource_type = Column(
        String(100),
        nullable=False,
    )

    resource_id = Column(
        Integer,
        nullable=True,
    )

    old_value = Column(
        String(5000),
        nullable=True,
    )

    new_value = Column(
        String(5000),
        nullable=True,
    )

    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    actor = relationship("User")