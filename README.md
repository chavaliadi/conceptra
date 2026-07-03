# 🌌 Conceptra: Adaptive Learning Operating System (ALOS)

Conceptra is an **Adaptive Learning Operating System (ALOS)** designed to compile unstructured course syllabi into dynamic, state-tracking execution environments. 

Most "AI study apps" act as simple wrappers around LLMs, leading to high latency, hallucinated study guides, and unstable study calendars. Conceptra takes a different approach: it treats the LLM as a **stateless utility service** and runs its learning engine using **deterministic systems, graph theory, and cognitive science algorithms**.

---

## 🏛️ System Philosophy: Decoupled Architecture

Conceptra divides your learning process into three independent layers. This guarantees that your schedule, progress tracking, and study calendars are governed by stable backend math rather than unpredictable AI generations.

```mermaid
graph TD
    subgraph Knowledge ["Knowledge Layer (Static Graph Schema)"]
        Concepts["Granular Concepts<br>(CRC, TCP Flow Control, ARP)"]
        Prereqs["DAG Dependencies<br>(Directed Edges)"]
    end
    
    subgraph Student ["Student State Layer (Mastery Registry)"]
        ProgressTable["Progress Table<br>(mastery_pct, ease_factor, interval_days)"]
        Attempts["Quiz Attempts<br>(is_correct, confidence, is_flagged)"]
        Calendar["Bin-Packed Schedule<br>(Topological Study Dates)"]
    end
    
    subgraph AISynthesis ["AI Synthesis & Resolution Layer (LLM Component)"]
        Extractor["LLM Concept Extractor<br>(Syllabus PDF -> JSON list)"]
        ResourceResolver["Resource URL Registry<br>(Hallucination-Free platform queries)"]
        TutorGrounder["Tutor Grounding Context<br>(Quiz mistakes in tutor prompt)"]
    end

    Extractor -.->|Populates| Knowledge
    Knowledge -->|Structural Constraints| Calendar
    ProgressTable -->|SM-2 Math Updates| Calendar
    Attempts -->|Updates| ProgressTable
    ProgressTable -->|Adaptation Signal| TutorGrounder
    TutorGrounder -.->|Personalizes| Student
```

### 1. The Knowledge Layer (The Compiler)
When you upload a syllabus, the system compiles it into a **Directed Acyclic Graph (DAG)**. 
- **Concepts (Nodes):** The syllabus is broken down into granular sub-topics (e.g., instead of "Computer Networks", it extracts "IP Addressing", "Subnetting", "CIDR").
- **Dependencies (Edges):** The compiler maps what you must learn *before* you can study a harder topic (e.g., "Binary Arithmetic" $\rightarrow$ "Subnetting").
- **Cycle Detection:** A cycle validation algorithm ensures there are no circular dependencies (e.g., A depends on B, which depends on A), which would break scheduling.

### 2. The Student State Layer (The Registry & Scheduler)
This is the database registry of your progress. It does not rely on LLMs. It tracks:
- **Mastery Levels:** Calculated deterministically from quiz scores and reported confidence.
- **Forgetting Curves:** The SuperMemo-2 (SM-2) Spaced Repetition algorithm computes when you will forget a concept, automatically adjusting its interval.
- **Dynamic Scheduler:** Combines a topological sort of the knowledge graph with a greedy bin-packing algorithm to generate a custom day-by-day study program.

### 3. The AI Synthesis Layer (Stateless Handlers)
LLMs are stateless. Conceptra calls Groq API endpoints only when it needs translation tasks:
- Parsing course syllabi into clean structural JSON.
- Generating multiple-choice questions (MCQs) for concept checkpoints.
- Generating explanatory guides.
- Serving as a grounding-tutor that explains concepts during chat.

---

## 📁 Codebase Directory Map

Refer to these source locations to inspect the underlying implementations of each ALOS subsystem:

