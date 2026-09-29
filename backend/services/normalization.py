import math

from sqlalchemy.orm import Session

from backend.models.judging import JudgeAssignment, Score
from backend.models.project import Project
from backend.models.team import Team

def calculate_weighted_score(
    assignment: JudgeAssignment,
    db: Session,
) -> float | None:
    scores = (
        db.query(Score)
        .filter(
            Score.assignment_id == assignment.id,
        )
        .all()
    )

    if not scores:
        return None

    weighted_total = 0.0
    weight_total = 0.0

    for score in scores:
        criterion = score.criterion

        if criterion is None or criterion.max_score <= 0:
            continue

        percentage_score = (
            score.score_value / criterion.max_score
        ) * 100.0

        weighted_total += (
            percentage_score * criterion.weight
        )
        weight_total += criterion.weight

    if weight_total <= 0:
        return None

    return weighted_total / weight_total


def get_event_id_for_assignment(
    assignment: JudgeAssignment,
    db: Session,
) -> int | None:
    if assignment.project is None:
        return None

    return (
        db.query(Team.event_id)
        .filter(
            Team.id == assignment.project.team_id
        )
        .scalar()
    )

def normalize_project_scores(
    project_id: int,
    db: Session,
):
    assignments = (
        db.query(JudgeAssignment)
        .filter(
            JudgeAssignment.project_id == project_id,
            JudgeAssignment.status == "assigned",
        )
        .order_by(JudgeAssignment.id.asc())
        .all()
    )

    if not assignments:
        return {
            "project_id": project_id,
            "status": "insufficient_data",
            "reason": "No judge assignments found",
            "judges": [],
            "final_score": None,
        }

    event_id = get_event_id_for_assignment(
        assignments[0],
        db,
    )

    if event_id is None:
        return {
            "project_id": project_id,
            "status": "insufficient_data",
            "reason": "Project event could not be determined",
            "judges": [],
            "final_score": None,
        }

    completed_assignments = []

    all_event_assignments = (
        db.query(JudgeAssignment)
        .join(
            Project,
            Project.id == JudgeAssignment.project_id,
        )
        .join(
            Team,
            Team.id == Project.team_id,
        )
        .filter(
            Team.event_id == event_id,
            JudgeAssignment.status == "assigned",
        )
        .order_by(JudgeAssignment.id.asc())
        .all()
    )
    for assignment in all_event_assignments:
        weighted_score = calculate_weighted_score(
            assignment,
            db,
        )

        if weighted_score is None:
            continue

        completed_assignments.append(
            {
                "assignment": assignment,
                "weighted_score": weighted_score,
            }
        )

    target_judges = [
        assignment.judge_id
        for assignment in assignments
    ]

    judge_distributions = {
        judge_id: []
        for judge_id in target_judges
    }

    for item in completed_assignments:
        judge_id = item["assignment"].judge_id

        if judge_id in judge_distributions:
            judge_distributions[judge_id].append(
                item["weighted_score"]
            )

    judge_results = []

    for assignment in assignments:
        raw_score = calculate_weighted_score(
            assignment,
            db,
        )

        if raw_score is None:
            continue

        distribution = judge_distributions.get(
            assignment.judge_id,
            [],
        )

        if len(distribution) < 3:
            judge_results.append(
                {
                    "judge_id": assignment.judge_id,
                    "raw_score": round(raw_score, 2),
                    "normalized_score": None,
                    "status": "fallback",
                    "reason": (
                        "At least 3 completed evaluations "
                        "from this judge are required"
                    ),
                }
            )
            continue

        mean = sum(distribution) / len(distribution)

        variance = sum(
            (value - mean) ** 2
            for value in distribution
        ) / len(distribution)

        std_dev = math.sqrt(variance)

        if std_dev < 1e-9:
            judge_results.append(
                {
                    "judge_id": assignment.judge_id,
                    "raw_score": round(raw_score, 2),
                    "normalized_score": round(raw_score, 2),
                    "status": "fallback",
                    "reason": "Judge scores have zero variance",
                }
            )
            continue

        z_score = (
            raw_score - mean
        ) / std_dev

        normalized_score = 50.0 + (z_score * 15.0)

        normalized_score = max(
            0.0,
            min(100.0, normalized_score),
        )

        judge_results.append(
            {
                "judge_id": assignment.judge_id,
                "raw_score": round(raw_score, 2),
                "normalized_score": round(
                    normalized_score,
                    2,
                ),
                "status": "normalized",
                "judge_mean": round(mean, 2),
                "judge_std_dev": round(
                    std_dev,
                    2,
                ),
            }
        )

    normalized_values = [
        item["normalized_score"]
        for item in judge_results
        if item["normalized_score"] is not None
    ]

    if not normalized_values:
        raw_values = [
            item["raw_score"]
            for item in judge_results
        ]

        return {
            "project_id": project_id,
            "status": "insufficient_data",
            "reason": (
                "Not enough completed judge history "
                "for reliable normalization"
            ),
            "judges": judge_results,
            "final_score": (
                round(
                    sum(raw_values) / len(raw_values),
                    2,
                )
                if raw_values
                else None
            ),
        }

    final_score = (
        sum(normalized_values)
        / len(normalized_values)
    )

    overall_status = (
        "normalized"
        if all(
            item["status"] == "normalized"
            for item in judge_results
        )
        else "mixed"
    )

    return {
        "project_id": project_id,
        "status": overall_status,
        "judges": judge_results,
        "final_score": round(final_score, 2),
    }