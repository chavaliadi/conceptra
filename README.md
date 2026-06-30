# 🌌 Conceptra: AI-Powered Learning Operating System

Conceptra is a next-generation **AI-Powered Learning Operating System** that converts unstructured syllabus documents (PDFs) or custom study topics into interactive, personalized, and adaptive study plans.

It generates an optimized **Concept Dependency Graph (DAG)**, maps a week-by-week **Topological Study Schedule** based on your exam date, generates **deep learning summaries and interactive quizzes**, provides a **context-aware AI Tutor with memory**, and supports a **Community Library for sharing and forking** curriculum roadmaps.

---

## 🎯 Project Aim & Vision

The core philosophy of Conceptra is that **learning should not be a linear list of chapters, but a dependency-mapped graph of concepts**. 

Most student learning systems suffer from:
1. **Chapter bloat:** Syllabus documents group atomic technical concepts under generic chapters (e.g. "Chapter 4: Network Protocols" instead of atomic sub-topics like "Address Resolution Protocol (ARP)" or "Distance Vector Routing").
2. **Self-inflicted schedule bottlenecks:** Static calendars assign equal study time to every topic regardless of cognitive difficulty.
3. **Split-brain learning tracking:** State profiles and quiz schedules are kept out-of-sync, leading to erratic scheduling.
4. **Rickrolling reference links:** Generic AI search queries often hallucinate dead URLs or generic video links.

Conceptra solves this by:
* Parsing syllabus documents into **granular (sub-topic/algorithm level) concepts**.
* Calculating prerequisites to build a **Directed Acyclic Graph (DAG)** of your knowledge.
* Packing study plans using a **Greedy Bin-Packing Study Scheduler** with cognitive difficulty costs (easy = 30m, medium = 60m, hard = 90m).
* Grounding study content with **objective MCQ grading** and an adaptive **SM-2 Spaced-Repetition System** that tracks your mastery and schedules review alerts.

---

## 🏛️ System Architecture

```mermaid
graph TD
    User([User / Browser])
    
    subgraph Frontend ["React Frontend (Vite + TypeScript)"]
        Dashboard["Dashboard & Graph View"]
        TutorDrawer["AI Tutor Drawer & MCQ Quiz"]
        CommunityLibrary["Community Library & Forking"]
        SSEListener["SSE Progress Listener"]
    end
    
    subgraph Backend ["FastAPI Application Server"]
        API["API Endpoints (FastAPI)"]
        RateLimiter["SlowAPI (Rate Limiter)"]
        Prometheus["Prometheus /metrics"]
        Sentry["Sentry Error Tracking"]
        Cache["Redis Cache & Pub/Sub"]
    end
    
    subgraph Queues ["Asynchronous Task Execution"]
        RQ["Redis Queue (RQ Worker)"]
    end

    subgraph Data ["Persistence & AI Layer"]
        DB[("PostgreSQL (Port 5435)")]
        Groq["LLM Provider (Groq API)"]
    end

    User -->|Interacts| Dashboard
    User -->|Chat / MCQ Quiz / Explainers| TutorDrawer
    User -->|Browse / Fork Plans| CommunityLibrary
    
    Dashboard -->|POST /api/v2/plans| RateLimiter
    RateLimiter --> API
    TutorDrawer -->|POST /api/v2/tutor/chat| API
    CommunityLibrary -->|POST /api/v2/plans/fork| API
    
    API -->|Write Job to Queue| Cache
    API -->|Read/Write Cache| Cache
    API -->|Read/Write Data| DB
    API -->|Log Telemetry| DB
    API --> Prometheus
    API --> Sentry
    
    Cache -->|Job trigger| RQ
    RQ -->|Execute 4-Stage Pipeline| RQ
    RQ -->|Fetch completions| Groq
    RQ -->|Persist Graph & Schedule| DB
    RQ -->|Publish Progress Status| Cache
    
    Cache -->|SSE Progress Channel| SSEListener
    SSEListener -->|Real-time Updates| Dashboard
```

---

## 🔄 Core Workflows & Logic

### 1. Asynchronous Multi-Stage AI Pipeline
When a user uploads a syllabus PDF or types a study topic:
1. **Syllabus Text Extraction:** The system extracts the raw text layer, verifying it is search-friendly (rejecting image-only scans).
2. **Concept Extraction (Stage 1):** The text is parsed by the LLM into 4–40 granular concepts with individual titles, descriptions, and difficulty weights.
3. **Dependency Graphing (Stage 2):** Prerequisites are built dynamically. A Cycle-Detection validator ensures the graph is a Directed Acyclic Graph (DAG) with no loops.
4. **Bin-Packing Study Scheduler (Stage 3):** The scheduler distributes concepts over daily hours budgets using difficulty weights.
5. **Content Synthesis (Stage 4):** Summaries, Handpicked Resources (Wiki, YouTube queries resolved server-side to prevent link rot), and MCQs are synthesized.

