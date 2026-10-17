# Asset Intelligence Copilot: Architecture & Evaluation Write-Up

**FlytBase Hacktoberfest 2026**  
**Author:** Asset Intelligence Team  
**Date:** 17 October 2026  

---

# Page 1: System Design & Architecture

### 1. Overview & Core Philosophy
The **Asset Intelligence Copilot** provides engineering-grade decision support across fleets of oil and gas assets (~200 wells). Industrial operators cannot tolerate hallucinations, silent data overwrites, or opaque arithmetic. We designed the copilot with three strict guarantees:
1. **Deterministic Arithmetic:** All downtime calculations, spill reporting deadlines, containment thresholds, and maintenance expenditures are computed strictly in deterministic Python code; the LLM never performs math.
2. **Dynamic Manual/SOP Thresholds:** Thresholds (e.g., T200 wellhead $\Delta T \ge 15.0\,^\circ\text{C}$, T350 wellhead $\Delta T \ge 20.0\,^\circ\text{C}$, spill reporting $\ge 5\,\text{bbl}$ in 24 hours) are extracted dynamically from raw markdown manuals and SOPs rather than hardcoded.
3. **Transparent Provenance & Conflict Reporting:** Every answer cites the source file, record ID, and excerpt. Conflicting field observations, telemetry, or user claims are highlighted rather than smoothed over.

---

### 2. Storage, Indexing & Retrieval
- **Structured SQLite Engine (`data/asset_intelligence.db`):** 
  - Ingests structured and semi-structured assets: `wells` (200 rows), `inspections` (39,567 rows), `maintenance` (5,665 rows), and `regulatory_events` (90 rows).
  - Fast B-tree indices on `(well_id, inspected_at)`, `(area_id)`, and `(well_id, completed_at)` enable sub-10ms query execution across 45,000+ records.
- **Unstructured SQLite FTS5 Full-Text Search:**
  - Ingests 1,514 markdown maintenance reports, engineering manuals, standard operating procedures (SOPs), and human context notes.
  - Tokenized with Porter stemming for rapid discovery of root-cause analyses, workover notes, and containment timelines.
- **Audited Corrections & Knowledge Storage:**
  - `corrections`: Stores field re-measurements and volume adjustments with full audit metadata (`author`, `timestamp`, `reason`, `original_value`, `corrected_value`, `evidence`). Raw records remain immutable.
  - `shared_notes`: Global operational notes visible across all users.
  - `private_messages`: Per-user conversation history keyed by `user_id`, strictly isolated at the database layer.

---

### 3. Tool Pipeline & Execution Flow
```
User Question
    │
    ▼
LLM / Rules Intent Classifier & Entity Extractor (well_ids, area, time window, task)
    │
    ▼
Deterministic Tool Selection (wells, downtime, spills, repairs, compliance, memory)
    │
    ▼
Data Retrieval (SQLite indexed queries + FTS5 manual/note search)
    │
    ▼
Deterministic Python Calculation Engine (rules.py, downtime.py, compliance.py)
    │
    ▼
Evidence Assembly & Conflict Checker (telemetry vs human context vs audit log)
    │
    ▼
LLM Answer Synthesizer (Natural language wording + mandatory citations)
    │
    ▼
Visualization Generator (Card, Table, Line Chart, Bar Chart, Map, Heatmap)
    │
    ▼
FastAPI JSON Response → React + Vite Industrial Ops UI
```

---

### 4. Two-Level Memory & Conflict Transparency
- **Shared Audited Memory:** When an engineer corrects an erroneous sensor reading (e.g., WELL-0164 wellhead temperature re-measured from 24 °C to 41 °C) or overrides a spill classification (e.g., WELL-0151 adjusted from 4.5 to 5.4 bbl), the change immediately updates ground truth across all users while keeping the raw file untouched.
- **Strict Private Memory Isolation:** Past queries and discussed assets are stored with the active `user_id`. When User A asks about *"the wells we discussed yesterday,"* User A receives their specific asset context; User B asking the exact same question receives a polite notice that no prior conversation exists.
- **Handling Conflicting Evidence:** When telemetry contradicts a user's verbal claim (e.g., user claims a well is running, but telemetry shows $\Delta T < 1.0\,^\circ\text{C}$), the copilot does not overwrite facts. It flags the statement as an *Unconfirmed Claim*, presents the sensor telemetry, and invites an audited correction with physical evidence.

---

### 5. Format-Driven Idempotent Ingestion & Test Data Readiness
The ingestion engine (`backend/app/ingest/loader.py`) operates dynamically:
- Automatically crawls and parses any conforming dataset directory structure (`assets/WELL-XXXX/`, `fleet/well-types/`, `fleet/sops/`).
- Idempotent execution: running the ingestion script repeatedly drops and rebuilds tables transactionally, producing identical row counts without duplication.
- Unseen test datasets dropped into the directory load seamlessly with zero code modifications.

---

### 6. Models, Latency & Cost Optimization
- **Primary LLM Tier:** High-speed inference using Google Gemini 2.5 Flash / OpenAI GPT-4o-mini / local Ollama (`gemma4`).
- **Cost Reduction:** Exact prompt caching via SQLite cache table (`llm_cache.db`). Deterministic intent extraction falls back to an offline rule-based parser if LLM quota is exhausted or network fails, guaranteeing 100% uptime at $0 inference cost for standard operational questions.

---

# Page 2: Benchmark Evaluation Results & Findings

### 1. Official Evaluation Suite (Q1 – Q18) Performance Matrix

| Query | Topic | Visual Output | Verification & Ground Truth | Status |
|---|---|---|---|:---:|
| **Q1** | WELL-0001 Current Status | **Status Card** | Non-producing ($\Delta T = 3.2\,^\circ\text{C} < 15.0\,^\circ\text{C}$ limit). Inspected 15 Oct 2026 by Ryan Brooks. Planned rod string shut-in noted in `CTX-0001-003`. | **PASS** |
| **Q2** | Non-Producing Wells in NE Block 8 | **Data Table** | 4 wells: WELL-0164, WELL-0170, WELL-0172, WELL-0175. Cites open work orders and sensor deltas without inventing unrecorded causes. | **PASS** |
| **Q3** | WELL-0001 13-Week Temperature Trend | **Line Chart** | 13 weekly points (23 Jul – 15 Oct 2026) plotting wellhead vs ambient temperature; highlights offline status in final two weeks. | **PASS** |
| **Q4** | WELL-0001 4-Year Spill History | **Data Table** | 6 confirmed spills totaling 15.1 bbl. Correctly filters out rainwater false positive `INS-0001-0070` cited in `CTX-0001-001`. | **PASS** |
| **Q5** | WELL-0001 Calendar Year 2025 Downtime | Text + Citations | 21 downtime days from 3 non-producing inspections (24 Jul, 16 Oct, 23 Oct 2025; $3 \times 7 = 21$ days). | **PASS** |
| **Q6** | Top Downtime Wells in NE Block 7 (4 Mos) | **Bar Chart** | Ranked: 1. WELL-0121 (49 days, T200), 2. WELL-0107 (42 days, T350), 3. WELL-0138 (42 days, T350). | **PASS** |
| **Q7** | 90-Day Spills in NE Block 8 | **Map** | Maps 4 real spills with exact pad coordinates: WELL-0151 (4.5 bbl), WELL-0165 (1.2 bbl), WELL-0175 (3.9 bbl), WELL-0186 (0.6 bbl). | **PASS** |
| **Q8** | 2026 Spills by Area and Month | **Heatmap** | Complete matrix across 4 areas and 10 months. Excludes false positives; aggregates verified releases. | **PASS** |
| **Q9** | WELL-0001 Regulatory Compliance | **Data Table** | Identifies 4 violations from 11 Jun 2026 spill (SR-01, SR-02, SR-03, RC-04). Highlights open flowline RCA and missing shut-in notice. | **PASS** |
| **Q10** | Spills Exceeding 4h Containment Limit | **Data Table** | 2 spills in SW Block 24: WELL-0082 (~7.1 h) and WELL-0100 (~8.1 h) parsed from maintenance work orders. | **PASS** |
| **Q11** | Conversation Memory Recall | **Data Table** | Recalls 3 wells discussed yesterday by Michael Turner; calculates 2026 maintenance costs: WELL-0138 ($46,942), WELL-0121 ($25,794), WELL-0107 ($5,176). | **PASS** |
| **Q12** | Telemetry Correction & Re-Query | Table + Alert | Updates WELL-0164 temp to 41.0 °C; flags conflict with "Pump jack not moving"; re-querying Q2 excludes WELL-0164 (leaving 3 non-producing wells). | **PASS** |
| **Q13** | AI Volume Correction & Re-Classification | Response | Corrects WELL-0151 from 4.5 to 5.4 bbl. Dynamically promotes to reportable spill ($\ge 5\,\text{bbl}$), triggering 24h SR-01 reporting. | **PASS** |
| **Q14** | Well-Type Rule Override (Scoped) | **Data Table** | Sets T350 pump jack RCA threshold to 2 repairs. Adds WELL-0120 (T350 with 2 repairs), but excludes WELL-0102 (T200 with 2 repairs). | **PASS** |
| **Q15** | Shared Correction Propagation | Response | Jessica Reed sees WELL-0164 producing (from Turner's correction). Laura Simmons sees WELL-0151 as the sole reportable spill in NE-8. | **PASS** |
| **Q16** | Shared Notes vs Private Memory Isolation | Response | Shared note for WELL-0007 visible to all; Jessica Reed asking about Turner's discussed wells receives clean zero-leakage notice. | **PASS** |
| **Q17** | Handling Conflicting Statements | Response | Confirms cold telemetry for WELL-0175 and WELL-0001; flags user claims of normal operation as unconfirmed claims without overwriting ground truth. | **PASS** |
| **Q18** | Disagreements on AI Analysis | Response | Identifies 20 Aug spill dispute on WELL-0101 (produced water vs crude). Confirms executed repair MNT-0101-029 and documents the open dispute. | **PASS** |

---

### 2. What Worked
- **Decoupled Deterministic Calculation Engine:** Treating business logic as pure Python functions with automated unit tests eliminated calculation drift and hallucinated dates or costs.
- **Dynamic SOP Extraction:** Parsing regex rules directly from markdown SOPs ensured adaptability when operational limits changed.
- **Two-Level Memory Design:** Partitioning shared audited corrections from private chat history gave field teams collaborative accuracy while preserving confidential inquiry privacy.
- **Interactive Visual Generation:** Providing structured JSON visual specifications (`card`, `table`, `line`, `bar`, `map`, `heatmap`) with responsive table view-switchers ensured field operators could immediately inspect raw tabular data or graphical trends.

---

### 3. Edge Cases Encountered & Lessons Learned
- **Markdown Text Formatting Variability:** In `T350.md`, a newline separated `"above"` and `"ambient"`, requiring whitespace-agnostic regexes (`\s+` instead of literal spaces).
- **Nested JSON Fields:** Maintenance costs were nested under `cost_usd: {"labor": ..., "parts": ..., "total": ...}` rather than top-level floats.
- **Negative & Positive Invalidation Contexts:** Filtering false positive spills required checking both inspection remarks and linked context notes (`CTX-XXXX-XXX`) for retraction terms like `"rainwater"` or `"not crude"`.
- **Keyword Collision in Search:** Searching for `"map"` matched `"heatmap"`; strict word boundaries and precedence ordering resolved visual specification conflicts.

---

### 4. Next Steps for Production Deployment
1. **IoT Telemetry Streaming:** Connect ingestion to MQTT/Kafka pipelines for real-time SCADA sensor ingestion.
2. **Automated Multi-Modal Vision:** Incorporate drone aerial imagery directly into the UI alongside inspection records.
3. **Role-Based Access Control (RBAC):** Formalize correction approvals with multi-signature sign-offs for regulatory filings.
