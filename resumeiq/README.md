# ResumeIQ — AI Resume Analyzer

Upload a PDF resume + paste a job description → get a deterministic,
fully-explainable ATS compatibility score, skill/keyword matching,
section-by-section feedback, and grounded recommendations.

- **Frontend:** HTML, CSS, vanilla JavaScript (`frontend/`)
- **Backend:** Python, Flask (`backend/`)
- **AI:** Gemini API — used **only** for structured extraction (never for scoring)
- **Scoring:** a fully deterministic engine in `backend/services/scoring_engine.py` — same resume + job description always produces the same score, and every point is explained
- **Auth / persistence:** Firebase Authentication + Firestore (optional in local dev)
- **Cloud:** Docker image ready for Google Cloud Run

## Architecture

```
Browser (frontend/)
  → POST /api/analyze (multipart/form-data)
  → Flask backend (backend/)
      → utils/validators.py       (PDF + job description validation)
      → services/pdf_service.py   (extract resume text)
      → services/gemini_service.py (Gemini: structured extraction ONLY)
      → schemas/response_schema.py (validate Gemini's JSON before trusting it)
      → services/scoring_engine.py (deterministic ATS score, 6 weighted categories)
      → services/section_analysis.py (section scores, strengths, recommendations)
      → services/firebase_service.py (optional: save to the caller's history)
  ← JSON response
```

The Gemini API key is read from an environment variable on the backend
only. It is never sent to, or reachable from, frontend JavaScript.

## Deterministic ATS scoring

Total = 100 points, split across six categories (see
`backend/services/scoring_engine.py` for the exact formulas and
`score_breakdown.<category>.explanation` in every API response for a
plain-English explanation of that request's numbers):

| Category           | Points |
|---------------------|-------:|
| skill_match          | 30 |
| keyword_match         | 20 |
| project_match          | 20 |
| education_match         | 10 |
| structure                | 10 |
| certifications            | 10 |

Skill/keyword matching is normalized (case, punctuation, a curated alias
table like `JS` ↔ `JavaScript`, `Postgres` ↔ `PostgreSQL`) but never
performs unsafe semantic substitutions — see `backend/utils/normalize.py`.

## Local development

### 1. Backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure environment variables:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
GEMINI_API_KEY=your-key-from-https://aistudio.google.com/app/apikey
ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

Firebase (`FIREBASE_PROJECT_ID` / `GOOGLE_APPLICATION_CREDENTIALS`) is
**optional** in local dev — leave both unset and `/api/analyze` still
works; `/api/auth/profile` and `/api/history/*` will return a clean
`service_unavailable` / `authentication_error` response instead of
crashing.

Run the server:

```bash
python app.py
```

The Flask server listens on `0.0.0.0`, port `$PORT` (defaults to
`8080`), so it's ready as-is for `gcloud run deploy`.

### 2. Frontend

The frontend is static HTML/CSS/JS — no build step. Serve it with any
static file server, e.g.:

```bash
cd frontend
python -m http.server 5500
```

Then open `http://localhost:5500`. If your backend isn't at
`http://localhost:8080`, set the base URL before `js/main.js` loads by
adding this to `index.html`:

```html
<script>window.RESUMEIQ_API_BASE_URL = "https://your-backend-url";</script>
```

### 3. Run the tests

```bash
cd backend
pip install -r requirements-dev.txt   # adds pytest + reportlab (test-PDF generation)
pytest
```

Covers: ATS score calculation, keyword/skill normalization, skill
matching, invalid PDF handling, empty job description, the health
endpoint, and malformed/invalid Gemini response handling.

## API

| Method | Endpoint                     | Auth required |
|--------|-------------------------------|----------------|
| GET    | `/api/health`                   | No |
| POST   | `/api/analyze`                    | No |
| POST   | `/api/auth/profile`                 | Yes (Firebase ID token) |
| GET    | `/api/history`                        | Yes |
| GET    | `/api/history/<analysis_id>`            | Yes |
| DELETE | `/api/history/<analysis_id>`              | Yes |

`/api/analyze` accepts `multipart/form-data` with fields `resume` (PDF
file) and `job_description` (string), and returns the full analysis
JSON documented in `backend/routes/analyze.py`. Authenticated routes
expect `Authorization: Bearer <firebase-id-token>`.

Errors are always clean JSON — never a Python stack trace:

```json
{ "success": false, "error": { "code": "invalid_file", "message": "..." } }
```

## Security notes

- The Gemini API key and Firebase service-account credentials never
  leave the backend process.
- Uploaded PDF bytes are processed in memory and **never written to
  disk or to Firestore** — only the structured analysis result is
  persisted (and only when the caller is authenticated).
- File type and size are validated server-side regardless of what the
  frontend already checked.
- CORS is restricted to the origins listed in `ALLOWED_ORIGINS`.

## Deployment (Google Cloud Run)

```bash
cd backend
gcloud run deploy resumeiq-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your-key,ALLOWED_ORIGINS=https://your-frontend-domain
```

For Firestore/Firebase Auth in production, grant the Cloud Run service
account the Firebase Admin / Firestore roles and leave
`GOOGLE_APPLICATION_CREDENTIALS` unset so Application Default
Credentials are used, instead of shipping a service-account key file in
the image.

Deploy `frontend/` to any static host (Firebase Hosting, Cloud Storage
+ CDN, Netlify, etc.) and point `window.RESUMEIQ_API_BASE_URL` at your
deployed backend URL.

## Project structure

```
backend/
  app.py                    Flask app factory + global error handling
  config.py                 Environment-variable configuration
  requirements.txt          Runtime dependencies
  requirements-dev.txt      + pytest, reportlab (for tests)
  Dockerfile                Cloud Run image
  routes/                   health, analyze, auth, history blueprints
  services/
    pdf_service.py            PDF text extraction (pypdf)
    gemini_service.py          Gemini structured extraction only
    matching_engine.py          Skill/keyword matching
    scoring_engine.py            Deterministic ATS scoring
    section_analysis.py           Section scores + recommendations
    firebase_service.py            Auth + Firestore persistence
  schemas/response_schema.py    Gemini response schema + validation
  utils/
    validators.py                Server-side input validation
    normalize.py                  Skill/keyword normalization
    errors.py                      Controlled, user-facing error types
    auth.py                         Bearer-token helper
  tests/                          Unit tests (pytest)

frontend/
  index.html                Upload / loading / dashboard views (SPA-lite)
  css/styles.css            Design system (from the Stitch export)
  js/api.js                 Backend API client
  js/main.js                 View logic, form handling, dashboard rendering
```
