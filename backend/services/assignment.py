from datetime import datetime, timezone

from sqlalchemy.orm import Session
from backend.services.audit import record_audit_event
from backend.models.judging import JudgeAssignment
from backend.models.project import Project
from backend.models.team import Team
from backend.models.user import User


def assign_judges(
    event_id: int,
    judges_per_project: int,
    db: Session,
    actor_user_id: int | None = None,
):
    projects = (
        db.query(Project)
        .join(Team, Project.team_id == Team.id)
        .filter(
            Team.event_id == event_id,
            Project.status == "submitted",
        )
        .order_by(Project.id.asc())
        .all()
    )

    judges = (
        db.query(User)
        .filter(User.role == "judge")
        .order_by(User.id.asc())
        .all()
    )

    judge_load = {
        judge.id: (
            db.query(JudgeAssignment)
            .filter(JudgeAssignment.judge_id == judge.id)
            .count()
        )
        for judge in judges
    }

    results = []

    for project in projects:
        team = (
            db.query(Team)
            .filter(Team.id == project.team_id)
            .first()
        )

        if team is None:
            results.append(
                {
                    "project_id": project.id,
                    "assigned": [],
                    "status": "incomplete",
                    "reason": "Project team not found",
                }
            )
            continue

        team_member_ids = {
            member.id
            for member in team.members
        }

        existing_judge_ids = {
            assignment.judge_id
            for assignment in (
                db.query(JudgeAssignment)
                .filter(
                    JudgeAssignment.project_id == project.id,
                    JudgeAssignment.status == "assigned",
                )
                .all()
            )
        }

        eligible_judges = [
            judge
            for judge in judges
            if judge.id not in team_member_ids
            and judge.id not in existing_judge_ids
        ]

        eligible_judges.sort(
            key=lambda judge: (
                judge_load[judge.id],
                judge.id,
            )
        )

        required_new_judges = max(
            0,
            judges_per_project - len(existing_judge_ids),
        )

        selected = eligible_judges[:required_new_judges]

        assigned = sorted(existing_judge_ids)

        for judge in selected:
            assignment = JudgeAssignment(
                project_id=project.id,
                judge_id=judge.id,
                status="assigned",
                assigned_at=datetime.now(timezone.utc),
            )

            db.add(assignment)
            db.flush()

            record_audit_event(
                db=db,
                actor_user_id=actor_user_id,
                action="JUDGE_ASSIGNED",
                resource_type="project",
                resource_id=project.id,
                new_value={
                    "judge_id": judge.id,
                    "assignment_id": assignment.id,
                },
            )
            judge_load[judge.id] += 1
            assigned.append(judge.id)

        assigned.sort()

        if len(assigned) >= judges_per_project:
            result_status = "complete"
            reason = None
        else:
            result_status = "incomplete"
            reason = (
                f"Only {len(assigned)} judges are assigned; "
                f"{judges_per_project} are required"
            )
        results.append(
            {
                "project_id": project.id,
                "assigned": assigned,
                "status": result_status,
                "reason": reason,
            }
        )

    db.commit()

    return {
        "event_id": event_id,
        "judges_per_project": judges_per_project,
        "projects_processed": len(projects),
        "results": results,
    }