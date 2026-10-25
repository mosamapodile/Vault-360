# Vault 360 — Different Paydays. Real Possibilities.

**An interactive, responsive full-stack hackathon prototype.** Built around the supplied Vault 360 brand showcase: deep charcoal, teal `#00A79D`, gold `#FFB612`, light sand, dashboard cards, multilingual onboarding, and a clear focus on people who earn in irregular patterns.

> **SAFETY / SCOPE**: Demonstration only. Vault 360 **does not lend money**, access a bank, generate credit scores, make legally binding credit decisions, charge fees, or disburse funds. Synthetic transactions are seeded. The affordability heuristic and instalments are illustrative and MUST NOT be used to approve real credit. No production borrower data should be entered.

## Quick start (Windows PowerShell / Linux / macOS)

Requires Python 3.10+ (3.12 recommended).

```powershell
cd vault360
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS / WSL instead: source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000/**. API documentation is at **http://127.0.0.1:8000/api/docs**.

**Demo account:** `thabo@demo.vault360.co.za` / PIN `1234`. This PIN is intentionally public. **Never deploy this application exposed to the internet as a real financial service**.

### Docker option

```bash
docker compose up --build
```

Browse **http://localhost:8000**. `docker compose down` stops containers; the named volume retains local demo records. To remove the volume: `docker compose down -v` (erases all demo data).

## User journey

1. **Login** — prefilled demonstration profile and synthetic 90-day irregular-income transactions. Select **English**, **isiZulu**, or **Sepedi** from the dropdown on any screen.
2. **Home** — illustrative 90-day earnings, volatility, disposable cash velocity, income chart and literacy progress.
3. **Transactions** — view records, create an entry, or import a CSV using `day,description,amount,category` with dates in the previous 90 days. Use positive amounts for `income`, negative for `business`, `living`, `transport` or `other`.
4. **My Insights** — view conservative cash-flow calculations. Answer five gamified financial-comprehension questions in the selected language; results are not a credit score.
5. **Borrow** — inspect example Start / Grow / Plus tiers. Demo gating requires cash flow and a literacy quest score of at least 60%. Save a **simulation**, which always has `DEMO_REVIEW` status — never approval.
6. **Repayments** — see a hypothetical three-part schedule that is not a mandate, debit order, loan contract or amount due.
7. **My Profile / Help** — languages, contrast mode, browser text-to-speech, privacy and limitations.

**Try voice accessibility:** Press 🔊 next to a heading, in the quest, or profile. The implementation uses browser `speechSynthesis` with BCP-47 language tags `en-ZA`, `zu-ZA`, `nso-ZA`. **IsiZulu/Sepedi voices are not guaranteed** on all devices. Text is available as a fallback. Browser speech recognition and telephone IVR are not implemented.

## Three locked-in product layers

| Layer | Prototype behavior | Not included in this demo |
| --- | --- | --- |
| 1. Accessibility and comprehension | English/isiZulu/Sepedi navigation and questionnaire; voice readout; keyboard navigation; high-contrast option; five-question educational score | Professionally validated translation, complete screen-reader QA, offline voice packs |
| 2. Irregular-income intelligence | 90-day CSV/manual cash-flow ingestion; three 30-day buckets; monthly average; income coefficient of variation; conservative remaining cash estimate | Real bank/Open Banking integration, bureau checks, identity verification, production scoring, regulator-grade affordability |
| 3. Microcredit orchestration | Start/Grow/Plus illustrative tiers, guardrails, simulated application, indicative 3-part repayment schedule, audit trail | Lending license, real provider partnerships, loan agreements, actual pricing/interest, payment collection, disbursement, production reconciliation |

## Calculation guide

On a rolling 90-day window:
- Income and expenses are grouped into three consecutive 30-day periods.
- Average monthly income = average of the three buckets.
- Income volatility = standard deviation of those buckets / average × 100%.
- Conservative available cash = `max(0, min(minimum_monthly_income, 0.8 * average_income) - average_monthly_expenses - max(R300, 15% * average_income))`.
- Illustrative monthly repayment cap = `min(25% * conservative_available_cash, R650)`.
- Demo tier limits = Start R1,000, Grow R2,000, Plus R3,000 (example figures only); a 3-way principal-only illustration and extra count-based conditions are used to gate tier simulations.

**These numbers are product placeholders, not law, market pricing, or appropriate affordability rules.** Actual lending must assess household obligations, existing debts, credit bureau data where required, fees/interest, legal limits, verified source reliability, fraud risk, suitability, customer consent and human oversight. Revisit repayment date alignment using verified inflow timing rather than fixed 30-day offsets. Consent, mandated pre-agreement disclosures and a complaints route are required for a real lending journey.

## Localization workflow

The app stores English (`en`), isiZulu (`zu`) and Sepedi (`nso`) UI dictionaries and translated literacy questions in **`frontend/app.js`**. Find `const strings` and `const questions` to edit UI copy. The API stores the language code in the user record. **Some financial detail text, category labels, dates, validation errors and helper copy remain in English**; the included dictionaries cover the key user journey but not every backend string. Before real-world use, move all interface strings into reviewed translation catalogs and have native speakers and financial/legal specialists verify terminology; complete accessibility testing with actual regional speech engines and screen readers.

Visual tokens are in `frontend/styles.css` (`:root`). The supplied visual identity remains at `assets/brand-reference.png`; the small app icon is original SVG, not an extracted vector of the submitted artwork. The page recreates the palette/layout direction using CSS and reusable cards.

## API endpoints

`GET /api/health`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET/PATCH /api/me`, `GET/POST /api/transactions`, `POST /api/transactions/import`, `GET/POST /api/quest`, `GET /api/assessment`, `GET/POST /api/applications`, `GET /api/applications`, `GET /api/audit`. Authenticated routes use `Authorization: Bearer <token>`.

