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

# Include Routers
from thaqib.api.routes import ptt
app.include_router(ptt.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to Thaqib API. Systems online."}
