# CCL Student Info Chat

This repo contains a **FastAPI backend** that powers a student information chatbot and an **React frontend** built with Vite.

## Backend (FastAPI)

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the API server

```bash
uvicorn main:app --reload
```

The backend will start at: `http://localhost:8000`

## Frontend (React + Vite)

### Install dependencies

```bash
cd frontend
npm install
```

### Run in development mode

```bash
npm run dev
```

Open the app in the browser (usually `http://localhost:5173`). It will communicate with the backend at `http://localhost:8000`.

## Notes

- The frontend stores a `session_id` in `localStorage` so chat history is preserved across refreshes.
- The backend already has CORS enabled for development.
