from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# --- Auth ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Plants ---

class PlantCreate(BaseModel):
    name: str
    species: Optional[str] = None
    location: Optional[str] = None


class PlantOut(BaseModel):
    id: int
    name: str
    species: Optional[str]
    location: Optional[str]
    status: str = "unknown"
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Photos ---

class PhotoOut(BaseModel):
    id: int
    plant_id: int
    filepath: str
    taken_at: datetime
    note: Optional[str]

    model_config = {"from_attributes": True}


# --- Diagnoses ---

class DiagnosisOut(BaseModel):
    id: int
    plant_id: int
    photo_id: Optional[int]
    issue_category: Optional[str]
    issue_summary: Optional[str]
    clarifying_qa: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Care Plans ---

class ChecklistItemOut(BaseModel):
    id: int
    text: str
    done: bool

    model_config = {"from_attributes": True}


class CarePlanOut(BaseModel):
    id: int
    diagnosis_id: int
    steps: str
    expected_recovery_days: Optional[int]
    status: str
    created_at: datetime
    checklist_items: list[ChecklistItemOut] = []

    model_config = {"from_attributes": True}


# --- Diagnose request / response (from frontend) ---

class StartDiagnoseRequest(BaseModel):
    plant_id: int
    photo_id: int
    description: str = ""


class AnswerRequest(BaseModel):
    answer: str


class DiagnoseStatus(BaseModel):
    diagnosis_id: int
    status: str                        # "awaiting_answer" | "complete" | "error"
    # present when status == "awaiting_answer"
    question: Optional[str] = None
    question_num: Optional[int] = None
    total_questions: Optional[int] = None
    # always present once vision has run
    species: Optional[str] = None
    issue_category: Optional[str] = None
    issue_summary: Optional[str] = None
    # present when status == "complete"
    care_plan_steps: Optional[list[str]] = None
    expected_recovery_days: Optional[int] = None


class ChecklistToggle(BaseModel):
    done: bool


# --- Weekly check-in ---

class CheckInOut(BaseModel):
    id: int
    plant_id: int
    new_photo_id: int
    prev_photo_id: Optional[int]
    progress: Optional[str]          # improving / stable / worsening
    changes_observed: Optional[str]
    recommendation: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