```mermaid
sequenceDiagram
    participant U as User Browser
    participant API as FastAPI Server
    participant Redis as Redis Queue
    participant W as RQ Worker
    participant LLM as Groq LLM
    participant DB as PostgreSQL

    U->>API: Upload Syllabus PDF / Topic
    API->>DB: Initialize Plan (Status: generating)
    API->>Redis: Enqueue Plan Generation Job
    API-->>U: SSE Connection Established (Listen to Plan UUID)
    
    W->>Redis: Pick Up Job
    W->>LLM: Step 1: Extract Granular Concepts (4-40 items)
    LLM-->>W: Concept List (easy/medium/hard)
    W->>LLM: Step 2: Determine Prerequisites
    LLM-->>W: Prerequisite Edges List
    W->>W: Perform Cycle Detection & Topological Sort
    W->>W: Step 3: Run Greedy Bin-Packing Study Scheduler
    W->>LLM: Step 4: Synthesize Study Guide Content & Quizzes
    LLM-->>W: Concept explanations & 3x MCQs per concept
    W->>DB: Save Concepts, Edges, Schedule, & Content
    W->>Redis: Publish progress: "completed"
    Redis-->>U: SSE message: "completed" (Redirects dashboard)
```

---

### 2. Spaced Repetition (SM-2) Grading & Mastery Loop
Conceptra tracks learning progress natively through objective quizzes.

```mermaid
flowchart TD
    Start([Quiz Checkpoint Opened]) --> SelectAnswer[User selects MCQ Option]
    SelectAnswer --> RateConfidence[User rates confidence: Guessing / Somewhat / Confident]
    RateConfidence --> Submit[Submit payload to /quiz/grade]
    Submit --> CheckIndex{Is selected_option_index == correct_option_index?}
    
    CheckIndex -->|Yes| Correct[is_correct = True]
    CheckIndex -->|No| Incorrect[is_correct = False]
    
    Correct --> MapQualityCorrect{Confidence reported?}
    Incorrect --> MapQualityIncorrect{Confidence reported?}
    
    MapQualityCorrect -->|💪 Confident| Q5[Quality = 5]
    MapQualityCorrect -->|🤔 Somewhat / 😰 Guessing| Q3[Quality = 3]
    
    MapQualityIncorrect -->|😰 Guessing / 🤔 Somewhat| Q2[Quality = 2]
    MapQualityIncorrect -->|💪 Confident| Q1[Quality = 1: Penalized False Confidence]
    
    Q5 & Q3 & Q2 & Q1 --> UpdateSM2[Calculate repetitions, ease_factor, interval_days]
    UpdateSM2 --> Persist[Update Progress Table & Log QuizAttempt]
    Persist --> End([Mastery scores & schedule updated])
```

#### SM-2 Mathematical Blend
Backend grading compares selected indices directly:
* **Correct + high confidence (1.00)** $\rightarrow$ Blends to Quality Score **5**.
* **Correct + low confidence (0.25 / 0.50)** $\rightarrow$ Blends to Quality Score **3**.
* **Incorrect + low confidence (0.25 / 0.50)** $\rightarrow$ Blends to Quality Score **2**.
* **Incorrect + high confidence (1.00)** $\rightarrow$ Blends to Quality Score **1** *(confident incorrect, heavily penalized to trigger immediate review)*.

Mastery updates are bounded:
$$\text{new\_mastery} = \max(0.0, \min(100.0, \text{current\_mastery} + \Delta))$$
The next review date is scheduled as:
$$\text{next\_review\_at} = \text{now} + \Delta\text{interval\_days}$$

---

### 3. Study Calendar Bin-Packing Logic
Instead of placing topics sequentially on subsequent calendar slots, Conceptra packs them greedily:
* **Prerequisites First:** We perform a topological sort of the graph to ensure prerequisites always precede dependent topics.
* **Difficulty Cost Assignment:** Each topic has a time cost based on its cognitive difficulty:
  * `easy` $\rightarrow$ 30 minutes
  * `medium` $\rightarrow$ 60 minutes
  * `hard` $\rightarrow$ 90 minutes
