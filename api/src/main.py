from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import asyncio
import signal
import time
import logging
from datetime import datetime
from .routes import router
from .models import HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("teehr-api")

app = FastAPI(
    title="TEEHR Dashboard API", 
    version="0.1.0",
    timeout=300  # 5 minute timeout
)

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


# Add timeout middleware for long-running requests
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Add timeout handling for long-running requests."""
    start_time = time.time()
    
    try:
        # Set a timeout for request processing
        response = await asyncio.wait_for(call_next(request), timeout=300)  # 5 minutes
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log slow requests
        if process_time > 10:
            logger.warning(f"SLOW REQUEST: {request.method} {request.url.path} took {process_time:.3f}s")
        elif process_time > 5:
            logger.info(f"MEDIUM REQUEST: {request.method} {request.url.path} took {process_time:.3f}s")
        
        return response
    except asyncio.TimeoutError:
        logger.error(f"REQUEST TIMEOUT: {request.method} {request.url.path} after {time.time() - start_time:.3f}s")
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timed out after 5 minutes. Try reducing the data range or adding more filters."}
        )
    except Exception as e:
        logger.error(f"REQUEST ERROR: {request.method} {request.url.path} - {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"}
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