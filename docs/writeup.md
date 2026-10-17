# Asset Intelligence Copilot: System Design & Architecture (Page 1)

**FlytBase Hacktoberfest 2026** | **Author:** [NAME] | **Date:** 17 October 2026

---

### 1. Storage, Indexing & Retrieval
- **Relational Fleet Store (`data/asset_intelligence.db`):** Ingests structured assets into SQLite tables (`wells`, `inspections`, `maintenance`, `regulatory_events`). Multi-column B-tree indices on `(well_id, inspected_at)`, `area_id`, and `(well_id, completed_at)` provide fast filtering across 45,000+ historical records.
- **Unstructured Document Indexing (SQLite FTS5):** Indexes 1,655 operational documents—1,509 maintenance workover logs, 2 equipment manuals (T200, T350), 3 regulatory SOPs, and 141 field context notes (`CTX-XXXX-XXX`). FTS5 BM25 scoring enables discovery of root-cause analyses, containment actions, and workover logs.
- **Audited Corrections & Private State:** A dedicated `corrections` table records field re-measurements and overrides while preserving raw source records. A `private_messages` table stores conversation histories keyed strictly by `user_id`.

### 2. Tools & Pipeline Execution Flow
- **Pipeline Architecture:** `Question → Intent/Entity Extraction → Validated Tool Selection → Indexed Retrieval → Deterministic Python Calc → Evidence Assembly → Synthesized Answer & Viz Spec`.
- **Deterministic Tool Dispatch:** Tools (`search_wells`, `calculate_downtime`, `search_regulator_events`, `search_manuals_and_sops`, `record_correction`, `retrieve_private_memory`, `generate_visualization`) are strictly validated against schemas. The pipeline enforces a maximum of two logical LLM calls per turn (intent classification and final answer synthesis).

### 3. Numbers, Documents & Notes
- **Quantitative Telemetry:** Sensor deltas ($\Delta T = T_{\text{wellhead}} - T_{\text{ambient}}$), flow pressures, and fluid volumes.
- **Operational Manuals & SOP Thresholds:** Extracted dynamically from source text (e.g., T200 wellhead $\Delta T \ge 15.0\,^\circ\text{C}$; T350 $\Delta T \ge 20.0\,^\circ\text{C}$; spill reporting $\ge 5\,\text{bbl}$ within 24 hours); thresholds are never hardcoded in model prompts.
- **Human Context Notes:** Qualitative field observations (`CTX-XXXX-XXX`) account for planned shut-ins (preventing false downtime flags) and false-positive releases (e.g., recorded dye tests or rainwater pooling).

### 4. Both Memory Levels: Shared vs. Private
- **Shared Audited Memory:** Operational overrides (e.g., re-measuring wellhead temperature or re-classifying spill volume) require user identification, timestamp, reason, original value, corrected value, and citation evidence. Once committed, the override updates ground truth across all users while raw source files remain immutable, scoped to a single well or all wells of a type.
- **Private User Memory:** Chat conversations are partitioned by `user_id`. Prior questions, referenced assets, and temporary inquiry context remain strictly confidential to the initiating user and never leak into another user's session.

### 5. Conflicts & Discrepancy Transparency
When qualitative field statements contradict physical telemetry (e.g., operator notes asserting normal production while thermal sensors indicate $\Delta T < 1.0\,^\circ\text{C}$), the system does not silently average or overwrite data. Contradictions are surfaced side-by-side with source citations, flagging unverified assertions and prompting the user to submit an audited correction if field re-testing occurred.

### 6. New-Data Handling (Tested by Simulation)
Ingestion is format-driven and idempotent. Robustness to unseen test datasets was validated through simulation:
- **Date-Shift Simulation:** Source records were synthetically translated by +180 days; downtime windows, compliance reporting intervals, and trend charts updated consistently.
- **Asset Mutation & Deletion Simulation:** Asset identifiers were renamed and random inspection records deleted; the parser and calculation engines handled missing intervals deterministically (0 days downtime for uninspected weeks).
- **Transactional Idempotence:** Re-running the ingestion pipeline cleanly resets and populates database tables without record duplication.

### 7. Models, Latency & Cost Optimization
- **Model Layer:** Google Gemini `gemini-3.5-flash-lite` serves as the primary language model, supported by local Ollama (`gemma4:e4b`) and deterministic rule engines.
- **Cost & Call Budgeting:** Strictly capped at two logical LLM calls per query. Deterministic tool execution and rule fallbacks require zero provider calls. Session-level caching and exponential backoff retry wrappers minimize external API calls and prevent token exhaustion.

### 8. What I Would Do Next
- **Real-Time SCADA Telemetry:** Connect ingestion to industrial MQTT/Kafka message brokers for sub-second edge event processing.
- **Multimodal Aerial Inspection:** Ingest drone thermographic imagery directly into visual response cards alongside sensor telemetry.
- **Cryptographic RBAC Auditing:** Implement multi-signature authorization and cryptographic audit logs for compliance filings.

<div class="page-break"></div>

# Benchmark Evaluation Results & Findings (Page 2)

### 1. Official Evaluation Suite (Q1 – Q18) Results Template
*This compact matrix serves as the standardized evaluation template to be populated directly from `results.md` upon arrival of the final benchmark dataset.*

| Question | Answer Summary | Evidence | Worked/Failed | Why |
|---|---|---|:---:|---|
| **Q1:** Current Status (WELL-0001) | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q2:** Offline Fleet (NE Block 8) | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q3:** 13-Wk Temp Trend (WELL-0001) | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q4:** 4-Yr Spill History (WELL-0001) | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q5:** 2025 Downtime (WELL-0001) | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q6:** Top Downtime Wells (NE Block 7)| [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q7:** 90-Day Spills Map (NE Block 8)| [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q8:** 2026 Spills Heatmap | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q9:** Regulatory Audit (WELL-0001) | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q10:** Containment > 4h Violations | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q11:** Conversation Memory Recall | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q12:** Telemetry Correction & Re-Query| [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q13:** Spill Override & Classification| [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q14:** Well-Type Rule Scope Override| [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q15:** Shared Correction Propagation| [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q16:** Shared Notes vs Private Memory| [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q17:** Handling Conflicting Claims | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |
| **Q18:** AI Analysis Disagreement Audit | [Pending final results.md] | [Source / Citation] | [Pending] | [Evaluation notes] |

### 2. What Worked
- **Deterministic Python Calculation Engine:** Delegating arithmetic (downtime day accumulation, spill reporting deadlines, repair cost sums) strictly to Python functions completely eliminated arithmetic drift, off-by-one errors, and hallucinations.
- **Dynamic SOP & Manual Parsing:** Extracting operating thresholds directly from markdown documentation enabled the system to adapt dynamically to distinct asset specifications without hardcoded prompts.
- **Dual Memory Layer:** Segregating shared audited corrections from private chat history provided collaborative accuracy across users while strictly isolating sensitive inquiry context.
- **Multimodal Visualization Specs:** Returning structured visualization specifications (cards, tables, line charts, bar charts, maps, heatmaps) paired with an interactive view selector enabled operators to toggle between charts and raw tabular data.

### 3. What Failed & Limitations (Caught & Remediated During Simulation)
- **Regex Line-Break Sensitivity in SOP Markdown:**
  - *Failure:* Automated SOP parsing initially failed on `T350.md` due to an unexpected newline in the source phrase (`at least **20 °C above\nambient**`).
  - *Remediation:* Replaced literal whitespace patterns with whitespace-agnostic `\s+` across all manual and SOP parsers.
- **Null Geospatial Coordinates in Asset Records:**
  - *Failure:* Map queries failed to render pins when individual asset metadata contained `null` latitude and longitude values.
  - *Remediation:* Implemented deterministic area-center coordinates from `fleet/areas.json` with reproducible pad offsets when exact coordinates are missing.
- **Asset Bundling of Leaflet Markers:**
  - *Failure:* In sandboxed browser environments, Vite's asset bundling failed to resolve Leaflet's default PNG marker paths, causing 404 errors.
  - *Remediation:* Replaced default PNG icon dependencies with standalone inline SVG markers (`L.divIcon`), guaranteeing offline rendering.
- **Query Intent Precedence & Keyword Collision:**
  - *Failure:* User queries requesting a geographic `"map"` occasionally collided with `"heatmap"` intent rules.
  - *Remediation:* Applied strict word-boundary matching (`\bmap\b` vs `\bheatmap\b`) and structured intent classification precedence.