* **Daily Budget Constraints:** Daily slots are limited by the user's `hours_per_day` budget.
* **Greedy Allocation:** The scheduler loops over the sorted concepts list, packing them sequentially into Day 1, Day 2, etc. If a concept's cost exceeds the remaining day budget, it rolls over to the next day's budget.
* **Spaced Repetition Review Queues:** Concepts due for review are loaded from the `Progress` table, sorted topologically, and prioritized by lowest mastery percentage using Kahn's algorithm.

---

### 4. AI Tutor Misconception Grounding
When the user chats with the AI Tutor for a specific concept:
1. The backend runs a query over `QuizAttempt` to fetch the top 3 confident-incorrect attempts for that concept.
2. The tutor prompt is customized with:
   * Current student mastery scores (mastery, confidence level, attempts count).
   * Specific misconceptions: *"The user chose option A (incorrect) instead of option B (correct) for question X."*
3. The AI Tutor adapts its response style to address the specific misconception and student capability level directly.

---

## 🔑 Required API Keys & Environment Variables

Conceptra depends on a few configuration keys:

| Environment Variable | Where it goes | Purpose | Value Example |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Backend `.env` | Async Connection string for PostgreSQL database | `postgresql+asyncpg://postgres:postgres@localhost:5435/conceptra` |
| `REDIS_URL` | Backend `.env` | Redis connection URL for background jobs / SSE | `redis://localhost:6379` |
| `GROQ_API_KEY` | Backend `.env` | Access token for llama-3.1-70b-versatile pipelines | `gsk_XYZ123...` |
| `CLERK_SECRET_KEY` | Backend `.env` | Clerk secret API key to validate JWT auth headers | `sk_test_XYZ...` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Backend `.env` | Clerk publishable public identifier | `pk_test_XYZ...` |
| `SENTRY_DSN` | Backend `.env` | (Optional) Error monitoring tracking endpoint | `https://sentry_endpoint...` |
| `VITE_API_VERSION` | Frontend `.env.local` | API version router prefix | `v2` |
| `VITE_CLERK_PUBLISHABLE_KEY` | Frontend `.env.local` | Clerk publishable key for client sign-in checks | `pk_test_XYZ...` |

---

## 🛠️ Step-by-Step Setup Guide

Follow these instructions to clone and run the entire stack locally.

### Prerequisites
* **Python:** version 3.10+
* **Node.js:** version 18+
* **PostgreSQL:** Running locally on port `5435`
* **Redis:** Running locally on port `6379`

---

### 1. Database Setup
Create a PostgreSQL database named `conceptra`.
```sql
CREATE DATABASE conceptra;
```

---

### 2. Backend Installation & Setup

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   # Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend/` folder and populate it with your API keys:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5435/conceptra
   REDIS_URL=redis://localhost:6379
   GROQ_API_KEY=your_groq_api_key_here
   CLERK_SECRET_KEY=your_clerk_secret_key_here
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key_here
   ```
5. Apply database schema migrations:
   ```bash
   alembic upgrade head
   ```
6. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   * The API runs at `http://127.0.0.1:8000`
   * Swagger docs are at `http://127.0.0.1:8000/docs`

---

### 3. Asynchronous Worker Setup

For background generation, you need to run the RQ worker.

1. Open a new terminal window/tab.
2. Navigate to the `backend/` directory and activate the virtual environment:
   ```bash
   cd backend
   source .venv/bin/activate
   ```
3. Run the worker script:
   ```bash
   python -m app.worker
   ```
   * The worker listens to the `default` Redis queue and executes the multi-stage generation.

---

### 4. Frontend Installation & Setup

1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install package dependencies:
   ```bash
   npm install
   ```
3. Create a `.env.local` file inside the `frontend/` folder:
   ```env
   VITE_API_VERSION=v2
   VITE_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key_here
   ```
4. Start the frontend Vite development server:
   ```bash
   npm run dev
   ```
   * The frontend runs at `http://localhost:5173`

---

## 📈 Monitoring & Observability

Conceptra compiles system logs and analytics natively:

1. **Benchmark Telemetry Dashboard:** Access `http://localhost:5173/benchmarks` to view LLM latencies, stage durations (extraction, scheduling, graph creation, content synth), token costs, and cache hit metrics.
2. **Prometheus Metrics:** Scrape system performance from `http://127.0.0.1:8000/metrics`.
3. **Sentry Dashboard:** Any unhandled FastAPI server-side exceptions will automatically pipe to Sentry for review.
