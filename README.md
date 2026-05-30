# Conceptra

Study intelligence tool — paste a topic, get a concept dependency map, schedule, and per-concept content.

**Phase 1:** FastAPI backend + React frontend with in-memory fixture data. No database, no Docker, no AI pipeline yet.

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API runs at http://127.0.0.1:8000 — docs at http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173 (proxies `/api` to the backend).

## Try it

1. Open http://localhost:5173
2. Enter **Operating Systems** or **React Fundamentals**
3. Pick an exam date and submit
4. Explore concepts, open the detail panel, mark progress

> Plans are stored in memory on the backend — they disappear when you restart the server.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/plans` | Create a plan from fixtures |
| GET | `/api/plans/{uuid}` | Get full plan |
| GET | `/api/plans/{uuid}/concepts/{id}/content` | Get concept content |

## Project structure

```
Conceptra/
├── backend/app/          # FastAPI + Pydantic + in-memory store
├── frontend/src/         # React + Tailwind + React Router
└── Conceptra_Blueprint.docx
```

## What's next (Phase 2+)

- AI pipeline (mock → Claude)
- React Flow graph UI
- PostgreSQL persistence
- Docker, Redis, deployment