```
├── backend/
│   └── app/
│       ├── api/
│       │   └── routes/
│       │       ├── plans_v2.py       <-- REST endpoints for syllabus uploading, calendar replanning, and analytics
│       │       └── tutor_routes.py   <-- AI tutor RAG chat synthesis & Spaced Repetition MCQ grading loops
│       ├── models/
│       │   ├── database.py           <-- ORM Schemas (Plan, Concept, Edge, Progress, QuizAttempt, TutorChatMessage)
│       │   └── schemas.py            <-- Pydantic validation schemas (including custom weekly availability arrays)
│       └── services/
│           ├── ai_service.py         <-- Groq client handler for plan compilation, QA generation, and replanning prompts
│           ├── dag_service.py        <-- Kahn's topological sorter, BFS level grouper, and greedy bin-packing scheduler
│           ├── scheduler.py          <-- Blended Ebbinghaus retention decay & review debt telemetry
│           └── srs.py                <-- Core SuperMemo-2 algorithm parameters
└── frontend/
    └── src/
        ├── api/
        │   └── client.ts             <-- Typings-safe client wrapper for background sync endpoints
        ├── components/
        │   ├── ConceptGraph.tsx      <-- Level-based dependency visualizer rendering 5 discrete mastery statuses
        │   └── AnalyticsDashboard.tsx <-- SVG Ebbinghaus forgetting curve line chart & review debt metric card
        ├── pages/
        │   ├── PlanView.tsx          <-- Study dashboard featuring interactive weekly availability scheduler
        │   └── Landing.tsx           <-- File extraction & syllabus generation entry page
        └── types.ts                  <-- TypeScript interfaces mirroring database schemas
```

---

## 🗄️ Database Schema Design

The ALOS database schema is designed to enforce relational integrity. If a study plan is deleted, all child metadata cascades cleanly.

```
                  ┌───────────────────────┐
                  │         Plan          │
                  └───────────┬───────────┘
                              │ 1
                              ├───────────────────────┐
                            * │                     * │
                  ┌───────────▼───────────┐ ┌─────────▼─────────┐
                  │        Concept        │ │       Edge        │
                  └───────────┬───────────┘ └───────────────────┘
                              │ 1
          ┌───────────────────┼───────────────────┐
        1 │                 * │                 * │
┌─────────▼─────────┐ ┌───────▼───────┐ ┌─────────▼─────────┐
│     Progress      │ │  QuizAttempt  │ │ TutorChatMessage  │
└───────────────────┘ └───────────────┘ └───────────────────┘
```

- **Plan:** Stores master study parameters (`hours_per_day`, `exam_date`, `topic`, and `calendar_timetable` JSONB weekly study limits).
- **Concept:** Individual study items containing names, cognitive descriptions, and difficulty weights (`easy`, `medium`, `hard`).
- **Edge:** Directed dependency vectors storing `from_concept_id` (prerequisite) and `to_concept_id` (target).
- **Progress:** Spacing registry storing `repetitions`, `ease_factor`, `interval_days`, `mastery_pct`, `last_reviewed_at`, and `next_review_at`.
- **QuizAttempt:** Student history containing `question_text`, `is_correct`, and `confidence_reported`.
- **TutorChatMessage:** Context message thread containing chat history for conversational RAG queries.

---

## 📈 Spaced Repetition & Forgetting Curves (Simply Explained)

To ensure you retain what you study, Conceptra implements a cognitive decay model based on the **Ebbinghaus Forgetting Curve** and the **SuperMemo-2 (SM-2) Spaced Repetition** algorithm.

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

### The MCQ Confidence Grading Matrix
When you answer a quiz, you report your confidence: **Guessing**, **Somewhat Confident**, or **Highly Confident**. The system maps this to an SM-2 Quality Score (0 to 5):

1. **Correct + Highly Confident $\rightarrow$ Quality 5:** You fully grasp the concept.
2. **Correct + Low/Somewhat Confident $\rightarrow$ Quality 3:** Correct answer, but spacing intervals will expand slowly to ensure reinforcement.
3. **Incorrect + Low/Guessing Confidence $\rightarrow$ Quality 2:** You didn't know, but you knew you didn't know. Spacing intervals reset.
4. **Incorrect + Highly Confident $\rightarrow$ Quality 1 (Critical):** You had **false confidence** (a deep misconception). The system heavily penalizes your ease factor and schedules an immediate review.

### How Spaced Repetition Math Works
The Quality Score ($q$) modifies the concept's **Ease Factor ($EF$)** and **Repetitions count ($R$)**:

- **Ease Factor adjustment:**
  $$EF_{\text{new}} = EF_{\text{old}} + (0.1 - (5 - q) \times (0.08 + (5 - q) \times 0.02))$$
  We clamp $EF$ to a minimum of $1.3$.
- **Interval calculation ($I$ in days):**
  - If $R = 1 \rightarrow I = 1$ day
  - If $R = 2 \rightarrow I = 6$ days
  - If $R > 2 \rightarrow I_{\text{new}} = I_{\text{old}} \times EF_{\text{new}}$

