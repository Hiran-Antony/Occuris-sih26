"""
Occuris FastAPI Application — Main entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api.region import router as region_router
from app.api.vessels import router as vessel_router
from app.api.journeys import journey_router, dashboard_router
from app.api.forensics import router as forensics_router

app = FastAPI(
    title="Occuris Maritime Intelligence API",
    description="Maritime Memory & Oil Spill Forensic Investigation System — SIH 2026",
    version="1.0.0",
)

# Allow the Vite dev server (localhost:5173) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(region_router)
app.include_router(vessel_router)
app.include_router(journey_router)
app.include_router(dashboard_router)
app.include_router(forensics_router)


from fastapi.staticfiles import StaticFiles
import os

# Mount the masks directory so the frontend can display them
masks_dir = os.path.join(os.path.dirname(__file__), "..", "data", "masks")
os.makedirs(masks_dir, exist_ok=True)
app.mount("/masks", StaticFiles(directory=masks_dir), name="masks")

@app.on_event("startup")
def startup():
    init_db()
    print("[OK] Occuris API ready - Bay of Bengal Maritime Intelligence System")


@app.get("/")
def root():
    return {
        "system": "Occuris Maritime Intelligence",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }
