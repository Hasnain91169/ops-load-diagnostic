# Operations Load Diagnostic (Lightweight, Reusable)

Read-only diagnostic tool for logistics operations teams to quickly estimate operational load and AI automation leverage from inbound communications.

## What This Does
- Ingests a short sample of inbound operational messages (7-14 days or capped item count).
- Classifies each item into work category, work nature, and SLA sensitivity.
- Aggregates workload metrics with conservative handling-time assumptions.
- Produces a single static report (`.md`, `.html`, or both).

## What This Does Not Do
- No email sending.
- No workflow changes.
- No continuous scanning.
- No TMS/ERP integration.
- No authentication or accounts.

## System Architecture

### Components
1. `ingestion.py`
- Input modes:
  - CSV (`timestamp,sender,subject,body`)
  - Text batch (`---`-separated messages)
  - IMAP read-only fetch (optional)
- Applies time and volume limits.

2. `classification.py`
- `HeuristicClassifier` (default): rule-assisted keyword logic.
- `OpenAIClassifier` (optional): LLM-backed classification behind the same interface.
- Output dimensions per item:
  - Work Category: Tracking/ETA, Exception/Delay, Documentation, Rate/Pricing, Internal Coordination, Other
  - Work Nature: Repetitive vs Exception-driven
  - Risk Flag: SLA-sensitive vs Not SLA-sensitive

3. `aggregation.py`
- Computes:
  - Total inbound volume
  - Volume percentage by category
  - Repetitive vs exception split
  - Conservative handling time estimates
  - Estimated hours/week
  - SLA-sensitive clusters

4. `reporting.py`
- Static report generation:
  - Markdown
  - HTML

5. `cli.py`
- Single command execution for one-time diagnostics.

## Core Data Flow
1. Ingest inbound slice.
2. Normalize to `InboundItem`.
3. Classify each item.
4. Aggregate to workload metrics.
5. Emit static report + summary JSON.

## Classification Logic (Directional, Explainable)
- Category selection: keyword scoring over subject + body.
- Work Nature:
  - Exception-driven if exception cues detected (e.g., delay, urgent, failed).
  - Otherwise repetitive.
- SLA flag:
  - Marked SLA-sensitive if urgency/deadline/cutoff cues are present.
- Confidence:
  - Heuristic confidence score based on keyword density (conservative).

## Conservative Handling Time Defaults
- Tracking / ETA: 4 minutes
- Exception / Delay: 12 minutes
- Documentation: 7 minutes
- Rate / Pricing: 8 minutes
- Internal Coordination: 6 minutes
- Other: 5 minutes

These are defaults intended for directional diagnostics and can be tuned per prospect.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

Optional for OpenAI classification:
```bash
pip install openai
set OPENAI_API_KEY=your_key_here
```

## Usage

### 1) CSV Mode
```bash
ops-diagnostic --mode csv --input examples/sample_inbound.csv --lookback-days 14 --max-items 200 --format both
```

### 2) Text Batch Mode
```bash
ops-diagnostic --mode text --input examples/sample_batch.txt --format markdown
```

### 3) IMAP Mode (read-only)
```bash
ops-diagnostic --mode imap --imap-host imap.yourmail.com --imap-user user@company.com --imap-password "app-password" --imap-folder INBOX --lookback-days 10 --max-items 150
```

### 4) OpenAI Classifier Mode
```bash
ops-diagnostic --mode csv --input examples/sample_inbound.csv --classifier openai --openai-model gpt-4.1-mini
```

## Output
Generated in `output/`:
- `operations_load_diagnostic_<timestamp>.md`
- `operations_load_diagnostic_<timestamp>.html`
- `operations_load_diagnostic_<timestamp>.summary.json`

## Example Report Sections
1. Inbound Volume Snapshot
2. Work Category Breakdown
3. Repetitive vs Exception Work
4. Estimated Operational Load (hours/week)
5. Automation Leverage Summary

## Reuse Across Prospects
- Keep ingestion format constant (CSV or forwarded mailbox).
- Run 7-14 day diagnostic window.
- Share static report in discovery calls.
- Tune handling-time defaults by vertical if needed.
