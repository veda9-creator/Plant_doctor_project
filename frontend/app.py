import base64
import json
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

import os
API = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Plant Doctor", page_icon="🌿", layout="wide")

def _img_to_base64(filename: str) -> str | None:
    path = Path(__file__).parent / filename
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode()

def set_login_background():
    b64 = _img_to_base64("bg_login.jpg")
    if b64:
        bg = f"url('data:image/jpeg;base64,{b64}')"
    else:
        bg = "linear-gradient(135deg, #1a472a 0%, #2d6a4f 40%, #52b788 100%)"
    st.markdown(f"""
    <style>
    .stApp {{
        background: {bg};
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    .stApp::before {{
        content: '';
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.45);
        z-index: 0;
    }}
    .stApp > * {{ position: relative; z-index: 1; }}
    .stApp * {{ color: white !important; }}
    .stTextInput input {{ color: black !important; background: white !important; }}
    .stTextInput label {{ color: black !important; }}
    .stTextInput label p {{ color: black !important; }}
    .stTextInput button {{ color: black !important; }}
    .stTextInput button svg {{ fill: black !important; stroke: black !important; }}
    .stTabs [data-baseweb="tab-list"] {{ background: rgba(255,255,255,0.15); border-radius: 8px; }}
    .stTabs [data-baseweb="tab"] {{ color: black !important; }}
    .stButton button {{ color: black !important; }}
    .stButton button p {{ color: black !important; }}
    </style>
    """, unsafe_allow_html=True)

def set_dashboard_background():
    b64 = _img_to_base64("bg_dashboard.jpg")
    if b64:
        bg = f"url('data:image/jpeg;base64,{b64}')"
    else:
        bg = "linear-gradient(160deg, #f0faf4 0%, #d8f3dc 50%, #e8f5e9 100%)"
    st.markdown(f"""
    <style>
    .stApp {{
        background: {bg};
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    .stApp::before {{
        content: '';
        position: fixed;
        inset: 0;
        background: rgba(255,255,255,0.55);
        z-index: 0;
    }}
    .stApp > * {{ position: relative; z-index: 1; }}
    </style>
    """, unsafe_allow_html=True)

CATEGORY_EMOJI = {
    "water": "💧",
    "light": "☀️",
    "pest": "🐛",
    "nutrient": "🌱",
    "disease": "🦠",
    "healthy": "✅",
}

STATUS_BADGE = {
    "healthy":    ("🟢", "Healthy"),
    "recovering": ("🟡", "Recovering"),
    "critical":   ("🔴", "Critical"),
    "unknown":    ("⚪", "Unknown"),
}

