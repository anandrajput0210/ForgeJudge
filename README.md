# ForgeJudge

**Trust the Result.**

ForgeJudge is a self-hostable hackathon submission and judging platform built with React, FastAPI, PostgreSQL, and Docker Compose.

## Run locally

    docker compose up

Frontend: http://localhost:3000
Backend: http://localhost:8000
API docs: http://localhost:8000/docs

## T1 - Core

- Authentication and login
- Participant, judge, organizer, and admin roles
- Event creation and configurable dates
- Tracks and prizes
- Team creation and invitations
- Project creation, editing, and submission
- Submission deadline enforcement
- Public project gallery

## T2 - Judging

- Judge invitations and acceptance
- Algorithmic judge assignment
- Team-member conflict exclusion
- Idempotent assignments
- Weighted judging rubrics
- Backend-enforced role isolation
- Judge progress tracking
- Organizer judging progress
- Cross-judge score normalization
- Normalized leaderboard
- CSV judging export
- Audit records for judging actions

## T3 - Public

- Configurable community voting
- One vote per participant per event
- Own-team voting protection
- Voting rate limiting
- Hidden results while voting is open
- Results revealed after voting closes
- Randomized project ordering
- Project comments
- Audit records for votes and comments

## Technology

Frontend: React + TypeScript + Vite
Backend: Python + FastAPI
Database: PostgreSQL 16
Deployment: Docker Compose

## Judging normalization

ForgeJudge uses judge-distribution normalization. Each judge's completed evaluations are used to calculate that judge's scoring distribution. Project scores can then be normalized against the relevant judge distribution. When insufficient historical data is available, the system falls back instead of applying an unreliable normalization.

## Security and integrity

Backend authorization protects judge and organizer operations. Voting includes duplicate-vote protection, own-team protection, rate limiting, and audit records.

## Current status

T1, T2, and T3 backend functionality has been implemented and tested. The frontend provides the public gallery, authentication, voting, comments, and project interaction flow.