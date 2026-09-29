from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.teams import router as teams_router
from backend.api.events import router as events_router
from backend.api.auth import router as auth_router
from backend.models import event, judging, project, team, user, vote, comment, voting
from backend.api.votes import router as votes_router
from backend.core.database import Base, engine
from database.seed import seed
from backend.api.projects import router as projects_router
from backend.api.judging import router as judging_router
app = FastAPI(
    title="ForgeJudge",
    description="Self-hostable hackathon submission and judging platform",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


Base.metadata.create_all(bind=engine)

seed()
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(teams_router)
app.include_router(projects_router)
app.include_router(judging_router)
app.include_router(votes_router)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "ForgeJudge",
    }