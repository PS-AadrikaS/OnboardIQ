"""
OnboardIQ - Streamlit Dashboard (Product Squads Enterprise Purple Edition)

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
UI_DIR = Path(__file__).resolve().parent

st.set_page_config(page_title="OnboardIQ | Product Squads AI Labs", page_icon="🧭", layout="wide")

# ---------- Custom Purple & White CSS Theme ----------
st.markdown("""
<style>
    /* Main Theme Colors */
    :root {
        --primary-purple: #6B46C1;
        --light-purple: #F3E8FF;
        --dark-purple: #4C1D95;
        --border-purple: #DDD6FE;
    }
    
    /* Headers & Title */
    h1, h2, h3 {
        color: #4C1D95 !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Buttons */
    .stButton>button {
        background-color: #6B46C1 !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button:hover {
        background-color: #5B21B6 !important;
        box-shadow: 0 4px 12px rgba(107, 70, 193, 0.3) !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #FAF5FF !important;
        border-right: 1px solid #E9D5FF !important;
    }
    
    /* Status Cards */
    div[data-testid="stMetricValue"] {
        color: #6B46C1 !important;
    }
    
    .status-card {
        background: white;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #E9D5FF;
        box-shadow: 0 2px 8px rgba(107, 70, 193, 0.05);
    }
    
    /* LinkedIn Badge */
    .linkedin-badge {
        background: #0077B5;
        color: white !important;
        padding: 6px 14px;
        border-radius: 20px;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        margin-top: 5px;
    }
    .linkedin-badge:hover {
        background: #005582;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)


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
    """
    <a href="https://www.linkedin.com/company/productsquads/" target="_blank" class="linkedin-badge">
        🔗 LinkedIn: Product Squads
    </a>
    <br/><br/>
    <a href="https://productsquads.co/" target="_blank" style="color: #6B46C1; font-weight: 600; text-decoration: none;">
        🌐 Visit Website: productsquads.co
    </a>
    """,
    unsafe_allow_html=True
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

# Display Product Squads AI Labs Banner
banner_path = UI_DIR / "product_squads_banner.jpg"
if banner_path.exists():
    st.image(str(banner_path), use_container_width=True)

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

# ---------- AI Product Video Showcase Section ----------
st.markdown("---")
st.markdown("### 🎬 Product Squads AI Overview Video")
st.caption("Learn how Product Squads builds autonomous enterprise AI agents.")

video_file = UI_DIR / "demo_video.mp4"
if video_file.exists():
    st.video(str(video_file))
else:
    st.info(
        "📹 **AI Video Showcase Placeholder**: Add your AI-generated mp4 video to `ui/demo_video.mp4` "
        "or replace this with your video URL using `st.video('https://your-video-url.mp4')`!"
    )

# ---------- Footer: Product Squads ----------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #4C1D95; font-size: 0.9rem; padding: 15px; background: #FAF5FF; border-radius: 10px; border: 1px solid #E9D5FF;'>
        🚀 Built for <b>Product Squads</b> Enterprise AI Solutions · 
        <a href='https://www.linkedin.com/company/productsquads/' target='_blank' style='color: #6B46C1; font-weight: 600;'>LinkedIn</a> · 
        <a href='https://productsquads.co/' target='_blank' style='color: #6B46C1; font-weight: 600;'>Website</a>
    </div>
    """,
    unsafe_allow_html=True
)
