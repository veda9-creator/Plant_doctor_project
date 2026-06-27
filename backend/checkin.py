"""
Weekly check-in: compare two plant photos with a multi-image vision call.
Reuses the LLM helpers from agent.py — no code duplication.
"""

from datetime import datetime

try:
    from .agent import _b64, _chat, _parse_json
except ImportError:  # Allow running as `python checkin.py` or from backend folder
    from agent import _b64, _chat, _parse_json


def compare_photos(
    prev_path: str,
    new_path: str,
    care_plan_steps: list[str],
    days_since: int,
) -> dict:
    """
    Send both photos to the vision model in one call.
    Returns: {progress, changes_observed, recommendation}
    """
    steps_text = "\n".join(f"- {s}" for s in care_plan_steps) if care_plan_steps else "(no active care plan)"

    prompt = (
        f"You are a plant doctor doing a weekly progress check.\n\n"
        f"The owner has been following this care plan for {days_since} day(s):\n"
        f"{steps_text}\n\n"
        "The FIRST image is the BEFORE photo. The SECOND image is TODAY's photo.\n\n"
        "Assess the plant's progress:\n"
        "1. Is it improving, stable, or worsening?\n"
        "2. What specific visual changes do you notice between the two photos?\n"
        "3. Should the care plan be adjusted, and if so, how?\n\n"
        "Return JSON only:\n"
        '{"progress": "improving|stable|worsening", '
        '"changes_observed": "specific visual differences between the two photos", '
        '"recommendation": "continue current plan / specific adjustments needed"}'
    )

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": f"BEFORE photo ({days_since} day(s) ago):"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(prev_path)}"}},
            {"type": "text", "text": "TODAY's photo:"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(new_path)}"}},
            {"type": "text", "text": prompt},
        ],
    }]

    raw = _chat(messages, max_tokens=512)
    return _parse_json(raw)


def days_between(dt_a: datetime, dt_b: datetime) -> int:
    return max(1, abs((dt_b - dt_a).days))
