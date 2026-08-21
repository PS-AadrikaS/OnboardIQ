# OnboardIQ

**A Goal-Based Autonomous Employee Onboarding Agent System**, built with FastMCP, Groq open-weights agent loop, and a Streamlit dashboard.

Give it one goal — *"onboard this new hire"* — and a goal-based orchestrator agent autonomously plans and executes the entire onboarding process across three specialist agents (Provisioning, Scheduling, Compliance), each running as its own MCP server. It only escalates to a human when something genuinely needs judgment or legal signatures.

See `onboardiq_master_documentation.md` for the master design write-up (use case, architecture, agent taxonomy, cost-reduction techniques explained in plain language).

---

## Architecture at a glance

```
User goal ("onboard EMP001")
        │
        ▼
Orchestrator Agent  (goal-based, Reason → Act → Observe loop)
        │
   ┌────┼─────────────────┐
   ▼    ▼                 ▼
Provisioning   Scheduling    Compliance
MCP Server     MCP Server    MCP Server
(accounts,     (orientation, (documents,
 access)        1:1 booking)  checklist)
```

- **Architecture:** 1 Goal-Based Autonomous Orchestrator Agent coordinating 3 specialist FastMCP tool servers (Provisioning, Scheduling, Compliance).
- **3 self-built MCP servers** (FastMCP), each backed by mock JSON "systems" that behave like a real IT directory, calendar, and HR document tracker.
- **Cost reduction, 3 techniques:**
  1. Deterministic tool calls (create account, book slot, update checklist) cost zero LLM tokens — the LLM is only used to *decide what to do next*.
  2. Cheap model (`openai/gpt-oss-20b`) handles routine steps; only escalates to a stronger model (`openai/gpt-oss-120b`) after a real failure/conflict.
  3. The agent's working memory is a small structured message history, not a growing transcript — so cost per step stays flat regardless of how long a run takes.

---

## Prerequisites

Before you start, make sure you have:

1. **Python 3.10 or newer** — check with:
   ```bash
   python --version
   ```
2. **pip** (comes with Python)
3. **Git** (to clone the repo)
4. **A Groq API key** — get a free key at [console.groq.com/keys](https://console.groq.com/keys). Required to run the orchestrator (the dashboard's status panels work without it, but "Start Onboarding" needs it).
5. (Recommended) A terminal comfortable with virtual environments — the steps below use one.

---

## Step-by-step setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd onboardiq
```

### 2. Create and activate a virtual environment

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

You should see `(venv)` appear at the start of your terminal prompt.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your API key

```bash
cp .env.example .env
```

Open `.env` in a text editor and replace `gsk_your_groq_api_key_here` with your real Groq API key:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. Verify the MCP servers work (optional but recommended)

This checks the 3 MCP servers independently — no API key or cost involved:

```bash
python test_servers.py
```

You should see each server list its tools and return successful results.

### 6. Run the dashboard

```bash
streamlit run ui/app.py
```

This opens automatically in your browser (usually `http://localhost:8501`). From there:
- Pick a new hire from the sidebar dropdown
- Click **Start Onboarding** to run the orchestrator live
- Watch the **📡 Live Agent Observability Stream** on the right side
- Read the **📍 HR Onboarding Timeline** tab for clean English status badges (`[PASSED]`, `[CONFLICT]`, `[ACTION NEEDED]`)
- Inspect the **🧠 Technical Decision Log** tab to see raw reasoning steps and tool calls
- Check the **💰 Cost & Token Metrics** tab to see model usage and token breakdown

### 7. (Alternative) Run from the command line

If you just want to see it run without the UI:

```bash
python orchestrator/run_onboarding.py EMP001
```

Replace `EMP001` with any employee ID from `data/employees.json` (`EMP001`, `EMP002`, `EMP003`).

### 8. Reset demo data between runs

Onboarding actions (account creation, bookings) persist to the JSON data files. Before re-running a demo from a clean state:

```bash
python reset_data.py
```

Or click **Reset Demo Data** in the sidebar of the Streamlit app.


---

## Project structure

```
onboardiq/
├── data/                       # Mock "systems" (JSON files act as databases)
│   ├── employees.json          #   new-hire records
│   ├── calendar.json           #   existing bookings / conflicts
│   ├── checklist.json          #   required documents per department
│   └── provisioning_state.json #   account/access records
├── mcp_servers/
│   ├── storage.py              # shared JSON read/write helper
│   ├── provisioning_server.py  # MCP server: accounts & access
│   ├── scheduling_server.py    # MCP server: orientation & 1:1 booking
│   └── compliance_server.py    # MCP server: document checklist
├── orchestrator/
│   ├── mcp_hub.py               # connects to all 3 MCP servers as one tool set
│   ├── agent_loop.py            # the Reason→Act→Observe orchestrator loop
│   ├── status.py                # reads ground-truth status (no LLM, free)
│   └── run_onboarding.py        # CLI entry point
├── ui/
│   └── app.py                   # Streamlit dashboard
├── test_servers.py              # sanity check for the 3 MCP servers
├── reset_data.py                # resets mock data to initial demo state
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ANTHROPIC_API_KEY is not set` | Make sure you created `.env` from `.env.example` and it's in the project root (not inside `orchestrator/`). |
| `ModuleNotFoundError` | Make sure your virtual environment is activated and `pip install -r requirements.txt` completed without errors. |
| Streamlit opens but status panels error out | Run `python test_servers.py` first to confirm the MCP servers work independently of the dashboard. |
| Want a clean slate before a demo | Run `python reset_data.py`. |
| Orchestrator seems "stuck" | It has a 15-step iteration cap and will report `max_iterations_reached` rather than loop forever — check the Decision Log tab to see what it was doing. |

---

## Notes for evaluation / review

- All external "systems" (IT directory, calendar, HR platform) are mocked via local JSON files by design, so the demo is self-contained and doesn't depend on third-party accounts or credentials. The MCP server interfaces are written so a real API could be substituted later without changing any tool signatures.
- Sample employee data is entirely synthetic.
- The decision log recorded on each run is the evidence that the orchestrator is reasoning step-by-step rather than following a fixed script — worth walking through live during a review.
