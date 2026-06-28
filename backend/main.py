import json
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from sqlalchemy.orm import Session

if __package__:
    from .agent import graph as lg_graph
    from .checkin import compare_photos, days_between
    from .models import User, Plant, Photo, Diagnosis, CarePlan, ChecklistItem, CheckIn, create_tables, get_db
    from .schemas import (
        UserCreate, UserOut, Token,
        PlantCreate, PlantOut,
        PhotoOut, DiagnosisOut, CarePlanOut, ChecklistToggle,
        StartDiagnoseRequest, AnswerRequest, DiagnoseStatus,
        CheckInOut,
    )
    from .auth import hash_password, verify_password, create_access_token, get_current_user
else:  # Running as `python main.py` directly from the backend folder
    from agent import graph as lg_graph
    from checkin import compare_photos, days_between
    from models import User, Plant, Photo, Diagnosis, CarePlan, ChecklistItem, CheckIn, create_tables, get_db
    from schemas import (
        UserCreate, UserOut, Token,
        PlantCreate, PlantOut,
        PhotoOut, DiagnosisOut, CarePlanOut, ChecklistToggle,
        StartDiagnoseRequest, AnswerRequest, DiagnoseStatus,
        CheckInOut,
    )
    from auth import hash_password, verify_password, create_access_token, get_current_user

app = FastAPI(title="Plant Doctor API")

_data_dir = os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent.parent))
UPLOADS_DIR = Path(_data_dir) / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.on_event("startup")
def startup():
    create_tables()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return Token(access_token=create_access_token(user.id))


@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Plants
# ---------------------------------------------------------------------------

@app.get("/plants", response_model=list[PlantOut])
def list_plants(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Plant).filter(Plant.user_id == current_user.id).all()


