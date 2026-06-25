# Conceptra Deployment Guide

This guide details how to deploy Conceptra as a clean local-ready or production cloud application using **Railway** (for FastAPI backend + Postgres + Redis + RQ Background Worker) and **Vercel** (for the Vite + React frontend).

---

## Technical Stack Architecture

```
[ Vite + React Frontend ] (Vercel)
          │ (HTTPS Requests & SSE)
          ▼
[ FastAPI Backend API ] (Railway)
     ├── PostgreSQL Database (Persistent storage)
     ├── Redis Server (Cache & PubSub Stream)
     └── Redis Queue (RQ Worker Process)
```

---

## 1. Backend & Infrastructure Deployment (Railway)

We deploy the FastAPI server, PostgreSQL, Redis, and the RQ worker as separate services under a single Railway project.

### Step 1.1: Provision Databases
1. Go to [Railway](https://railway.app/) and create a new project.
2. Choose **Provision PostgreSQL** to add a database instance.
3. Choose **Provision Redis** to add a Redis cache instance.

### Step 1.2: Deploy FastAPI API Service
1. Link your GitHub repository containing the backend code.
2. In Railway Service settings, set the **Root Directory** to `backend`.
3. Set the **Build Command** to:
   ```bash
   pip install -r requirements.txt
   ```
4. Set the **Start Command** to:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Configure the Environment Variables (see below).

### Step 1.3: Deploy RQ Background Worker Service
1. Create another service in the same project linked to the same GitHub repository.
2. Set the **Root Directory** to `backend`.
3. Set the **Build Command** to:
   ```bash
   pip install -r requirements.txt
   ```
4. Set the **Start Command** to run the RQ worker loop:
   ```bash
   python -m app.worker
   ```
5. Configure the exact same Environment Variables as the API service.

### API & Worker Environment Variables

| Variable Name | Description | Source / Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | SQLAlchemy Connection URL (psycopg2 for migrations, asyncpg for API) | Postgres Connection String |
| `REDIS_URL` | Redis URL for cache, PubSub, and RQ | Redis Connection String |
| `GROQ_API_KEY` | Groq developer API key | Groq Console |
| `GROQ_MODEL` | LLM model to run completions | `llama-3.3-70b-versatile` |
| `SENTRY_DSN` | Exception reporting URL (optional) | Sentry Project Settings |

*Note: In Railway, database variables like `DATABASE_URL` can be automatically referenced from provisioned database services using `${{ Postgres.DATABASE_URL }}`.*

---

## 2. Frontend Deployment (Vercel)

The frontend is a static Vite application deployed directly to Vercel.

### Step 2.1: Deploy to Vercel
1. Log in to [Vercel](https://vercel.com/) and create a new project.
2. Import your GitHub repository.
3. Set the **Framework Preset** to `Vite`.
4. Set the **Root Directory** to `frontend`.
5. Set the **Build Command** to:
   ```bash
   npm run build
   ```
6. Set the **Output Directory** to `dist`.

### Step 2.2: Configure Environment Variables
Set the following environment variables in your Vercel project settings:

```env
VITE_API_VERSION=v2
VITE_API_BASE_URL=https://your-backend-service-url.railway.app
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

---

## 3. Database Migrations (Production Setup)

Before using the application in production, apply database schema migrations.
You can run migrations locally pointing to your production database URL, or execute them in a Railway post-build command.

To run migrations manually:
```bash
cd backend
export DATABASE_URL="your-production-database-connection-url"
.venv/bin/alembic upgrade head
```