### Decay-Aware Retention & Review Debt
Every concept's retention decays exponentially over time since it was last reviewed:
$$\text{Retention} = 100 \times \left(0.9\right)^{\frac{\Delta \text{days}}{I}}$$
- **Review Debt:** Any concept where the current retention index drops below critical thresholds or the next review date has passed is marked as "Overdue", generating **Review Debt** that must be resolved before introducing new topics.

---

## 🧮 Scheduling Algorithms (Simply Explained)

Conceptra uses deterministic scheduling to turn your knowledge graph into a study calendar.

### 1. Topological Sorting (Kahn's Algorithm)
To prevent a student from studying advanced concepts before mastering prerequisites, Conceptra performs a topological sort on the dependency DAG.

- We start by identifying nodes with **zero in-degree** (no prerequisites).
- We place these nodes first in the queue.
- We then remove these nodes from the graph and decrease the in-degree of all their child nodes.
- We repeat this process until all concepts are sorted.
If the graph contains cycles, Kahn's algorithm fails, triggering validation errors immediately during upload.

### 2. Greedy Bin-Packing with Availability Timetables
Syllabus topics have varying difficulty ratings. Conceptra assigns a time cost to each:
- **Easy:** 30 minutes
- **Medium:** 60 minutes
- **Hard:** 90 minutes

To schedule study sessions:
1. The user inputs their available weekly timetable (e.g., Monday = 2 hrs, Saturday = 4 hrs, Sunday = 0 hrs).
2. The scheduler loops through the topologically sorted concepts.
3. It packs them into available calendar slots sequentially.
4. If a concept's time cost exceeds the remaining availability budget for that day, it is packed into the next day with positive availability.
5. Days with $0$ hours availability (rest days) are skipped entirely, letting you schedule around work or weekends.

---

## 🤖 RAG-Grounded AI Tutoring (Simply Explained)

Ordinary AI tutors have no memory of your learning behavior. Conceptra integrates your database state into the LLM context (Retrieval-Augmented Generation) to guide the tutor:

1. **State Injection:** The backend checks the mastery score, ease factor, and elapsed review interval of the active concept.
2. **Graph Context Injection:** The tutor retrieves the mastery status of the concept's prerequisites. If you are struggling with "Subnet Masks" and try to learn "Routing Tables", the tutor is grounded in this blocker.
3. **Misconception Injection:** The system fetches your last 3 **confident-incorrect** quiz responses (where you selected the wrong answer with high confidence). The prompt includes: *"The student answered question X incorrectly, choosing option Y (incorrect) instead of option Z (correct). Direct your response to resolve this specific misunderstanding."*

This grounds the tutor in your personal memory profile, yielding highly contextual answers.

---

## 💻 Technical Stack & Local Infrastructure

- **Backend:** FastAPI application server with SlowAPI rate limiting, SQLAlchemy, and Alembic migrations.
- **Frontend:** React, Vite, TailwindCSS, and TypeScript.
- **Database:** PostgreSQL (Port 5435).
- **Cache & Pub/Sub:** Redis (Port 6379) for caching database plans and broadcasting progress updates.
- **Background Worker:** Redis Queue (RQ) worker running async syllabus extraction, DAG cycle checking, and content generation.
- **LLM Pipeline:** Groq API using `llama-3.1-70b-versatile` for language modeling.

---

## 🛠️ Step-by-Step Installation & Setup

### Prerequisites
* **Python:** version 3.10+
* **Node.js:** version 18+
* **PostgreSQL:** Running locally on port `5435`
* **Redis:** Running locally on port `6379`

---

### 1. Database Setup
Create a PostgreSQL database named `conceptra`:
```sql
CREATE DATABASE conceptra;
```

---

### 2. Backend Setup
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
4. Create a `.env` file in the `backend/` folder:
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
   * Swagger docs will be accessible at `http://127.0.0.1:8000/docs`

---

### 3. Background Worker Setup
1. Open a new terminal tab/window, navigate to the `backend/` folder, and activate the virtual environment:
   ```bash
   cd backend
   source .venv/bin/activate
   ```
2. Start the Redis Queue background worker:
   ```bash
   python -m app.worker
   ```

---

### 4. Frontend Setup
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
4. Start the Vite development server:
   ```bash
   npm run dev
   ```
   * The frontend runs locally at `http://localhost:5173`
   * Open the app in your browser to start compiling your learning plans!
