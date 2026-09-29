# ForgeJudge Judging System

## Purpose

ForgeJudge separates judging from the public submission workflow. Judge operations are protected by backend authorization and all important judging actions are recorded in the audit trail.

## Judge Invitation

Organizers can invite judges to an event. Judges accept invitations through a token-based workflow and become associated with the event.

## Judge Assignment

Judges are assigned to submitted projects by the backend assignment service.

The assignment algorithm:

1. Finds eligible judges for the event.
2. Removes members of the project's team from the eligible set.
3. Removes judges already assigned to the project.
4. Considers judge workload when selecting judges.
5. Creates only the number of new assignments required.

Repeated assignment runs are idempotent because existing assignments count toward the required judge count.

## Conflict Prevention

A project team member cannot be selected as a judge for that project. This rule is enforced by the backend assignment logic.

Judges are also prevented from accessing another judge's assignment.

## Rubric

ForgeJudge supports configurable weighted rubrics. Each criterion has a name, description, weight, and maximum score.

Criterion weights must total 100 percent.

## Scoring

Judges submit numeric scores for rubric criteria. The backend validates that scores are within the criterion's configured range.

Scores are linked to the judge assignment and criterion.

Partial evaluations are supported. An assignment with zero scores is not_started, an assignment with some but not all required criteria is in_progress, and an assignment with all required criteria is completed.

## Progress Tracking

Judge progress reports total assignments, completed assignments, in-progress assignments, not-started assignments, and progress percentage.

Organizers can view aggregate judging progress for the event.

## Score Normalization

ForgeJudge uses judge-distribution normalization rather than normalizing judges against only one project.

For a target project, each judge's raw weighted score is compared with that judge's completed evaluation distribution for the same event.

The normalized score uses the judge's mean and standard deviation and is rescaled to a bounded score range.

Normalization is used only when enough completed judge history exists and the judge distribution has non-zero variance.

When there is insufficient data or zero variance, the system falls back to the raw score instead of applying an unreliable normalization.

This approach allows a judge who systematically scores higher or lower than another judge to be compared through their own scoring distribution.

## Leaderboard

The leaderboard calculates final project scores using the judging normalization service and sorts projects by final score.

Projects without sufficient completed judging data remain pending until a final score can be calculated.

## CSV Export

Organizers can export assignment and criterion score data as CSV.

## Auditability

The judging workflow records audit events for important changes.

Examples include:
- Score creation
- Score updates
- Project submission
- Judge assignment

Audit records contain the acting user, action, resource type, resource ID, and old/new values when available.

## Authorization Model

Organizer and admin operations include judge invitations, assignment, rubric creation, normalization, leaderboard access, progress access, and export.

Judges can access only their own assignments and submit scores for assignments assigned to them.

Participants cannot access judge-only operations.

## Normalization Proof

The local acceptance test used two judges and four projects. Both judges completed enough evaluations to activate normalization.

Project 1 produced:
- Judge 2 raw score: 85.5
- Judge 2 normalized score: 49.60
- Judge 6 raw score: 74.5
- Judge 6 normalized score: 29.15
- Final normalized score: 39.38

The leaderboard subsequently consumed normalized scores for the projects.
