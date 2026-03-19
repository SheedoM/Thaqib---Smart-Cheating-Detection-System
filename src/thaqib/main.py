from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI App
app = FastAPI(
    title="Thaqib Smart Cheating Detection System API",
    description="Backend API and WebSocket services for real-time exam monitoring.",
    version="1.0.0"
)

# Automated Database Initialization (Dev/Setup convenience)
from src.thaqib.db.database import engine
from src.thaqib.db.models import Base
import src.thaqib.db.models # Ensure all models are imported for metadata

Base.metadata.create_all(bind=engine)

# Apply CORS Middleware for Frontend Access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
from src.thaqib.api.routes import ptt, auth, institutions, halls, setup

app.include_router(ptt.router, prefix="/api/v1/ptt")
app.include_router(setup.router, prefix="/api/setup", tags=["Setup"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(institutions.router, prefix="/api/institutions", tags=["Institutions"])
app.include_router(halls.router, prefix="/api/halls", tags=["Halls"])

@app.get("/")
async def root():
    return {"message": "Welcome to Thaqib API. Systems online."}
