"""
OnboardIQ - Streamlit Dashboard (HR Executive Edition)

Run with:  streamlit run ui/app.py
"""
import asyncio
import json
import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "orchestrator"))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from agent_loop import run_onboarding
from status import get_employee_status
from evaluator import evaluate_run

sys.path.insert(0, str(ROOT_DIR))
import reset_data

DATA_DIR = ROOT_DIR / "data"

st.set_page_config(page_title="OnboardIQ", page_icon="🧭", layout="wide")


# ---------- helpers ----------

def load_employees() -> dict:
    with open(DATA_DIR / "employees.json") as f:
        return json.load(f)


def run_async(coro):
    return asyncio.run(coro)


def status_badge(done: bool) -> str:
    return "✅ Done" if done else "⏳ Pending"


# ---------- session state ----------

if "run_result" not in st.session_state:
    st.session_state.run_result = None
if "last_employee_id" not in st.session_state:
    st.session_state.last_employee_id = None


# ---------- sidebar ----------

st.sidebar.title("🧭 OnboardIQ")
st.sidebar.caption("Agentic Multi-Agent Employee Onboarding")

employees = load_employees()
employee_id = st.sidebar.selectbox(
    "New hire",
    options=list(employees.keys()),
    format_func=lambda eid: f"{employees[eid]['name']} — {employees[eid]['role']}",
)
employee = employees[employee_id]

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Department:** {employee['department']}")
st.sidebar.markdown(f"**Start date:** {employee['start_date']}")
st.sidebar.markdown(f"**Manager:** {employee['manager']}")
st.sidebar.markdown("---")

run_clicked = st.sidebar.button("▶️ Start Onboarding", type="primary", use_container_width=True)
reset_clicked = st.sidebar.button("🔄 Reset Demo Data", use_container_width=True)

if reset_clicked:
    reset_data.main()
    st.session_state.run_result = None
    st.sidebar.success("Demo data reset.")


# ---------- main ----------

st.title("Employee Onboarding Dashboard")

if run_clicked:
    st.session_state.run_result = None
    st.session_state.last_employee_id = employee_id

    with st.spinner("🤖 Autonomous Orchestrator running onboarding steps..."):
        try:
            result = run_async(run_onboarding(employee))
            st.session_state.run_result = result
            st.session_state.last_employee_id = employee_id
            evaluate_run(result)
        except Exception as e:
            st.error(f"Run failed: {e}")
            st.info("Make sure GROQ_API_KEY is configured in your .env file.")

# Ground-truth status cards
status = run_async(get_employee_status(employee_id))

c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("🗂️ Provisioning")
    prov = status["provisioning"]
    st.write(f"Account created: {status_badge(prov['account_created'])}")
    st.write(f"Access assigned: {status_badge(prov['access_assigned'])}")
    if prov["access"]:
        st.caption("Access: " + ", ".join(prov["access"]))

with c2:
    st.subheader("📅 Scheduling")
    sched = status["schedule"]
    st.write(f"Orientation booked: {status_badge(sched['orientation_booked'])}")
    st.write(f"Manager 1:1 booked: {status_badge(sched['manager_1on1_booked'])}")
    for kind, info in sched["bookings"].items():
        st.caption(f"{kind}: {info['date']} {info['slot']}")

with c3:
    st.subheader("📋 Compliance")
    docs = status["documents"]
    st.write(f"All documents complete: {status_badge(docs['all_complete'])}")
    if docs["missing_documents"]:
        st.caption("Missing: " + ", ".join(docs["missing_documents"]))

st.markdown("---")

# ---------- Executive Summary & Timeline ----------

result = st.session_state.run_result

if result and st.session_state.last_employee_id == employee_id:
    status_color = {"complete": "green", "escalated": "orange", "max_iterations_reached": "red"}
    st.markdown(
        f"### Onboarding Status: :{status_color.get(result.status, 'gray')}[{result.status.upper()}]"
    )
    st.write(f"**Executive Summary:** {result.summary}")

    # --- Short Executive Banners ---
    if result.status == "escalated":
        st.warning(f"📋 **HR Action Required**: {result.summary}")
    elif result.status == "complete":
        st.success("🎉 **Automated Onboarding Complete**: All accounts, meetings, and compliance documents verified!")

    st.markdown("### 📍 Milestone Timeline")

    # Milestone filtering (showing key business milestones cleanly)
    milestones_shown = 0
    for step in result.decision_log:
        action = step.get("action")
        res = step.get("result", {})

        if action == "provisioning__create_account":
            st.success(f"👤 **Account Created**: System ID `{res.get('account_id', 'created')}`")
            milestones_shown += 1
        elif action == "provisioning__assign_access":
            access_str = ", ".join(res.get("access", [])) if isinstance(res, dict) and res.get("access") else "software access"
            st.success(f"🔑 **Software Access Assigned**: `{access_str}`")
            milestones_shown += 1
        elif action == "scheduling__check_calendar_conflicts" and isinstance(res, dict) and res.get("conflict"):
            st.warning(f"⚡ **Calendar Conflict Resolved**: Rescheduled busy slot `{res.get('date')} {res.get('slot')}` ({res.get('reason')})")
            milestones_shown += 1
        elif action == "scheduling__book_orientation":
            st.success(f"📅 **Orientation Booked**: `{res.get('date')} {res.get('slot')}`")
            milestones_shown += 1
        elif action == "scheduling__book_manager_1on1":
            st.success(f"🤝 **Manager 1:1 Booked**: `{res.get('date')} {res.get('slot')}`")
            milestones_shown += 1
        elif action == "compliance__check_document_status":
            if isinstance(res, dict) and res.get("missing_documents"):
                st.warning(f"📋 **Compliance Pending**: Missing `{', '.join(res.get('missing_documents'))}`")
            else:
                st.success("📋 **Compliance Passed**: All required documents complete")
            milestones_shown += 1
        elif action == "control__finish":
            st.success(f"✅ **Onboarding Finished**: {step.get('input', {}).get('summary', '')}")
            milestones_shown += 1
        elif action == "control__escalate":
            st.error(f"🚨 **Escalated to HR**: {step.get('input', {}).get('reason', '')}")
            milestones_shown += 1
else:
    st.info("Click **▶️ Start Onboarding** in the sidebar to run the autonomous onboarding workflow.")
