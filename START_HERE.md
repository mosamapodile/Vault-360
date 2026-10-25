# Vault 360 — Community Partner Experience (v2)

**Vault 360 connects; it never lends.** This release retains the original premium visual identity (teal, gold, dark sidebar, vector lock), 90-day cash-flow insights, financial comprehension quest, PDF statement review, 12 official language choices, text-to-speech and contrast features, and adds an interactive three-partner journey.

> **Sandbox notice:** Mavela Community Credit (rural Limpopo), KasiRise Finance Network (townships) and MetroBridge Credit Collective (urban) are **invented organisations** created solely for this software experience. They are not real or verified licensed lenders. The interest rates and prices are fabricated illustration parameters, not credit offers. No bank account, lender network or money-transfer API is connected. All conditional matches, credits, instalments and repayments are written only to local SQLite records. DO NOT enter real bank records or personal details.

## Run with Ubuntu / WSL

```bash
cd vault360
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**, demo/test credentials: `thabo@demo.vault360.co.za` with PIN `1234`. This sign-in is prefilled. API docs: http://localhost:8000/api/docs.

**Important:** The ZIP contains a `vault360` directory. Start from inside that directory. Keep your terminal open. For a clean state, stop the server and delete `vault360.sqlite3` from the extracted project folder (this erases local test history).

## Walk through the full experience

1. **Home**: Explore the dashboard and its 90-day income analysis.
2. **My Insights**: Complete the five-question financial-comprehension quest (the example user passes with `2,3,1,2,1` when answers are counted from 1).
3. **Transactions**: Explore the example activity, or import `assets/SYNTHETIC-statement-demo.pdf`. Review each parsed transaction and opt in before saving. Uploaded PDF bytes are not saved by the backend. Never upload an actual banking document into this hackathon deployment.
4. **Find your match**: Inspect rural Limpopo / township / city fictional partners. Select a partner and calculate a transparent example quote. Choose **R300 over 3 months** for the rural partner for an easy happy-path run; all three partners can be explored. An indicative cash-flow guardrail may restrict larger amounts.
5. **Send my request**: Select the Start tier and consent to local example-information sharing. The request becomes `SUBMITTED`.
6. **My journey**: Advance through local partner screening, conditional match, acceptance, and fictional ledger credit. Each step is initiated by you, appears on the timeline, and is persisted in SQLite.
7. **Repayment planning**: Record three fictional instalments. The request moves to `SETTLED_IN_SANDBOX`. **No real loan, debit order or transfer occurs.**

## Architecture

- FastAPI + SQLite backend (`backend/main.py`), durable request timeline and payment schedule tables.
- HTML/CSS/vanilla JavaScript client (`frontend/`) with no frontend build tool.
- Server-side match eligibility based on the original conservative 90-day model, saved financial-comprehension result and payment cap.
- Fictional partner quote model: simple annual interest prorated by number of months, without service fees; provided only to illustrate comparison; not a compliance-complete APR or affordability model.
- User-controlled state machine. There are deliberately **no random instant approval claims**.
- The original `/api/applications` example route still exists for backwards compatibility, but the newer partner flow uses `/api/partners/*`.

## Languages & accessibility

All 12 South African official language choices are listed, including South African Sign Language. **Only English, isiZulu, Sepedi have initial UI translations; some new partner journey content is still in English**. Other choices fall back to English. SASL video content and full multilingual accessibility have **not** been implemented and must not be represented as such. Voice playback depends on voices provided by the local browser/OS; it is not voice-input or sign-language translation.

## Run tests

```bash
PYTHONPATH=. pytest -q
node --check frontend/app.js
```

## Before any real deployment

Use HTTPS; replace example login with verified authentication; use proper consent and data retention; implement robust PDF bank statement parsers, verified transaction sources, and purpose-limited handling of financial data; obtain sandbox and commercial agreements from **real NCR-registered credit providers**; implement lender-specific APIs, human review, regulatory affordability requirements, contractual disclosures, complaint process, and separate payment processors where authorized. The local state machine cannot substitute for these controls.

## Known limitations

- Fictional lenders with invented geographic coverage, not verified businesses.
- Offers and outcomes are sandbox states, not real offers, approval or transfer.
- Date schedules are simple illustrative 30-day intervals, not true deposit-aligned repayment mandates.
- PDF extraction works best with text-based statements and requires manual confirmation.
- Local database and memory-session authentication are for isolated testing, not hosting publicly.
- No external MoMo/bank payment APIs without credentials and compliance work.
