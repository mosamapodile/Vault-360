# Two additive features — Vault 360 v2

## Rainy Day
- Optional navigation screen for educational savings planning.
- Save a target and record self-reported progress (NOT money held by Vault 360).
- Based on the existing conservative cash calculation, optional illustrative monthly contribution is capped at R100 and 5% of the estimate.
- SQLite tables are created additively; no changes to lending or repayment schemas.
- Demo data can reset when the Render free service is restarted/redeployed. Do not use for real customer deposits or financial data.

## Printable report
- 'Download readiness PDF' in My Insights; authenticated API route `/api/reports/readiness.pdf`.
- One page, generated only in memory with ReportLab.
- Contains transaction summary, comprehension result, methodology and an unambiguous warning: **NOT a payslip, verified income proof, credit score, official statement or lending approval**.
- Based on user-editable/synthetic data. Never claim a partner has certified or accepted this report.
- Real regulated lenders must independently verify customer identity, statements and affordability.

## Deployment
- `netlify.toml` is UNCHANGED; existing `/api/*` reverse proxy works.
- Netlify deploys `frontend/`, Render deploys the FastAPI backend. Both must update before new buttons work.
- Use a feature branch, test a Netlify Deploy Preview and Render staging service, then merge to the configured production branch only after tests pass.
- Do not commit database files, secrets or virtual environments. No production deploy was performed here.