@app.post("/plants", response_model=PlantOut, status_code=201)
def create_plant(body: PlantCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plant = Plant(user_id=current_user.id, **body.model_dump())
    db.add(plant)
    db.commit()
    db.refresh(plant)
    return plant


@app.get("/plants/{plant_id}", response_model=PlantOut)
def get_plant(plant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plant = _get_owned_plant(plant_id, current_user.id, db)
    return plant


@app.delete("/plants/{plant_id}", status_code=204)
def delete_plant(plant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plant = _get_owned_plant(plant_id, current_user.id, db)
    db.delete(plant)
    db.commit()


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

@app.get("/plants/{plant_id}/photos", response_model=list[PhotoOut])
def list_photos(plant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned_plant(plant_id, current_user.id, db)
    return db.query(Photo).filter(Photo.plant_id == plant_id).order_by(Photo.taken_at.desc()).all()


@app.post("/plants/{plant_id}/photos", response_model=PhotoOut, status_code=201)
def upload_photo(
    plant_id: int,
    note: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_plant(plant_id, current_user.id, db)

    dest_dir = UPLOADS_DIR / str(current_user.id) / str(plant_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix or ".jpg"
    # use a timestamp-based filename to avoid collisions
    from datetime import datetime
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{suffix}"
    dest = dest_dir / filename

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    photo = Photo(plant_id=plant_id, filepath=str(dest), note=note or None)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


# ---------------------------------------------------------------------------
# Diagnoses & Care Plans
# ---------------------------------------------------------------------------

@app.get("/plants/{plant_id}/diagnoses", response_model=list[DiagnosisOut])
def list_diagnoses(plant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned_plant(plant_id, current_user.id, db)
    return db.query(Diagnosis).filter(Diagnosis.plant_id == plant_id).order_by(Diagnosis.created_at.desc()).all()


@app.get("/plants/{plant_id}/care-plan", response_model=CarePlanOut)
def get_care_plan(plant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned_plant(plant_id, current_user.id, db)
    latest_diagnosis = (
        db.query(Diagnosis)
        .filter(Diagnosis.plant_id == plant_id)
        .order_by(Diagnosis.created_at.desc())
        .first()
    )
    if not latest_diagnosis or not latest_diagnosis.care_plan:
        raise HTTPException(status_code=404, detail="No care plan yet")
    return latest_diagnosis.care_plan


@app.patch("/checklist/{item_id}", response_model=dict)
def toggle_checklist(
    item_id: int,
    body: ChecklistToggle,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.done = body.done
    db.commit()
    return {"id": item_id, "done": item.done}


# ---------------------------------------------------------------------------
# Weekly check-in
# ---------------------------------------------------------------------------

@app.post("/plants/{plant_id}/checkin", response_model=CheckInOut, status_code=201)
def weekly_checkin(
    plant_id: int,
    note: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime as dt

    plant = _get_owned_plant(plant_id, current_user.id, db)

    # Grab previous photo before saving the new one
    prev_photo = (
        db.query(Photo)
        .filter(Photo.plant_id == plant_id)
        .order_by(Photo.taken_at.desc())
        .first()
    )

    # Save new photo (same logic as upload_photo)
    dest_dir = UPLOADS_DIR / str(current_user.id) / str(plant_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix or ".jpg"
    filename = f"{dt.utcnow().strftime('%Y%m%d_%H%M%S')}{suffix}"
    dest = dest_dir / filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    new_photo = Photo(plant_id=plant_id, filepath=str(dest), note=note or None)
    db.add(new_photo)
    db.commit()
    db.refresh(new_photo)

    # Load active care plan steps for context
    care_plan_steps: list[str] = []
    latest_diag = (
        db.query(Diagnosis)
        .filter(Diagnosis.plant_id == plant_id)
        .order_by(Diagnosis.created_at.desc())
        .first()
    )
    if latest_diag and latest_diag.care_plan:
        care_plan_steps = json.loads(latest_diag.care_plan.steps)

    # Compare photos (or just describe if no previous photo)
    if prev_photo:
        elapsed = days_between(prev_photo.taken_at, dt.utcnow())
        result = compare_photos(prev_photo.filepath, str(dest), care_plan_steps, elapsed)
        prev_id = prev_photo.id
    else:
        result = {
            "progress": "stable",
            "changes_observed": "No previous photo to compare — this is your first check-in.",
            "recommendation": "Continue with the current care plan and check in again next week.",
        }
        elapsed = 0
        prev_id = None

    # Map progress → plant status
    status_map = {"improving": "recovering", "stable": "recovering", "worsening": "critical"}
    plant.status = status_map.get(result.get("progress", "stable"), "recovering")
    if not care_plan_steps:
        plant.status = "unknown"

    checkin = CheckIn(
        plant_id=plant_id,
        new_photo_id=new_photo.id,
        prev_photo_id=prev_id,
        progress=result.get("progress"),
        changes_observed=result.get("changes_observed"),
        recommendation=result.get("recommendation"),
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


@app.get("/plants/{plant_id}/checkins", response_model=list[CheckInOut])
def list_checkins(plant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned_plant(plant_id, current_user.id, db)
    return (
        db.query(CheckIn)
        .filter(CheckIn.plant_id == plant_id)
        .order_by(CheckIn.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Diagnose (LangGraph agent)
# ---------------------------------------------------------------------------

@app.post("/diagnose", response_model=DiagnoseStatus)
def start_diagnosis(
    body: StartDiagnoseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plant = _get_owned_plant(body.plant_id, current_user.id, db)
    photo = db.query(Photo).filter(
        Photo.id == body.photo_id, Photo.plant_id == body.plant_id
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    diag = Diagnosis(plant_id=body.plant_id, photo_id=body.photo_id)
    db.add(diag)
    db.commit()
    db.refresh(diag)

    thread_id = f"plant_{body.plant_id}_diag_{diag.id}"
    diag.thread_id = thread_id
    db.commit()

    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "plant_id": body.plant_id,
        "photo_path": photo.filepath,
        "description": body.description or "",
        "species": plant.species or "",
        "issue_category": "",
        "issue_summary": "",
        "clarifying_questions": [],
        "answers": [],
        "care_plan_steps": [],
        "expected_recovery_days": 0,
    }

    try:
        lg_graph.invoke(initial_state, config=config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    return _build_status(diag.id, config, db, plant)


@app.post("/diagnose/{diagnosis_id}/reply", response_model=DiagnoseStatus)
def reply_to_diagnosis(
    diagnosis_id: int,
    body: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diag = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
    if not diag:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    plant = _get_owned_plant(diag.plant_id, current_user.id, db)

    config = {"configurable": {"thread_id": diag.thread_id}}
    try:
        lg_graph.invoke(Command(resume=body.answer), config=config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    return _build_status(diagnosis_id, config, db, plant)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_status(diagnosis_id: int, config: dict, db: Session, plant: Plant) -> DiagnoseStatus:
    snapshot = lg_graph.get_state(config)
    state = snapshot.values

    # Collect any pending interrupt
    pending = [
        intr
        for task in snapshot.tasks
        for intr in task.interrupts
    ]

    if pending:
        val = pending[0].value
        question = val.get("question") if isinstance(val, dict) else str(val)
        return DiagnoseStatus(
            diagnosis_id=diagnosis_id,
            status="awaiting_answer",
            question=question,
            question_num=val.get("question_num", 1) if isinstance(val, dict) else 1,
            total_questions=val.get("total_questions", 1) if isinstance(val, dict) else 1,
            species=state.get("species") or None,
            issue_category=state.get("issue_category") or None,
            issue_summary=state.get("issue_summary") or None,
        )

    # Graph finished — persist results
    diag = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
    steps = state.get("care_plan_steps") or []

    if steps and not diag.care_plan:
        diag.issue_category = state.get("issue_category")
        diag.issue_summary = state.get("issue_summary")
        qa_pairs = [
            {"q": q, "a": a}
            for q, a in zip(
                state.get("clarifying_questions", []),
                state.get("answers", []),
            )
        ]
        diag.clarifying_qa = json.dumps(qa_pairs)

        care_plan = CarePlan(
            diagnosis_id=diagnosis_id,
            steps=json.dumps(steps),
            expected_recovery_days=state.get("expected_recovery_days") or 14,
        )
        db.add(care_plan)
        db.commit()
        db.refresh(care_plan)

        for step in steps:
            db.add(ChecklistItem(care_plan_id=care_plan.id, text=step))

        if state.get("species") and not plant.species:
            plant.species = state["species"]

        db.commit()

    return DiagnoseStatus(
        diagnosis_id=diagnosis_id,
        status="complete",
        species=state.get("species") or None,
        issue_category=state.get("issue_category") or None,
        issue_summary=state.get("issue_summary") or None,
        care_plan_steps=steps or None,
        expected_recovery_days=state.get("expected_recovery_days") or None,
    )


def _get_owned_plant(plant_id: int, user_id: int, db: Session) -> Plant:
    plant = db.query(Plant).filter(Plant.id == plant_id, Plant.user_id == user_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant
