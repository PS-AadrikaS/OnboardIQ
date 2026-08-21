"""
OnboardIQ - Streamlit Dashboard (Product Squads Enterprise Edition)

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

st.set_page_config(page_title="OnboardIQ | Product Squads", page_icon="🧭", layout="wide")


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
st.sidebar.caption("Powered by **Product Squads** AI Labs")

st.sidebar.markdown(
    "[🔗 Product Squads LinkedIn](https://www.linkedin.com/company/productsquads/)  \n"
    "[🌐 Visit Product Squads](https://productsquads.co/)"
)
st.sidebar.markdown("---")

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
st.caption("Product Squads Autonomous HR & IT Execution Engine")

# Ground-truth status cards
if run_clicked:
    st.session_state.run_result = None
    st.session_state.last_employee_id = employee_id

    with st.spinner("🤖 Autonomous Orchestrator running onboarding steps..."):
        try:
            result = run_async(run_onboarding(employee))
            st.session_state.run_result = result
            st.session_state.last_employee_id = employee_id
        except Exception as e:
            st.error(f"Run failed: {e}")
            st.info("Make sure GROQ_API_KEY is configured in your .env file.")

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

# ---------- Executive HR Overview & Timeline ----------

result = st.session_state.run_result

if result and st.session_state.last_employee_id == employee_id:
    missing_docs = status["documents"].get("missing_documents", [])

    if missing_docs:
        st.error(
            f"🔴 **Action Needed — Missing Compliance Paperwork**\n\n"
            f"The candidate has not submitted the following required legal forms: **{', '.join(missing_docs)}**.\n\n"
            f"Please collect signed paperwork to finalize onboarding."
        )
    elif result.status == "complete":
        st.success("🎉 **Automated Onboarding Complete**: Account created, software access granted, orientation & manager 1:1 scheduled!")

    st.markdown("### 📍 Milestone Timeline")

    for step in result.decision_log:
        action = step.get("action")
        res = step.get("result", {})

        if action == "provisioning__create_account":
            st.success(f"👤 **Account Created**: System ID `{res.get('account_id', 'created')}`")
        elif action == "provisioning__assign_access":
            access_str = ", ".join(res.get("access", [])) if isinstance(res, dict) and res.get("access") else "software access"
            st.success(f"🔑 **Software Access Assigned**: `{access_str}`")
        elif action == "scheduling__book_orientation":
            st.success(f"📅 **Orientation Booked**: `{res.get('date')} {res.get('slot')}`")
        elif action == "scheduling__book_manager_1on1":
            st.success(f"🤝 **Manager 1:1 Booked**: `{res.get('date')} {res.get('slot')}`")
        elif action == "compliance__check_document_status":
            if isinstance(res, dict) and res.get("missing_documents"):
                st.warning(f"📋 **Compliance Check**: Pending forms `{', '.join(res.get('missing_documents'))}`")
            else:
                st.success("📋 **Compliance Check**: All mandatory documents complete")

    # ---------- Agent Evaluation Metrics Section (At Bottom) ----------
    st.markdown("---")
    st.markdown("### 📊 Agent Evaluation Metrics")
    st.caption("Quantitative benchmark metrics evaluated automatically for this run.")

    eval_report = evaluate_run(result)

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Task Success Rate", f"{int(eval_report.task_success_rate * 100)}%")
    e2.metric("Tool Selection Accuracy", f"{int(eval_report.tool_selection_accuracy * 100)}%")
    e3.metric("Trajectory Accuracy", f"{int(eval_report.trajectory_accuracy * 100)}%")
    e4.metric("Conflict Recovery Rate", f"{int(eval_report.conflict_recovery_rate * 100)}%")

    e5, e6, e7, e8 = st.columns(4)
    e5.metric("Groundedness Score", f"{int(eval_report.groundedness_score * 100)}%")
    e6.metric("Latency", f"{eval_report.latency_seconds}s")
    e7.metric("Total Tokens", f"{eval_report.total_tokens:,}")
    e8.metric("Cheap Model Ratio", f"{int(eval_report.cheap_model_ratio * 100)}%")

    with st.expander("📋 View Evaluation Findings Audit"):
        for finding in eval_report.findings:
            st.markdown(f"• {finding}")
else:
    st.info("Click **▶️ Start Onboarding** in the sidebar to run the autonomous onboarding workflow.")

# ---------- Footer: Product Squads ----------
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748B; font-size: 0.85rem; padding: 10px;'>"
    "🚀 Built for <b>Product Squads</b> Enterprise AI Solutions · "
    "<a href='https://www.linkedin.com/company/productsquads/' target='_blank'>LinkedIn</a> · "
    "<a href='https://productsquads.co/' target='_blank'>Website</a>"
    "</div>",
    unsafe_allow_html=True
)
