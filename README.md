# Operations Load Diagnostic

Read-only, lightweight diagnostic for logistics ops teams. It classifies inbound operational messages, estimates workload, and outputs a static report.

## Online Web App (Vercel)
This repo now includes a browser app at the root:
- `index.html`
- `styles.css`
- `app.js`

### What it does online
- Upload CSV (`timestamp,sender,subject,body`) or text batch file (`---` separated messages).
- Apply one-time diagnostic limits (lookback days + max items).
- Classify each inbound item into:
  - Work Category
  - Work Nature
  - SLA risk flag
- Aggregate operational-load metrics.
- Generate on-screen report + download a PDF report.

### Deploy on Vercel
1. Push this repo to GitHub.
2. Import the repo in Vercel.
3. Root Directory: `.`
4. Framework Preset: `Other` (or no framework).
5. Deploy.

No backend is required for the web mode; processing runs fully in the browser.

## Conservative Defaults
- Tracking / ETA: 4 min
- Exception / Delay: 12 min
- Documentation: 7 min
- Rate / Pricing: 8 min
- Internal Coordination: 6 min
- Other: 5 min

## Input Limits (recommended)
- 7-14 day lookback
- 100-300 inbound items max

## Legacy CLI (still available)
Python CLI remains available in `src/operations_load_diagnostic/`.

### Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### Run example
```bash
ops-diagnostic --mode csv --input examples/sample_inbound.csv --lookback-days 14 --max-items 200 --format both
```
