import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

_data_dir = os.environ.get("DATA_DIR", ".")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_data_dir}/plant_doctor.db")
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    plants = relationship("Plant", back_populates="owner")

class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    species = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    status = Column(String, default="unknown")
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="plants")
    photos = relationship("Photo", back_populates="plant")
    diagnoses = relationship("Diagnoses", back_populates="plant")
    checkins = relationship("CheckIn", back_populates="plant")

class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    filepath = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    taken_at = Column(DateTime, default=datetime.utcnow)

    plant = relationship("Plant", back_populates="photos")

class Diagnoses(Base):
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=True)
    thread_id = Column(String, nullable=True, index=True)
    issue_category = Column(String, nullable=True)
    issue_summary = Column(Text, nullable=True)
    clarifying_qa = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plant = relationship("Plant", back_populates="diagnoses")
    care_plan = relationship("CarePlan", back_populates="diagnoses", uselist=False)

Diagnosis = Diagnoses

class CarePlan(Base):
    __tablename__ = "care_plans"

    id = Column(Integer, primary_key=True, index=True)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=False)
    steps = Column(Text, nullable=True)
    expected_recovery_days = Column(Integer, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    diagnoses = relationship("Diagnoses", back_populates="care_plan")
    checklist_items = relationship("ChecklistItem", back_populates="care_plan")

class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    care_plan_id = Column(Integer, ForeignKey("care_plans.id"), nullable=False)
    text = Column(String, nullable=False)
    done = Column(Boolean, default=False)

    care_plan = relationship("CarePlan", back_populates="checklist_items")

class CheckIn(Base):
    __tablename__ = "check_ins"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    new_photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    prev_photo_id = Column(Integer, ForeignKey("photos.id"), nullable=True)
    progress = Column(String, nullable=True)
    changes_observed = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plant = relationship("Plant", back_populates="checkins")

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
