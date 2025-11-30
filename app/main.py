"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Create FastAPI app
app = FastAPI(
    title="Email Intelligence Platform",
    description="AI-powered email processing with Microsoft Graph integration",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Email Intelligence Platform API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "email-intelligence-api"
    }


# Import and include routers
from app.api import auth, webhooks, emails

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(emails.router, prefix="/api/emails", tags=["Emails"])

# Will be added as we build them:
# from app.api import actions, users
# app.include_router(actions.router, prefix="/api/actions", tags=["Actions"])
# app.include_router(users.router, prefix="/api/users", tags=["Users"])
