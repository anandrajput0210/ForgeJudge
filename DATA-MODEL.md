# ForgeJudge Data Model

## Core Entities

### User
- Stores account identity and role.
- Roles currently used: participant, judge, organizer, admin.

### Event
- Represents a hackathon event.
- Stores name, description, owner, start time, and end time.

### Track
- Belongs to an event.
- Groups projects and prizes.

### Prize
- Belongs to a track.
- Stores prize name and amount.

### Team
- Belongs to an event.
- Stores team name.
- Members are linked through the team_members association table.

### TeamInvite
- Stores team invitation tokens.
- Records the team, creator, and invitation token.

### Project
- Belongs to a team.
- Can belong to a track.
- Stores project name, description, repository URL, demo URL, submission timestamp, and status.

## Judging Entities

### JudgeInvite
- Stores judge invitation information and acceptance state.

### JudgeAssignment
- Connects a judge to a submitted project.
- Stores assignment status and assignment metadata.

### Rubric
- Belongs to an event.
- Contains configurable judging criteria.

### RubricCriterion
- Belongs to a rubric.
- Stores criterion name, description, weight, and maximum score.

### Score
- Connects an assignment to a rubric criterion.
- Stores the numeric score and timestamp.

### AuditEvent
- Stores important system actions.
- Records actor user, action, resource type, resource ID, old value, new value, and timestamp.

## Public Voting Entities

### Vote
- Connects an event, project, and voter.
- A database unique constraint prevents more than one vote per voter per event.

### Comment
- Connects an event and project to the participant who wrote the comment.
- Stores comment content and creation time.

### VotingConfig
- Belongs to an event.
- Stores whether voting is enabled and the configured voting start and end times.
- One configuration record is allowed per event.

## Relationships

Event
  -> Tracks
  -> Teams
  -> VotingConfig
  -> Rubrics

Team
  -> Members (through team_members)
  -> Projects
  -> TeamInvites

Project
  -> Team
  -> Track
  -> JudgeAssignments
  -> Votes
  -> Comments

Rubric
  -> RubricCriteria

JudgeAssignment
  -> Judge
  -> Project
  -> Scores

## Integrity Rules

- Users have unique email addresses.
- Team membership uses a composite team_id/user_id key.
- Judge assignments exclude project team members.
- Repeated judge assignment runs do not create duplicate assignments for the same judge/project.
- Rubric weights must total 100.
- Scores cannot be below 0 or above the criterion maximum.
- A participant can cast only one vote per event.
- Participants cannot vote for their own team.
- Voting configuration has one record per event.

## Import and Export Paths

- Judging data can be exported through the judging CSV API.
- Project and event data are stored in PostgreSQL.
- The application schema is created from SQLAlchemy models during startup.

## Database Runtime

PostgreSQL 16 is used by the Docker Compose deployment.
