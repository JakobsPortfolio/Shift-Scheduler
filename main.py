from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
from scheduler import generate_schedule

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    employees: List[dict]
    availability: List[dict]
    shifts: List[dict]
    week_start: Optional[str] = None
    regenerate: Optional[bool] = None
    variation_seed: Optional[Any] = None


@app.get("/")
def home():
    return {"status": "scheduler running"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate")
def generate_post(payload: GenerateRequest):
    data = {
        "employees": payload.employees,
        "availability": payload.availability,
        "shifts": payload.shifts,
    }

    if payload.week_start:
        data["week_start"] = payload.week_start

    return generate_schedule(data)