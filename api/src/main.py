from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime
from .routes import router
from .models import HealthResponse

app = FastAPI(title="TEEHR Dashboard API", version="0.1.0")

# CORS middleware to allow frontend requests - MUST be first middleware
# Get the allowed origins from environment or use defaults
cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
print(f"DEBUG: CORS_ORIGINS from environment: {cors_origins_env}")

if cors_origins_env == "*":
    # In development, allow all origins
    allow_origins = ["*"]
    allow_credentials = False
    print("DEBUG: Using wildcard CORS origins")
else:
    # In production, use specific origins from environment
    allow_origins = [origin.strip() for origin in cors_origins_env.split(",")]
    allow_credentials = True
    print(f"DEBUG: Using specific CORS origins from config: {allow_origins}")

# Add CORS middleware FIRST - this is critical
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

app.include_router(router)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="0.1.0"
    )