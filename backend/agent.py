from typing import TypedDict
import base64
import json
from pathlib import Path
from urllib.parse import unquote, urlparse
from openai import OpenAI
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
import sqlite3

client = OpenAI()

class Plant(TypedDict):
   plant_id: str
   photo_path: str
   description: str
   species: str
   issue_category: str
   issue_summary: str
   clarifying_questions: list[str]
   answers: list[str]
   care_plan_steps: list[str]
   expected_recovery_days: int


def normalize_image_path(image_path: str) -> str:
    """Convert file:// URIs or normal paths to a local filesystem path."""
    if image_path.startswith("file://"):
        parsed = urlparse(image_path)
        if parsed.scheme == "file":
            image_path = unquote(parsed.path)
            if image_path.startswith("/") and len(image_path) > 2 and image_path[2] == ":":
                image_path = image_path.lstrip("/")
    return str(Path(image_path))


def get_image_mime_type(image_path: str) -> str:
    """Return the MIME type for the image based on its file extension."""
    extension = Path(image_path).suffix.lower()
    if extension == ".jpg" or extension == ".jpeg":
        return "image/jpeg"
    if extension == ".png":
        return "image/png"
    if extension == ".webp":
        return "image/webp"
    if extension == ".gif":
        return "image/gif"
    return "application/octet-stream"


def encoded_image(image_path: str) -> str:
    """Converts the image from the given path into a base64 encoded string."""
    image_path = normalize_image_path(image_path)
    with open(image_path, "rb") as file:
        return base64.b64encode(file.read()).decode("UTF-8")


def parse_llm_json(output_text: str) -> dict:
    """Try to parse LLM text output as JSON and return a dictionary."""
    cleaned = output_text.strip()
    if cleaned.startswith("```") and cleaned.rstrip().endswith("```"):
        cleaned = cleaned.strip("`\n ")
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip().strip("`\n ")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        alt = cleaned.replace("'", '"')
        try:
            return json.loads(alt)
        except json.JSONDecodeError:
            return {}


_b64 = encoded_image
_parse_json = parse_llm_json

def _chat(messages: list, max_tokens: int = 512) -> str:
    result = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=max_tokens,
    )
    return result.choices[0].message.content


def call_llm(prompt:str, image_path:str) -> str:

    image_path = normalize_image_path(image_path)
    mime_type = get_image_mime_type(image_path)
    base64_data = encoded_image(image_path)

    result = client.responses.create(
        model="gpt-5.2",
        input=[
            {
                "role" : "user",
                "content" : [
                    {
                        "type" : "input_text",
                        "text" : prompt
                    },
                    {
                        "type" : "input_image",
                        "image_url" : f"data:{mime_type};base64,{base64_data}"
                    }
                ]
            }
        ]
    )

    return result.output_text

    
def identify_species(state:Plant) -> dict:
    prompt = """What plant species is in this photo? 
              Reply with only: 'Common Name (Scientific name)'."""

    result = call_llm(prompt, state["photo_path"])
    return {"species": result.strip()}

def diagnose_issue(state:Plant) -> dict:
    prompt = (
        f"You are a plant doctor. Examine this plant photo carefully.\n"
        f"Species: {state.get('species') or 'Unknown'}\n"
        f"Owner says: \"{state['description']}\"\n\n"
        "Diagnose the PRIMARY issue. Choose ONE category:\n"
        "  water | light | pest | nutrient | disease | healthy\n\n"
        'Return only valid JSON with keys "category" and "summary".'
    )

    result_text = call_llm(prompt, state["photo_path"])
    parsed = parse_llm_json(result_text)
    return {
        "issue_category": parsed.get("category", result_text.strip()),
        "issue_summary": parsed.get("summary", "")
    }

def generate_questions(state: Plant) -> dict:
    prompt = (
        f"A plant owner needs help diagnosing their plant.\n"
        f"Species: {state.get('species') or 'Unknown'}\n"
        f"Problem: {state.get('issue_category', 'Unknown')} — {state.get('issue_summary', '')}\n"
        f"Owner's description: \"{state['description']}\"\n\n"
        "Write exactly 2 short, specific clarifying questions to refine the treatment.\n"
        "Focus on: watering habits, light exposure, recent changes, last fertilized.\n"
        "Return ONLY a JSON array: [\"question 1\", \"question 2\"]"
    )
    raw = call_llm(prompt, state["photo_path"])
    questions = parse_llm_json(raw)

    return {"clarifying_questions": [str(q) for q in questions[:2]]}

def ask_clarifying(state: Plant) -> dict:
    """Asks one question at a time via interrupt(). Loops back until all answered."""
    questions = state["clarifying_questions"]
    answers = list(state.get("answers") or [])
    idx = len(answers)

    answer = interrupt({
        "question": questions[idx],
        "question_num": idx + 1,
        "total_questions": len(questions),
    })

    return {"answers": answers + [answer]}

def route_after_clarifying(state: Plant) -> str:
    answers = state.get("answers") or []
    questions = state.get("clarifying_questions") or []
    return "ask_clarifying" if len(answers) < len(questions) else "prescribe"

def prescribe(state: Plant) -> dict:
    qa_text = "\n".join(
        f"Q: {q}\nA: {a}"
        for q, a in zip(state["clarifying_questions"], state["answers"])
    )
    prompt = (
        f"You are a plant doctor. Write a specific recovery plan.\n\n"
        f"Plant: {state.get('species') or 'Unknown'}\n"
        f"Problem: {state['issue_category']} — {state['issue_summary']}\n"
        f"Owner answered:\n{qa_text}\n\n"
        "Write a recovery plan with:\n"
        "1. Immediate actions (what to do today)\n"
        "2. This week's ongoing care\n"
        "3. What improvement signs to look for in 7 days\n\n"
        "Return JSON:\n"
        '{{"steps": ["Immediately do X", "Over the next week, do Y", ...], "expected_recovery_days": 14}}'
    )
    raw = call_llm(prompt, state["photo_path"])
    data = parse_llm_json(raw)
    return {
        "care_plan_steps": data["steps"],
        "expected_recovery_days": int(data.get("expected_recovery_days", 14)),
    }


conn = sqlite3.connect("./plant_doctor_checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

builder = StateGraph(Plant)
builder.add_node("identify_species", identify_species)
builder.add_node("diagnose_issue", diagnose_issue)
builder.add_node("generate_questions", generate_questions)
builder.add_node("ask_clarifying", ask_clarifying)
builder.add_node("prescribe", prescribe)

builder.add_edge(START, "identify_species")
builder.add_edge("identify_species", "diagnose_issue")
builder.add_edge("diagnose_issue", "generate_questions")
builder.add_edge("generate_questions", "ask_clarifying")
builder.add_conditional_edges("ask_clarifying", route_after_clarifying)
builder.add_edge("prescribe", END)

graph = builder.compile(checkpointer=checkpointer)







