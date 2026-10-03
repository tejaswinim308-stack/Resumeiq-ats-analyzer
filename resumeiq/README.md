

# 📄 ResumeIQ
### **Production-Grade, Explainable ATS Resume Analyzer**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Backend-Flask_3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Google Cloud Run](https://img.shields.io/badge/Cloud-Google_Cloud_Run-4285F4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Gemini API](https://img.shields.io/badge/AI-Google_Gemini_API-8E75B2?style=flat-square&logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Firebase](https://img.shields.io/badge/Auth_&_DB-Firebase-FFCA28?style=flat-square&logo=firebase&logoColor=black)](https://firebase.google.com/)

An enterprise-ready ATS optimization platform that provides **100% deterministic, fully-explainable ATS compatibility scores** by pairing LLM-driven structured extraction with a strict rule-based scoring engine.

[Architecture](#-architecture) • [Key Features](#-key-features) • [Scoring Breakdown](#-deterministic-ats-scoring-engine) • [API Reference](#-api-endpoints) • [Local Setup](#-local-development) • [Deployment](#-cloud-deployment-google-cloud-run)

</div>

---

## 💡 System Design & Highlights

Many AI resume screeners suffer from **hallucinations and inconsistent scoring** due to relying solely on LLMs for final grading. **ResumeIQ solves this** with a hybrid architecture:

* **LLM for Extraction, Not Evaluation:** The Gemini API is used strictly as a structured parser to convert raw PDF text into validated JSON schemas.
* **Deterministic ATS Engine:** Scoring uses exact mathematical formulas. Passing the same resume and job description will **always yield the exact same score**.
* **Zero-Trust Input & Payload Validation:** Strict server-side file and JSON schema verification using `pypdf` and custom schema validators before data processing.
* **Stateless & Privacy-First:** Uploaded PDF bytes are processed entirely in-memory and are never stored on disk or database. Only anonymized, structured evaluation metrics are saved for authenticated user history.

---

## 🏗️ Architecture


```

```
                              +------------------------------------+
                              |         Browser (Frontend)         |
                              |    HTML5 / Vanilla JS / CSS        |
                              +-----------------+------------------+
                                                |
                                   POST /api/analyze (multipart)
                                                v
                              +------------------------------------+
                              |         Flask Backend Engine       |
                              +-----------------+------------------+
                                                |
     +------------------------------------------+------------------------------------------+
     |                                          |                                          |
     v                                          v                                          v

```

+------------------+                      +------------------+                      +--------------------+
| PDF Extraction   |                      | Structured Parse |                      | Schema Verification|
| (pypdf)          |                      | (Gemini API)     |                      | (response_schema)  |
+--------+---------+                      +--------+---------+                      +---------+----------+
|                                          |                                         |
+------------------------------------------+-----------------------------------------+
|
v
+------------------------------------+
|    Deterministic Scoring Engine    |
|     (scoring_engine.py - 100 pt)   |
+-----------------+------------------+
|
v
+------------------------------------+
|     Section & Gap Analysis         |
|    (section_analysis.py)           |
+-----------------+------------------+
|
v
+------------------------------------+
| [Optional] Firebase Persistence    |
|   (Auth Check + Firestore Save)    |
+------------------------------------+

```

---

## 📊 Deterministic ATS Scoring Engine

Total compatibility is evaluated out of **100 points** across 6 weighted categories. Every response includes a plain-English mathematical breakdown explaining exactly why points were awarded or deducted:

| Category | Points | Description |
| :--- | :---: | :--- |
| **`skill_match`** | **30** | Direct match between applicant skills and required job skills |
| **`keyword_match`** | **20** | Presence of contextually important domain keywords |
| **`project_match`** | **20** | Alignment of technical projects with required experience |
| **`education_match`** | **10** | Degree and field of study verification |
| **`structure`** | **10** | ATS-readability, formatting quality, and section presence |
| **`certifications`** | **10** | Relevant domain certifications and professional qualifications |

> **Normalized Term Matching:** Includes standard normalization (lowercasing, punctuation stripping) and alias mapping (e.g., `JS` $\leftrightarrow$ `JavaScript`, `Postgres` $\leftrightarrow$ `PostgreSQL`), preventing false negatives without risky semantic over-generalization.

---

## 🛠️ Tech Stack

* **Frontend:** Single Page Application (SPA-lite) built with HTML5, CSS3, and Vanilla JavaScript (Fetch API).
* **Backend:** Python 3.10+, Flask, Gunicorn.
* **Generative AI:** Google Gemini API (`google-generativeai`).
* **Authentication & Database:** Firebase Auth (JWT Bearer Token verification) & Firestore.
* **Parsing & Validation:** `pypdf`, custom server-side validators.
* **Testing Suite:** `pytest` unit test suite covering scoring engine formulas, normalization rules, error handling, and mock PDF parsing.
* **Containerization & Hosting:** Docker, Google Cloud Run.

---

## 🔌 API Endpoints

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/health` | ❌ No | System health check and backend availability |
| `POST` | `/api/analyze` | ❌ No | Upload PDF resume + Job Description string for full evaluation |
| `POST` | `/api/auth/profile` | 🔑 Yes | Sync or retrieve authenticated user profile |
| `GET` | `/api/history` | 🔑 Yes | Fetch previous analysis history for logged-in user |
| `GET` | `/api/history/<id>` | 🔑 Yes | Fetch individual detailed evaluation report |
| `DELETE`| `/api/history/<id>` | 🔑 Yes | Remove analysis record from history |

---

## 🚀 Local Development

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

```

Create a `.env` file inside the `backend/` directory:

```env
PORT=8080
FLASK_ENV=development
GEMINI_API_KEY=your_gemini_api_key_here
ALLOWED_ORIGINS=http://localhost:5500,[http://127.0.0.1:5500](http://127.0.0.1:5500)

```

Run the backend development server:

```bash
python app.py

```

### 2. Frontend Setup

Since the frontend consists of static assets, serve it using any HTTP server:

```bash
cd frontend
python -m http.server 5500

```

Access the UI in your browser at `http://localhost:5500`.

### 3. Running Unit Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest

```

---

## ☁️ Cloud Deployment (Google Cloud Run)

The repository includes a production-ready `Dockerfile` configured for Google Cloud Run deployment:

```bash
cd backend

# Deploy to Cloud Run
gcloud run deploy resumeiq-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_api_key,ALLOWED_ORIGINS=[https://your-frontend-domain.com](https://your-frontend-domain.com)

```

---

## 📁 Repository Structure

```text
resumeiq/
├── backend/
│   ├── app.py                   # Flask app initialization & global error handlers
│   ├── config.py                # Environment variable configurations
│   ├── Dockerfile               # Production Docker container configuration
│   ├── routes/                  # API routes (analyze, auth, history, health)
│   ├── services/
│   │   ├── pdf_service.py       # In-memory PDF text extraction
│   │   ├── gemini_service.py    # Structured parsing using Gemini API
│   │   ├── scoring_engine.py    # Deterministic scoring logic
│   │   ├── section_analysis.py  # Recommendations & section breakdown
│   │   └── firebase_service.py  # Firebase auth & Firestore integration
│   ├── schemas/                 # Gemini API response schema validation
│   ├── utils/                   # Data normalization, validation & error handlers
│   └── tests/                   # Pytest automated test suites
└── frontend/
    ├── index.html               # SPA dashboard UI
    ├── css/                     # Application styling
    └── js/                      # API client integration & view handling logic

```

---
