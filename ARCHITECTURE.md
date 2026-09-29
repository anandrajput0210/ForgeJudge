# ForgeJudge Architecture

## Overview

ForgeJudge is a self-hostable hackathon submission and judging platform. The system is organized as a frontend application, a FastAPI backend, and a PostgreSQL database, all started through Docker Compose.

## Components

### Frontend

- React
- TypeScript
- Vite
- Browser fetch API for backend communication
- Nginx serves the production frontend build

### Backend

- Python
- FastAPI
- SQLAlchemy
- Role-based authorization
- REST API endpoints for authentication, events, teams, projects, judging, and public voting

### Database

- PostgreSQL 16
- SQLAlchemy models define the application schema
- Database tables are created through SQLAlchemy metadata during application startup

## Runtime Flow

1. Docker Compose starts PostgreSQL.
2. The FastAPI backend connects to PostgreSQL and initializes the application schema.
3. Seed data creates the local demonstration event and users.
4. The frontend is served by Nginx.
5. Browser requests are sent to the FastAPI REST API.
6. Backend authorization validates the user's role before protected operations.

## Judging Architecture

The judging subsystem contains judge invitations, judge assignments, configurable weighted rubrics, criterion scores, judge progress tracking, score normalization, leaderboard generation, and CSV export.

Judge assignment is performed by a backend service. Existing assignments are counted so repeated assignment runs are idempotent. Project team members and judges already assigned to the project are excluded from the eligible judge set.

Score normalization uses judge-specific scoring distributions. When a judge does not have sufficient completed evaluation history or has zero variance, the system uses a fallback instead of applying an unreliable normalization.

## Public Voting Architecture

The voting subsystem contains configurable voting windows, community votes, comments, randomized project ordering, duplicate-vote prevention, rate limiting, hidden results during voting, and post-voting result disclosure.

Voting configuration is stored separately from the event record. The vote creation and results endpoints use the configured voting window when one exists.

## Audit Architecture

Important operations record audit events. The audit record contains the acting user, action, resource type, resource ID, and serialized old/new values where applicable.

Examples include:
- Project submission
- Judge score creation and updates
- Vote creation
- Comment creation
- Voting configuration changes

## Authorization

Authorization is enforced in the backend rather than relying only on frontend visibility.

Examples:
- Participants cannot access judge-only endpoints.
- Judges cannot access another judge's assignment.
- Only organizers and administrators can perform judging administration.
- Only participants can cast community votes.
- Participants cannot vote for their own team.

## Deployment

ForgeJudge is designed to run locally with:

    docker compose up

The application uses local PostgreSQL and does not require a hosted database or external authentication service for the local deployment.

## Design Principle

Trust the Result: judging, voting, permissions, and auditability are implemented as backend-controlled workflows so the final result does not depend solely on frontend behavior.