## Testing

```bash
python -m pytest -q
```

Tests use a temporary SQLite database and cover login, authorization, financial assessment, literacy gating, demo applications, localizations, and CSV rejection.

## Deployment paths

**Recommended for local review:** `uvicorn ... --host 127.0.0.1`, or Docker Compose. For a **private staging demo only** on a server, set `VAULT_DB` to persistent disk, host the container behind HTTPS, use access controls and avoid real user data. Do not copy this hackathon application to an open production lending service. Build an actual identity system (real authentication, token expiry persistence, recovery, rate limiting, CSRF/CORS review, MFA as applicable), move secrets into a secret manager, introduce PostgreSQL and migrations, enforce encrypted data storage/retention, add backup/monitoring, audit log integrity, abuse prevention and thorough secure SDLC and accessibility testing.

### South African compliance path

A real pilot requires appropriately licensed credit providers, South African National Credit Act / NCR review, risk and affordability governance, POPIA obligations, explicit consent and privacy safeguards, credit-agreement and total-cost disclosures, debt collection controls, recourse/manual review, lender integration agreements and independent legal/security review. Vault 360 cannot claim regulator approval or responsible lending effectiveness on the basis of these demo rules.

## Project structure

```text
vault360/
├── backend/main.py           # FastAPI, SQLite, synthetic profile and rules
├── frontend/index.html       # App shell
├── frontend/app.js           # Views, translations, voice and interaction
├── frontend/styles.css       # Responsive design system
├── frontend/favicon.svg      # Minimal brand-inspired icon
├── assets/brand-reference.png
├── tests/test_api.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Known limitations / improvement backlog

- No real bank account connection or regulated product integration.
- No loan pricing/interest, fee schedule, instalment customization or actual deposit-event synchronization.
- CSV import does not replace existing records or deduplicate entries; never ingest genuine statements into the demo.
- Browser-dependent `speechSynthesis` voices, no microphone input / STT, incomplete localization of some descriptive strings.
- No production identity, consent system, MFA, fine-grained roles or provider portal.
- Application status is permanently `DEMO_REVIEW`; there are no actual approvals, denials, payments or loan balances.
- Simple heuristic, not a validated, unbiased or compliant underwriting model.
- In-memory login tokens reset on restart; 8-hour expiry, no account registration or password recovery.
- Basic keyboard support and contrast mode but no full WCAG audit.
- Dashboard is built without a frontend build step, favoring ease of local hacking over an enterprise component architecture.

**Prepared as a demonstrable MVP and foundation for iteration, not a finished live lending system.**

---

## October 25 premium visual + statement update (v1.1)

This archive supersedes the original version visually and functionally. The interface now uses a **coded teal/gold vector lock logo, premium charcoal sidebar, glowing hero panel, bank-statement onboarding hero, interactive FNB mini-course, synthetic PDF upload and explicit non-lender messaging**. The supplied reference image is **not** placed as an app background or embedded as an on-screen mockup. It remains in `/assets/brand-reference.png` for design comparison.

### Try the upgraded PDF journey

1. Log in, open **Transactions** and select **Download safe sample PDF**.
2. Upload that sample with **Read statement**. The server extracts transactions from **text-based, simple single-amount line PDFs** using pypdf, without saving the PDF itself.
3. Review detected dates, amounts and categories; change expense categories where appropriate.
4. Confirm the saved entries. The app updates the 90-day assessment and transaction history via the actual FastAPI/SQLite routes.
5. The **FNB how-to guide** draws from the bank's published verified-statement instructions: https://www.fnb.co.za/ways-to-bank/digital/fnb-app-guides.html .

**Limitations:** Genuine FNB PDFs can use different layouts with separate debit, credit and balance columns; the conservative parser will not import ambiguous lines. Scanned/image-only, encrypted, and complex-column PDFs are not yet supported. Do **not** test with real private statements: the demo's persisted extracted transaction data lacks production privacy/security safeguards. For safe local testing use `/assets/SYNTHETIC-statement-demo.pdf`. Running `python scripts_generate_sample.py` regenerates fictional, dated test entries (requires `reportlab`, included only as optional dev dependency; provided PDF already works).

### Language support inventory

The selector lists all **12 South African official languages**, including South African Sign Language (SASL): English `en`, isiZulu `zu`, Sepedi `nso`, isiXhosa `xh`, Afrikaans `af`, Sesotho `st`, Setswana `tn`, siSwati `ss`, Tshivenda `ve`, Xitsonga `ts`, isiNdebele `nr`, SASL `sasl`.

Only **English / isiZulu / Sepedi have starter UI and quiz dictionaries**, with some remaining English strings; unimplemented selections display English fallback and a disclosure. **SASL is not represented by speech synthesis or written translations**; a proper SASL experience needs commissioned native sign-language video segments, captions, focus order, and deaf-user usability testing. Browser voice availability for all languages is device dependent. This is a language roadmap, not a false claim of complete 12-language accessibility.

### Provider connectivity and MTN MoMo

`GET /api/partners` exposes a real authenticated local API reporting **zero connected providers**. Vault 360 has no lender contracts, credit offers, payouts, repayments or regulated integrations. The user journey works end-to-end **within the local demonstration** (login, PDF preview, reviewed import, cash-flow assessment, comprehension quiz, tier illustration, local record), but **real-world lending matching is not implemented**. MTN MoMo is primarily a payments API, not a licensed-credit-provider matching API; invoking it would not establish loan offers. For sandbox API keys visit https://momodeveloper.mtn.com/ and set up subscriptions/API user/API key per their docs. **No fake MoMo calls or payment confirmations are presented.** Never add sandbox credentials to frontend JS or the ZIP.

To develop real matching: partner with verified NCR-registered lenders, capture granular consent, define a lender-scoped data-minimization API, validate legally required affordability checks and legal disclosures with counsel, implement lender offer callbacks, and add authenticated administrative partner tools. Do not mark users as approved until a connected licensed lender returns a verified offer.

### Running and verifying on WSL

```bash
cd /mnt/c/Users/User/Downloads/vault360/vault360
source .venv/bin/activate  # if already created
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
# open http://localhost:8000; hard-refresh with Ctrl+Shift+R if old CSS is cached
```

Test with `python -m pytest -q`; tests include PDF processing and consent, no-partner guarantees and SASL preference persistence. Updated package is new ZIP. Do not overwrite project while its dev server is running without restarting the server and hard refreshing the browser.

---

## v2 Community Partner Experience

**Start with [`START_HERE.md`](START_HERE.md)** for the updated three-partner, borrower-to-settlement walkthrough. The three named partners are wholly fictitious. Current integration is a functioning *local-only* state machine, not a live payment or credit integration.
