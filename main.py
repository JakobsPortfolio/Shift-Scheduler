from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from pathlib import Path
from scheduler import generate_schedule

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
SAMPLE_DATA_FILE = BASE_DIR / "sample_data.json"
STATE_FILE = BASE_DIR / "schedule_state.json"


class GenerateRequest(BaseModel):
    week_start: str | None = None


def load_json_file(path: Path):
    with open(path) as f:
        return json.load(f)


def save_json_file(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def merge_data_with_state(base_data, state_data):
    state_employees = state_data.get("employees", {})

    for emp in base_data["employees"]:
        state = state_employees.get(str(emp["id"]), {})
        emp["hours_worked_this_month"] = state.get("hours_worked_this_month", 0)
        emp["last_week_shift_types"] = state.get("last_week_shift_types", [])
        emp["last_week_worked_weekend"] = state.get("last_week_worked_weekend", False)

    return base_data


@app.get("/")
def home():
    return {"status": "scheduler running"}

# Demo endpoint
@app.get("/generate")
def generate_get():
    base_data = load_json_file(SAMPLE_DATA_FILE)
    state_data = load_json_file(STATE_FILE)
    merged_data = merge_data_with_state(base_data, state_data)

    result = generate_schedule(merged_data)
    save_json_file(STATE_FILE, result["next_state"])

    return result

# Prod endpoint
@app.post("/generate")
def generate_post(payload: GenerateRequest):
    base_data = load_json_file(SAMPLE_DATA_FILE)
    state_data = load_json_file(STATE_FILE)
    merged_data = merge_data_with_state(base_data, state_data)

    if payload.week_start:
        merged_data["week_start"] = payload.week_start

    result = generate_schedule(merged_data)
    save_json_file(STATE_FILE, result["next_state"])

    return result