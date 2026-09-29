from datetime import datetime, timedelta, timezone

from backend.core.database import Base, SessionLocal, engine
from backend.core.security import hash_password
from backend.models.user import User


Base.metadata.create_all(bind=engine)


def get_or_create_user(
    db,
    email: str,
    password: str,
    role: str,
):
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def seed():
    db = SessionLocal()

    try:
        organizer = get_or_create_user(
            db,
            "organizer@forgejudge.local",
            "Organizer123!",
            "organizer",
        )

        judge = get_or_create_user(
            db,
            "judge@forgejudge.local",
            "Judge123!",
            "judge",
        )

        judge2 = get_or_create_user(
            db,
            "judge2@forgejudge.local",
            "Judge2123!",
            "judge",
        )

        admin = get_or_create_user(
            db,
            "admin@forgejudge.local",
            "Admin123!",
            "admin",
        )

        participant = get_or_create_user(
            db,
            "participant@forgejudge.local",
            "Participant123!",
            "participant",
        )

        from backend.models.event import Event, Prize, Track
        from backend.models.project import Project
        from backend.models.team import Team

        event = (
            db.query(Event)
            .filter(Event.name == "ForgeJudge Demo Hackathon")
            .first()
        )

        if event is None:
            now = datetime.now(timezone.utc)

            event = Event(
                name="ForgeJudge Demo Hackathon",
                description=(
                    "Seeded event for local ForgeJudge evaluation."
                ),
                owner_id=organizer.id,
                start_time=now - timedelta(hours=1),
                end_time=now + timedelta(days=7),
            )

            db.add(event)
            db.commit()
            db.refresh(event)

            print(f"Event created: {event.name}")

        track = (
            db.query(Track)
            .filter(
                Track.event_id == event.id,
                Track.name == "General",
            )
            .first()
        )

        if track is None:
            track = Track(
                event_id=event.id,
                name="General",
                description=(
                    "Default track for the ForgeJudge demo event."
                ),
            )

            db.add(track)
            db.commit()
            db.refresh(track)

            print(f"Track created: {track.name}")

        prize = (
            db.query(Prize)
            .filter(
                Prize.track_id == track.id,
                Prize.name == "Demo Prize",
            )
            .first()
        )

        if prize is None:
            prize = Prize(
                track_id=track.id,
                name="Demo Prize",
                amount=1000,
            )

            db.add(prize)
            db.commit()

            print(f"Prize created: {prize.name}")
        team = (
            db.query(Team)
            .filter(
                Team.event_id == event.id,
                Team.name == "ForgeJudge Demo Team",
            )
            .first()
        )

        if team is None:
            team = Team(
                event_id=event.id,
                name="ForgeJudge Demo Team",
            )

            team.members.append(participant)

            db.add(team)
            db.commit()
            db.refresh(team)

            print(f"Team created: {team.name}")

        project = (
            db.query(Project)
            .filter(
                Project.team_id == team.id,
                Project.name == "Trust the Result Demo",
            )
            .first()
        )

        if project is None:
            project = Project(
                team_id=team.id,
                track_id=track.id,
                name="Trust the Result Demo",
                description=(
                    "Seeded project demonstrating the ForgeJudge "
                    "submission lifecycle."
                ),
                repository_url="https://example.local/demo",
                demo_url="https://example.local/demo",
                status="submitted",
                submitted_at=datetime.now(timezone.utc),
            )

            db.add(project)
            db.commit()

            print(f"Project created: {project.name}")
        print("ForgeJudge seed complete")
        print(f"Organizer: {organizer.email}")
        print(f"Judge: {judge.email}")
        print(f"Judge 2: {judge2.email}")
        print(f"Admin: {admin.email}")
        print(f"Participant: {participant.email}")

    finally:
        db.close()
if __name__ == "__main__":
    seed()