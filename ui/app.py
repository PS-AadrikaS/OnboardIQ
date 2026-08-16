"""
OnboardIQ - Streamlit Dashboard

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

from agent_loop import run_onboarding, CHEAP_MODEL, EXPENSIVE_MODEL
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
st.sidebar.caption("Agentic multi-agent employee onboarding")

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
    st.sidebar.success("Data reset.")

st.sidebar.markdown("---")
st.sidebar.caption(f"Cheap model: `{CHEAP_MODEL}`")
st.sidebar.caption(f"Escalation model: `{EXPENSIVE_MODEL}`")


# ---------- main ----------

st.title("Employee Onboarding Dashboard")

# Main 3-Column Layout: Left = Main Dashboard (74%), Middle = Spacer (6%), Right = Live Agent Observability Panel (20% right margin)
col_left, _, col_right = st.columns([3.4, 0.3, 1.1])

with col_right:
    st.markdown("#### 📡 Live Agent Observability Stream")
    obs_placeholder = st.empty()
    if not st.session_state.run_result:
        obs_placeholder.info("🤖 **Standing By**: Click **Start Onboarding** to stream live agent activity.")

if run_clicked:
    st.session_state.run_result = None
    st.session_state.last_employee_id = employee_id

    with col_right:
        obs_placeholder.info("🤖 **Orchestrator Started**: Initializing Supervisor-Worker loop with Groq...")

        def on_live_step(step_entry):
            action = step_entry.get("action", "")
            res = step_entry.get("result", {})
            iter_num = step_entry.get("iteration")
            
            if "provisioning" in action:
                agent_name = "🗂️ Provisioning Server"
            elif "scheduling" in action:
                agent_name = "📅 Scheduling Server"
            elif "compliance" in action:
                agent_name = "📋 Compliance Server"
            else:
                agent_name = "🧠 Orchestrator Agent"

            obs_placeholder.markdown(
                f"<div style='font-size: 0.85rem; line-height: 1.4; background: #F8FAFC; padding: 10px; border-radius: 8px; border: 1px solid #E2E8F0;'>"
                f"<b>Step {iter_num}</b> · <b>{agent_name}</b><br/>"
                f"• <b>Tool Called</b>: <code>{action}</code><br/>"
                f"• <b>Reasoning</b>: {step_entry.get('reasoning', 'Taking next step.')}<br/>"
                f"• <b>Observed Output</b>: <code>{json.dumps(res)}</code>"
                f"</div>",
                unsafe_allow_html=True
            )

        try:
            result = run_async(run_onboarding(employee, step_callback=on_live_step))
            st.session_state.run_result = result
            st.session_state.last_employee_id = employee_id
            obs_placeholder.success("🎉 **Stream Complete**: All onboarding steps executed!")
        except Exception as e:
            st.error(f"Run failed: {e}")
            st.info(
                "Make sure GROQ_API_KEY is set (see .env.example) and that "
                "you have network access to the Groq API."
            )


with col_left:
    # Always show current ground-truth status (works even before any run)
    status = run_async(get_employee_status(employee_id))

    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("🗂️ Provisioning")
        prov = status["provisioning"]
        st.write(f"Account created: {status_badge(prov['account_created'])}")
        st.write(f"Access assigned: {status_badge(prov['access_assigned'])}")
        if prov["access"]:
            st.caption("Access granted: " + ", ".join(prov["access"]))

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

    # ---------- run result: decision log + cost tracker ----------

    result = st.session_state.run_result

    if result and st.session_state.last_employee_id == employee_id:
        status_color = {"complete": "green", "escalated": "orange", "max_iterations_reached": "red"}
        st.markdown(
            f"### Onboarding Status: :{status_color.get(result.status, 'gray')}[{result.status.upper()}]"
        )
        st.write(f"**Executive Summary:** {result.summary}")

        # --- Non-Technical HR Callout Banners ---
        conflicts_found = []
        missing_docs_found = []

        for step in result.decision_log:
            res = step.get("result", {})
            if isinstance(res, dict):
                if res.get("conflict"):
                    conflicts_found.append({
                        "date": res.get("date"),
                        "slot": res.get("slot"),
                        "reason": res.get("reason", "Slot busy")
                    })
                if res.get("missing_documents"):
                    missing_docs_found = res.get("missing_documents")

        if conflicts_found:
            st.warning(
                "⚡ **Automatic Conflict Resolution Triggered!**\n\n"
                + "\n".join([f"• **Meeting Conflict**: Slot `{c.get('date', '')} {c.get('slot', '')}` was busy ({c.get('reason', 'Busy')}). The system automatically reflected and rescheduled orientation to a free slot!" for c in conflicts_found])
            )

        if result.status == "escalated":
            st.info(
                "📋 **HR Action Required**\n\n"
                + f"• **Pending Action**: {result.summary}"
            )
        elif result.status == "complete":
            st.success("🎉 **Automated Onboarding Complete**: All accounts, role access, meetings, and compliance documents have been fully verified!")

        st.markdown("---")

        tab_timeline, tab_eval, tab_log, tab_cost = st.tabs(["📍 HR Onboarding Timeline", "📊 Agent Evaluation Metrics", "🧠 Technical Decision Log", "💰 Cost & Token Metrics"])

        with tab_timeline:
            st.caption("Clean, human-readable timeline for HR managers (No technical jargon).")
            
            for step in result.decision_log:
                action = step.get("action")
                res = step.get("result", {})

                if action == "provisioning__create_account":
                    st.success(f"**Step {step['iteration']}** · 👤 **Created System Account** [PASSED] — System ID `{res.get('account_id', 'created')}` generated successfully.")
                elif action == "provisioning__assign_access":
                    access_str = ", ".join(res.get("access", [])) if isinstance(res, dict) and res.get("access") else "role software access"
                    st.success(f"**Step {step['iteration']}** · 🔑 **Assigned Software Access** [PASSED] — Granted permissions for `{access_str}`.")
                elif action == "scheduling__check_calendar_conflicts":
                    if isinstance(res, dict) and res.get("conflict"):
                        st.warning(f"**Step {step['iteration']}** · ⚡ **Calendar Conflict Detected** [CONFLICT] — Slot `{res.get('date')} {res.get('slot')}` was unavailable due to *{res.get('reason')}*. System is finding a free slot...")
                    else:
                        st.info(f"**Step {step['iteration']}** · 🔍 **Checked Calendar Slot** [AVAILABLE] — Confirmed slot `{res.get('date')} {res.get('slot')}` is open.")
                elif action == "scheduling__book_orientation":
                    st.success(f"**Step {step['iteration']}** · 📅 **Booked Orientation Meeting** [PASSED] — Confirmed for `{res.get('date')} {res.get('slot')}`.")
                elif action == "scheduling__book_manager_1on1":
                    st.success(f"**Step {step['iteration']}** · 🤝 **Booked Manager 1:1 Meeting** [PASSED] — Confirmed for `{res.get('date')} {res.get('slot')}`.")
                elif action == "compliance__check_document_status":
                    if isinstance(res, dict) and res.get("missing_documents"):
                        st.info(f"**Step {step['iteration']}** · 📋 **Compliance Document Check** [ACTION NEEDED] — Pending forms: `{', '.join(res.get('missing_documents'))}`.")
                    else:
                        st.success(f"**Step {step['iteration']}** · 📋 **Compliance Document Check** [PASSED] — All mandatory onboarding forms are complete!")
                elif action == "control__finish":
                    st.success(f"**Step {step['iteration']}** · ✅ **Onboarding Complete** [FINISHED] — {step.get('input', {}).get('summary', '')}")
                elif action == "control__escalate":
                    st.error(f"**Step {step['iteration']}** · 🚨 **Escalated to HR Review** [ACTION REQUIRED] — Reason: {step.get('input', {}).get('reason', '')}")

        with tab_eval:
            st.caption("Quantitative benchmark metrics evaluating agent goal completion, tool selection, trajectory, conflict recovery, groundedness, and latency.")
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

            st.markdown("#### 📋 Evaluation Audit Findings")
            for finding in eval_report.findings:
                st.markdown(f"• {finding}")

        with tab_log:
            st.caption("Technical execution log for developers & reviewers showing raw reasoning, function parameters, and JSON outputs.")
            for step in result.decision_log:
                with st.expander(f"Step {step['iteration']} — {step['action']}  ·  model: {step['model']}"):
                    if step.get("reasoning"):
                        st.markdown(f"**Reasoning:** {step['reasoning']}")
                    if step.get("input"):
                        st.markdown("**Input:**")
                        st.json(step["input"])
                    if "result" in step:
                        st.markdown("**Result:**")
                        st.json(step["result"]) if isinstance(step["result"], dict) else st.write(step["result"])

        with tab_cost:
            cheap_calls = [c for c in result.cost_log if c["model"] == CHEAP_MODEL]
            expensive_calls = [c for c in result.cost_log if c["model"] == EXPENSIVE_MODEL]
            total_in = sum(c["input_tokens"] for c in result.cost_log)
            total_out = sum(c["output_tokens"] for c in result.cost_log)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total LLM calls", len(result.cost_log))
            m2.metric("Cheap-model calls", len(cheap_calls))
            m3.metric("Escalated calls", len(expensive_calls))
            m4.metric("Total tokens", f"{total_in + total_out:,}")

            st.caption(
                f"{len(cheap_calls)}/{len(result.cost_log)} steps "
                f"({round(100 * len(cheap_calls) / max(len(result.cost_log), 1))}%) "
                "were handled without ever needing the stronger, more expensive model."
            )

            st.markdown("**Per-call breakdown**")
            st.dataframe(result.cost_log, use_container_width=True)
    else:
        st.info("Click **Start Onboarding** in the sidebar to run the agent for this employee.")
