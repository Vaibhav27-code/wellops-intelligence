# Local Run & Video Recording Guide
**Asset Intelligence Copilot — FlytBase Hacktoberfest 2026**

This single guide covers everything you need to start the application locally, test all features, and follow a timed scene-by-scene script to record an impressive 3 to 5-minute video presentation.

---

## Part 1: Quick Local Setup & Launch

Open two terminal windows (PowerShell on Windows, or Bash on macOS/Linux).

### Terminal 1: Backend API (FastAPI)
```powershell
# Navigate to the repo root
cd d:\Hactoberfest

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# (Optional) Select LLM Provider:
# "rules" = 100% deterministic, ultra-fast, zero API key/token usage (ideal for recording!)
# "gemini" = Live Google Gemini 3.5 Flash Lite
$env:LLM_PROVIDER = "rules"

# Ingest dataset (if not already done)
python -m backend.app.ingest

# Start backend server
uvicorn backend.app.main:app --port 8000
```
> **Backend verification:** Open [http://localhost:8000/health](http://localhost:8000/health) in your browser. You should see `{"status":"ok","llm_provider":"rules",...}`.

---

### Terminal 2: Frontend UI (React + Vite)
```powershell
cd d:\Hactoberfest\frontend

# Start frontend dev server
npm run dev
```
> **Frontend verification:** Open [http://localhost:5173](http://localhost:5173) in your browser. You should see the dark industrial Operations Copilot dashboard.

---

## Part 2: 60-Second Pre-Recording Sanity Test

Run these quick checks before hitting "Record":
1. **User Picker:** Confirm top-left user dropdown shows 15 users (e.g. *Michael Turner*, *Jessica Reed*, *Laura Simmons*).
2. **Example Chips:** Confirm grouped chips appear above the chat input (Single Well, Area Analysis, Compliance, Memory & Corrections).
3. **Click a chip:** Click **Q1: WELL-0001 Status**. It should return a Status Card, calculation explanation, and citations within 1 second.
4. **View Selector:** Click the **Table** button on any chart response to verify interactive client-side view toggling.
5. **Copy as Markdown:** Hover over the response and click **Copy as Markdown**; verify the button changes to `✓ Copied!`.

---

## Part 3: Step-by-Step Video Recording Script (3 – 5 Minutes)

### Scene 1: Introduction & Architecture (0:00 – 0:45)
- **What to show on screen:** Open [http://localhost:5173](http://localhost:5173). Point your mouse at the top bar and the clean dark industrial interface.
- **What to say:**
  > "Hello! This is our **Asset Intelligence Copilot** for FlytBase Hacktoberfest 2026.
  >
  > In upstream oil & gas operations, field teams manage hundreds of complex wells. Operations data is scattered across sensor telemetry, maintenance work orders, regulatory spill reports, operating manuals, and human notes.
  >
  > The core architecture principle of this copilot is **zero hallucination on numbers**:
  > - All arithmetic—downtime days, spill reporting deadlines, and repair costs—is executed strictly by **deterministic Python code**, never by an LLM.
  > - Operating thresholds are dynamically extracted from raw Markdown manuals and SOPs (e.g., T200 15°C, T350 20°C, and 5-barrel spill thresholds).
  > - Every single metric carries clickable citations with exact source filenames, record IDs, and timestamps.
  > Let's walk through live scenarios."

---

### Scene 2: Live Fleet Analytics & Adaptive Visuals (0:45 – 2:00)
- **Action:** Select user **Michael Turner** (Production Engineer).
- **Prompt 1 (Click Chip Q1):** *"What is the current operational status of WELL-0001?"*
  - **What to show:** Point out the **Status Card** showing Offline / Non-Producing ($\Delta T = 3.2\,^\circ\text{C} < 15.0\,^\circ\text{C}$). Expand the **Citations Drawer** showing the raw inspection `INS-0001-0209` and planned shut-in note `CTX-0001-003`.
  - **What to say:** *"Notice that the copilot didn't just check sensor telemetry; it dynamically compared wellhead minus ambient temperature against the T200 manual threshold, and verified human context notes to identify an open rod-string shut-in."*

- **Prompt 2 (Click Chip Q3):** *"Show the 13-week temperature trend for WELL-0001."*
  - **What to show:** Highlight the interactive **Line Chart** plotting Wellhead vs Ambient temperature over the 13-week window.
  - **Demonstrate the View Selector:** Click the **Table** toggle to show the raw data table, then switch back to **Line Chart**.

- **Prompt 3 (Click Chip Q6):** *"Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months?"*
  - **What to show:** Show the **Bar Chart** ranking the top 3 wells (WELL-0121: 49 days, WELL-0107: 42 days, WELL-0138: 42 days).
  - **What to say:** *"Here, each weekly offline inspection deterministically accumulates 7 days of downtime under SOP rules."*

- **Prompt 4 (Click Chip Q7):** *"Show all spills in Northeast Block 8 in the last 90 days on a map."*
  - **What to show:** The **Leaflet Map** rendering real SVG pins for the 4 spill locations with popup volumes and dates.

---

### Scene 3: Two-Level Memory & Privacy Isolation (2:00 – 3:00)
- **What to explain:** Explain the dual memory layer: **Shared Audited Operational Memory** vs. **Strict Private Conversation Memory**.
- **Action:**
  1. While logged in as **Michael Turner**, click **Q11: Memory Recall** (*"For the three wells we discussed yesterday, what have repairs cost this year?"*).
  2. The copilot recalls Michael's 3 previously discussed wells (WELL-0138, WELL-0121, WELL-0107) and calculates total 2026 repair costs: **$77,912** with work order citations.
  3. **Now switch User:** Change the top-left dropdown from **Michael Turner** to **Jessica Reed**.
  4. Notice the chat history resets cleanly. Click or paste the same question: *"For the three wells we discussed yesterday, what have repairs cost this year?"*
  5. The copilot responds that **no prior conversation exists for Jessica**.
- **What to say:**
  > "Notice the privacy guarantee: past queries, discussed assets, and session context are strictly isolated by user ID at the database layer. Zero data leaks across users."

---

### Scene 4: Audited Corrections & Global Propagation (3:00 – 4:00)
- **Action:**
  1. Click **Q13: Override Spill Volume** or open the **Submit Correction** modal.
  2. Input:
     - Well: `WELL-0151`
     - Field: `Spill Volume`
     - Original: `4.5`
     - Corrected: `5.4`
     - Reason: `Field crew physical re-measurement`
  3. Submit the correction.
  4. **What to show:**
     - Point out the response: The spill is dynamically re-classified from Non-Reportable (< 5 bbl) to **Reportable ($\ge 5\,\text{bbl}$)** under regulatory SOP-SR-01.
     - Open the **Audit Sidebar** (`GET /corrections`) to show the immutable audit entry (Author, Timestamp, Original vs Corrected Value, Reason, Evidence).
  5. **Switch user to Laura Simmons (Environmental Compliance Lead):**
     - Query 90-day spills in NE Block 8. Laura Simmons immediately sees WELL-0151 as a reportable release citing Michael Turner's audited correction.

---

### Scene 5: Conflict Handling & Copy as Markdown (4:00 – 4:45)
- **Action:**
  1. Click **Q18: Disagreements on AI Analysis** (*"Are there any open disagreements about recent spill assessments?"*).
  2. **What to show:** The **Conflict Alert Banner** displaying side-by-side conflicting evidence (Operator inspection notes vs Maintenance fluid analysis on WELL-0101).
  3. **What to say:** *"When human claims contradict physical telemetry or chemical analysis, our copilot never averages or silently overwrites facts. It highlights both claims side-by-side with citations."*
  4. Click **Copy as Markdown** on the response. Paste it into Notepad or terminal to show the clean Markdown export with table, calculation logic, and citations ready for report writing.

---

### Scene 6: Conclusion & Testing Proof (4:45 – 5:00)
- **What to show:** Switch briefly to terminal or show test results:
  - `75 passed in pytest` (100% test coverage including pandas oracle differential testing).
  - `0 errors in npm run build`.
- **Closing statement:**
  > "In summary, Asset Intelligence Copilot provides deterministic calculations, dynamic SOP extraction, two-level memory, and rich visual transparency. Thank you!"

---

## Part 4: Copy-Paste Cheat Sheet for Recording

| Demo Step | Suggested User | Prompt / Chip to Click | Expected Visual |
|---|---|---|---|
| **Step 1** | Michael Turner | Click **Q1: WELL-0001 Status** | Status Card (Offline, 3.2°C) |
| **Step 2** | Michael Turner | Click **Q3: 13-Wk Temp Trend** | Line Chart (Wellhead vs Ambient) |
| **Step 3** | Michael Turner | Click **Q6: Top Downtime Wells** | Bar Chart (Ranked 49, 42, 42 days) |
| **Step 4** | Michael Turner | Click **Q7: 90-Day Spills Map** | Leaflet Map (4 SVG location pins) |
| **Step 5** | Michael Turner | Click **Q8: 2026 Spills Heatmap** | Heatmap Matrix (Areas vs Months) |
| **Step 6** | Michael Turner | Click **Q11: Memory Recall** | Data Table ($77,912 total repair cost) |
| **Step 7** | Jessica Reed | Ask: *"For the three wells we discussed yesterday..."* | Clean "No prior history" privacy alert |
| **Step 8** | Michael Turner | Click **Q13: Override Spill Volume** | Audit alert + Promotion to Reportable |
| **Step 9** | Laura Simmons | Ask: *"Which spills in NE Block 8 were reportable in last 90 days?"* | Shows WELL-0151 (5.4 bbl, cited correction) |
| **Step 10** | Any User | Click **Q18: Disagreements on AI Analysis** | Side-by-side Conflict Banner |
