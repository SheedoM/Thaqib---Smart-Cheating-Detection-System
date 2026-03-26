from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI App
app = FastAPI(
    title="Thaqib Smart Cheating Detection System API",
    description="Backend API and WebSocket services for real-time exam monitoring.",
    version="1.0.0"
)

# Apply CORS Middleware for Frontend Access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.thaqib.api.routes import ptt, auth, institutions, halls, setup, devices, users, exams

app.include_router(ptt.router, prefix="/api/v1/ptt")
app.include_router(setup.router, prefix="/api/setup", tags=["Setup"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(institutions.router, prefix="/api/institutions", tags=["Institutions"])
app.include_router(halls.router, prefix="/api/halls", tags=["Halls"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(exams.router, prefix="/api/sessions", tags=["Exam Sessions"])

@app.get("/")
async def root():
    return {"message": "Welcome to Thaqib API. Systems online."}
