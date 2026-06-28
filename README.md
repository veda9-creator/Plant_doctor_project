# 🌿 Plant Doctor

An AI-powered plant diagnosis app. Upload a photo of your plant, describe the problem, and get a diagnosis, care plan, and weekly progress tracking.

## Features

- User Accounts — Register, log in, manage multiple plants
- AI Diagnosis — Identifies plant species and diagnoses issues (water, light, pests, nutrients, disease)
- Clarifying Questions — The AI asks follow-up questions before prescribing a care plan
- Care Plan & Checklist — Step-by-step recovery plan with a trackable checklist
- Weekly Check-ins — Upload a new photo each week; the AI compares before/after and tracks progress

## Tech Stack
 Frontend -> Streamlit 
 Backend -> FastAPI 
 AI Agent -> LangGraph + OpenAI GPT-4o, GPT-5.2
 Database -> SQLite + SQLAlchemy 
 Auth -> JWT + bcrypt 

 ## Setup	

**1. Clone the repo**
git clone https://github.com/veda9-creator/Plant_doctor_project.git
cd plant-doctor

**2. Create a virtual environment and install dependencies**
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

**3. Add your OpenAI API key**
Create a .env file in the project root:
OPENAI_API_KEY=your-key-here

**4. Run the backend**
uvicorn backend.main:app --reload --port 8000

**5. Run the frontend (in a second terminal)**
streamlit run frontend/app.py
**Open http://localhost:8501 in your browser.**

**Project Structure**
plant-doctor/
├── backend/
│   ├── main.py        # FastAPI routes
│   ├── agent.py       # LangGraph AI agent
│   ├── models.py      # SQLAlchemy models
│   ├── schemas.py     # Pydantic schemas
│   ├── auth.py        # JWT authentication
│   └── checkin.py     # Weekly check-in logic
├── frontend/
│   └── app.py         # Streamlit UI
├── uploads/           # Uploaded plant photos
└── requirements.txt   # Install dependencies



