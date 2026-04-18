from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.thaqib.core.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Initialize FastAPI App
app = FastAPI(
    title="Thaqib Smart Cheating Detection System API",
    description="Backend API and WebSocket services for real-time exam monitoring.",
    version="1.0.0"
)

# Attach Limiter to app and set exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Custom Middleware for Security Headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
    return response

# Apply CORS Middleware for Frontend Access
# In production, this list should be strictly controlled via environment variables
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from src.thaqib.api.routes import ptt, auth, institutions, halls, setup, devices, users, exams, events, stream

app.include_router(ptt.router, prefix="/api/v1/ptt")
app.include_router(setup.router, prefix="/api/setup", tags=["Setup"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(institutions.router, prefix="/api/institutions", tags=["Institutions"])
app.include_router(halls.router, prefix="/api/halls", tags=["Halls"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(exams.router, prefix="/api/sessions", tags=["Exam Sessions"])
app.include_router(events.router, prefix="/api/events", tags=["Detection Events"])
app.include_router(stream.router, prefix="/api/stream", tags=["Video Stream"])

@app.get("/")
async def root():
    return {"message": "Welcome to Thaqib API. Systems online."}
