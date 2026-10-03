
# 📄 ResumeIQ — Application Core

This directory contains the primary source code and backend services for **ResumeIQ**, a deterministic, explainable ATS resume analyzer.

---

## 📂 Directory Structure

```text
.
├── backend/                  # Flask REST API & Core Engine
│   ├── app.py                # Entry point & error handlers
│   ├── config.py             # Environment configuration
│   ├── Dockerfile            # Container configuration for Google Cloud Run
│   ├── routes/               # API endpoints (analyze, auth, history, health)
│   ├── services/             # Extraction, matching & deterministic scoring engine
│   ├── schemas/              # Gemini structured response schemas
│   ├── utils/                # Server-side validation & error helpers
│   └── tests/                # Pytest unit testing suite
│
└── frontend/                 # Client Interface (Static SPA)
    ├── index.html            # Main UI layout
    ├── css/                  # Styling & layout rules
    └── js/                   # API integration & dashboard rendering

```

---

## ⚡ Quick Start (Local Run)

### 1. Run Backend (Port 8080)

```bash
cd backend
python -m venv .venv

# Activate venv:
# Windows: .venv\Scripts\activate | Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
python app.py

```

### 2. Run Frontend (Port 5500)

```bash
cd frontend
python -m http.server 5500

```

Open your browser at `http://localhost:5500`.

---

## 🧪 Unit Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest

```

```

```