PROGRESS_COLOR = {
    "improving": "green",
    "stable":    "orange",
    "worsening": "red",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def token() -> str | None:
    return st.session_state.get("token")


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {token()}"}


def api_get(path: str):
    return requests.get(f"{API}{path}", headers=auth_headers())


def api_post(path: str, **kwargs):
    return requests.post(f"{API}{path}", **kwargs)


def _detail(resp) -> str:
    """Extract error detail from a non-ok response, safely."""
    try:
        return resp.json().get("detail", "") or resp.text or f"HTTP {resp.status_code}"
    except Exception:
        return resp.text or f"HTTP {resp.status_code}"


def _save_photo(plant_id: int, file, note: str = "") -> dict | None:
    resp = requests.post(
        f"{API}/plants/{plant_id}/photos",
        data={"note": note},
        files={"file": (file.name, file.getvalue(), file.type)},
        headers=auth_headers(),
    )
    if resp.ok:
        return resp.json()
    st.error(f"Upload failed: {_detail(resp)}")
    return None


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

DEMO_EMAIL = "demo@plantdoctor.com"
DEMO_PASSWORD = "demo1234"

def _demo_login():
    api_post("/auth/register", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    resp = api_post("/auth/login", data={"username": DEMO_EMAIL, "password": DEMO_PASSWORD})
    if resp.ok:
        st.session_state["token"] = resp.json()["access_token"]
        st.rerun()

def page_login():
    set_login_background()
    col = st.columns([1, 2, 1])[1]
    with col:
        st.title("🌿 Plant Doctor")
        st.caption("Upload a photo. Get a diagnosis. Track recovery week over week.")
        st.divider()

        if st.button("🚀 Try Demo — no account needed", use_container_width=True, type="primary"):
            _demo_login()

        st.divider()

        tab_login, tab_register = st.tabs(["Log in", "Create account"])

        with tab_login:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pw")
            if st.button("Log in", use_container_width=True):
                resp = api_post("/auth/login", data={"username": email, "password": password})
                if resp.ok:
                    st.session_state["token"] = resp.json()["access_token"]
                    st.rerun()
                else:
                    st.error(_detail(resp) or "Login failed")

        with tab_register:
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_pw")
            if st.button("Create account", use_container_width=True):
                resp = api_post("/auth/register", json={"email": email, "password": password})
                if resp.ok:
                    st.success("Account created — log in above")
                else:
                    st.error(_detail(resp) or "Registration failed")


def page_dashboard():
    set_dashboard_background()
    st.title("My Plants")

    with st.sidebar:
        st.header("Add a plant")
        name = st.text_input("Nickname (e.g. 'Pothos in living room')")
        species = st.text_input("Species (optional — AI will identify from photo)")
        location = st.text_input("Location (e.g. 'north window')")
        if st.button("Add plant", use_container_width=True):
            resp = requests.post(
                f"{API}/plants",
                json={"name": name, "species": species or None, "location": location or None},
                headers=auth_headers(),
            )
            if resp.ok:
                st.success(f"Added {name}!")
                st.rerun()
            else:
                st.error(_detail(resp) or "Failed")

        st.divider()
        if st.button("Log out", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    resp = api_get("/plants")
    if not resp.ok:
        st.error(f"Could not load plants: {_detail(resp)}")
        return
    plants = resp.json()
    if not plants:
        st.info("No plants yet — add one in the sidebar to get started.")
        return

    cols = st.columns(3)
    for i, plant in enumerate(plants):
        with cols[i % 3]:
            with st.container(border=True):
                icon, label = STATUS_BADGE.get(plant.get("status", "unknown"), ("⚪", "Unknown"))
                st.subheader(f"{plant['name']}  {icon}")
                st.caption(label)
                if plant["species"]:
                    st.caption(f"*{plant['species']}*")
                if plant["location"]:
                    st.caption(f"📍 {plant['location']}")

                photo_resp = api_get(f"/plants/{plant['id']}/photos")
                photos = photo_resp.json() if photo_resp.ok else []
                if photos:
                    try:
                        st.image(photos[0]["filepath"], use_container_width=True)
                    except Exception:
                        st.caption("(photo preview unavailable)")
                else:
                    st.markdown("*No photos yet*")

                if st.button("Open plant", key=f"open_{plant['id']}", use_container_width=True):
                    st.session_state["active_plant"] = plant["id"]
                    st.rerun()


def page_plant(plant_id: int):
    resp = api_get(f"/plants/{plant_id}")
    if not resp.ok:
        st.error("Plant not found")
        return
    plant = resp.json()

    if st.button("← My Plants"):
        del st.session_state["active_plant"]
        st.session_state.pop(f"diag_{plant_id}", None)
        st.rerun()

    icon, label = STATUS_BADGE.get(plant.get("status", "unknown"), ("⚪", "Unknown"))
    st.title(f"{plant['name']}  {icon} {label}")
    if plant.get("species"):
        st.caption(f"*{plant['species']}*")
    if plant.get("location"):
        st.caption(f"📍 {plant['location']}")

    st.divider()
    tab_diagnose, tab_plan, tab_checkin, tab_gallery = st.tabs(
        ["🔍 Diagnose", "📋 Care Plan", "📅 Weekly Check-in", "🖼 Gallery"]
    )

    with tab_diagnose:
        _diagnose_tab(plant_id, plant)

    with tab_plan:
        _care_plan_tab(plant_id)

    with tab_checkin:
        _checkin_tab(plant_id)

    with tab_gallery:
        _gallery_tab(plant_id)


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------

def _diagnose_tab(plant_id: int, plant: dict):
    diag_key = f"diag_{plant_id}"
    diag = st.session_state.get(diag_key)

    # ---- AWAITING ANSWER ----
    if diag and diag.get("status") == "awaiting_answer":
        if diag.get("species"):
            st.info(f"**Species identified:** {diag['species']}")
        if diag.get("issue_category"):
            emoji = CATEGORY_EMOJI.get(diag["issue_category"], "🌿")
            st.warning(
                f"{emoji} **Issue detected:** {diag['issue_category']}  \n"
                f"{diag.get('issue_summary', '')}"
            )

        st.subheader(f"Question {diag['question_num']} of {diag['total_questions']}")
        st.write(f"**{diag['question']}**")

        answer = st.text_input("Your answer", key=f"ans_{diag['diagnosis_id']}_{diag['question_num']}")
        if st.button("Submit answer", use_container_width=True, type="primary"):
            if not answer.strip():
                st.warning("Please type an answer before submitting.")
            else:
                with st.spinner("Thinking..."):
                    r = requests.post(
                        f"{API}/diagnose/{diag['diagnosis_id']}/reply",
                        json={"answer": answer},
                        headers=auth_headers(),
                        timeout=120,
                    )
                if r.ok:
                    st.session_state[diag_key] = r.json()
                    st.rerun()
                else:
                    st.error(_detail(r) or "Error submitting answer")

        if st.button("Cancel", type="secondary"):
            st.session_state.pop(diag_key, None)
            st.rerun()

    # ---- COMPLETE ----
    elif diag and diag.get("status") == "complete":
        st.success("Diagnosis complete!")
        emoji = CATEGORY_EMOJI.get(diag.get("issue_category", ""), "🌿")
        st.subheader(f"{emoji} {(diag.get('issue_category') or 'Unknown').capitalize()} issue")
        st.write(diag.get("issue_summary", ""))
        st.info("Your care plan is ready — check the **Care Plan** tab.")
        if st.button("Start a new diagnosis"):
            st.session_state.pop(diag_key, None)
            st.rerun()

    # ---- UPLOAD FORM ----
    else:
        st.subheader("Upload a photo to diagnose")
        note = st.text_area("Describe what you see (optional but helps the AI)", key=f"dnote_{plant_id}")
        file = st.file_uploader("Plant photo", type=["jpg", "jpeg", "png", "webp"], key=f"dfile_{plant_id}")

        if file:
            st.image(file, caption="Preview", use_container_width=True)

        if file and st.button("Upload & Start Diagnosis", use_container_width=True, type="primary"):
            with st.spinner("Uploading..."):
                photo = _save_photo(plant_id, file, note)
            if not photo:
                return

            with st.spinner("AI is examining your plant (~15 seconds)..."):
                r = requests.post(
                    f"{API}/diagnose",
                    json={"plant_id": plant_id, "photo_id": photo["id"], "description": note},
                    headers=auth_headers(),
                    timeout=120,
                )
            if r.ok:
                st.session_state[diag_key] = r.json()
                st.rerun()
            else:
                st.error(f"Diagnosis failed: {_detail(r)}")


def _care_plan_tab(plant_id: int):
    resp = api_get(f"/plants/{plant_id}/care-plan")
    if resp.status_code == 404:
        st.info("No care plan yet — run a diagnosis first.")
        return
    if not resp.ok:
        st.error("Could not load care plan.")
        return

    plan = resp.json()
    if plan.get("expected_recovery_days"):
        st.caption(f"Expected recovery: **{plan['expected_recovery_days']} days**")

    done_count = sum(1 for item in plan.get("checklist_items", []) if item["done"])
    total_count = len(plan.get("checklist_items", []))
    if total_count:
        st.progress(done_count / total_count, text=f"{done_count}/{total_count} steps done")

    st.subheader("Recovery checklist")
    for item in plan.get("checklist_items", []):
        checked = st.checkbox(item["text"], value=item["done"], key=f"chk_{item['id']}")
        if checked != item["done"]:
            requests.patch(
                f"{API}/checklist/{item['id']}",
                json={"done": checked},
                headers=auth_headers(),
            )


def _checkin_tab(plant_id: int):
    # History
    checkin_resp = api_get(f"/plants/{plant_id}/checkins")
    checkins = checkin_resp.json() if checkin_resp.ok else []

    # Days since last check-in
    if checkins:
        last_date = datetime.fromisoformat(checkins[0]["created_at"].replace("Z", ""))
        days_ago = (datetime.utcnow() - last_date).days
        st.caption(f"Last check-in: **{days_ago} day(s) ago**")
    else:
        st.caption("No check-ins yet.")

    st.subheader("Upload this week's photo")
    file = st.file_uploader("New photo", type=["jpg", "jpeg", "png", "webp"], key=f"cifile_{plant_id}")
    if file:
        st.image(file, caption="New photo preview", use_container_width=True)

    if file and st.button("Submit Check-in", use_container_width=True, type="primary"):
        with st.spinner("Comparing photos and updating plan (~15 seconds)..."):
            r = requests.post(
                f"{API}/plants/{plant_id}/checkin",
                data={},
                files={"file": (file.name, file.getvalue(), file.type)},
                headers=auth_headers(),
                timeout=120,
            )
        if r.ok:
            result = r.json()
            progress = result.get("progress") or "stable"
            color = PROGRESS_COLOR.get(progress, "orange")
            st.markdown(
                f"<h3 style='color:{color}'>📊 {progress.capitalize()}</h3>",
                unsafe_allow_html=True,
            )
            st.write(f"**What changed:** {result.get('changes_observed', '')}")
            st.info(f"**Recommendation:** {result.get('recommendation', '')}")
            st.rerun()
        else:
            st.error(_detail(r) or "Check-in failed")

    # Show history
    if checkins:
        st.divider()
        st.subheader("Check-in history")
        for ci in checkins:
            progress = ci.get("progress") or "stable"
            color = PROGRESS_COLOR.get(progress, "orange")
            date_str = ci["created_at"][:10]
            with st.expander(f"{date_str}  —  :{color}[{progress.capitalize()}]"):
                if ci.get("prev_photo_id") and ci.get("new_photo_id"):
                    prev_resp = api_get(f"/plants/{plant_id}/photos")
                    all_photos = {p["id"]: p for p in (prev_resp.json() if prev_resp.ok else [])}
                    prev = all_photos.get(ci["prev_photo_id"])
                    new = all_photos.get(ci["new_photo_id"])
                    if prev and new:
                        c1, c2 = st.columns(2)
                        with c1:
                            try:
                                st.image(prev["filepath"], caption="Before", use_container_width=True)
                            except Exception:
                                st.caption("(before unavailable)")
                        with c2:
                            try:
                                st.image(new["filepath"], caption="After", use_container_width=True)
                            except Exception:
                                st.caption("(after unavailable)")

                st.write(f"**Changes:** {ci.get('changes_observed', '—')}")
                st.write(f"**Recommendation:** {ci.get('recommendation', '—')}")


def _gallery_tab(plant_id: int):
    photo_resp = api_get(f"/plants/{plant_id}/photos")
    photos = photo_resp.json() if photo_resp.ok else []
    if not photos:
        st.info("No photos yet.")
        return

    st.caption(f"{len(photos)} photo(s) — newest first")
    cols = st.columns(3)
    for j, photo in enumerate(photos):
        with cols[j % 3]:
            try:
                st.image(photo["filepath"], caption=photo["taken_at"][:10], use_container_width=True)
                if photo.get("note"):
                    st.caption(photo["note"])
            except Exception:
                st.caption("(unavailable)")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if not token():
    page_login()
elif "active_plant" in st.session_state:
    page_plant(st.session_state["active_plant"])
else:
    page_dashboard()