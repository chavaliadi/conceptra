# Conceptra Master Roadmap: From Prototype to Production Study Companion
## Detailed Implementation & Future Phases Plan

**Last Updated:** June 22, 2026
**Project:** Conceptra - Study Intelligence Tool
**Status:** Phase 3 Completed (Planning Next Phases)

---

## Executive Summary

Phase 2 transforms Conceptra from a fixture-based prototype into a production-grade system with persistent storage and AI-powered content generation. This document details the architectural decisions, implementation roadmap, and technical specifications for building this foundation.

**Key Principle:** *Build a rock-solid database layer first, validate it works perfectly with the frontend, then layer in AI. This ensures isolation of failure points and makes debugging tractable.*

---

## Phase 1: What We Built ✅

### Architecture
```
React Frontend (Vite + TypeScript + React Router)
        ↓
FastAPI Backend (in-memory store)
        ↓
Fixture Data (hard-coded JSON)
```

### Features Completed
- ✅ Topic input form with date/hours selection
- ✅ Graph visualization (React Flow + circular layout)
- ✅ Calendar view (week-by-week study schedule)
- ✅ Concept detail panel (explanations, quiz, resources)
- ✅ Progress tracking (localStorage)
- ✅ Status marking (learned/struggling/skipped/untouched)
- ✅ Prerequisite unlock system
- ✅ PDF upload UI (backend handler ready)
- ✅ 5 complete fixture datasets

### Current Data Flow
```
React
  ↓
FastAPI (app.main:app)
  ↓
In-Memory Store (app/store.py)
  ↓
Fixture Data (app/fixtures/sample_plans.py)
```

### API Endpoints (Phase 1)
- `GET /health` — Health check
- `POST /api/plans` — Create plan from topic (fixtures)
- `POST /api/plans/upload-syllabus` — Upload PDF (extracts filename as topic)
- `GET /api/plans/{uuid}` — Get full plan
- `GET /api/plans/{uuid}/concepts/{id}/content` — Get concept details

**Limitation:** All data disappears when server restarts. No multi-user support. No real content generation.

---

## Phase 2: Production Database & AI Pipeline

### Why This Order?

#### Problem: Tight Coupling
Current state has frontend, backend, and data all tightly coupled through fixtures. If anything breaks, debugging is exponentially harder because you can't isolate failures.

#### Solution: Layered Isolation
```
Phase 2a: Database Layer (stable baseline)
Phase 2b: Connect React (same UI, different source)
Phase 2c: AI Pipeline (plugs into existing database)
Phase 2d: Validation & Refinement
```

Each phase is independently testable. If AI breaks, you know the database works. If frontend breaks, you know the API works.

---

## Phase 2a: Database Foundation

### 2a.1 Technology Stack

| Component | Technology | Reason |
|-----------|-----------|--------|
| Database | PostgreSQL 15+ | ACID compliance, JSONB support, mature ORM support |
| ORM | SQLAlchemy 2.0 | Type hints, async support, declarative models |
| Migrations | Alembic | Zero-downtime schema changes, rollback safety |
| Connection Pool | SQLAlchemy Engine | Connection pooling, async support |
| Validation | Pydantic v2 | Runtime type safety, OpenAPI integration |
| Testing | pytest + pytest-asyncio | Async test support, fixtures, mocking |

### 2a.2 Database Schema

#### Why This Design?

**Normalization Level:** ~3NF with partial denormalization
- **Fully normalized:** Plans reference concepts, concepts reference edges
- **Denormalized:** Store JSONB for quiz/resources (read-heavy, write-once per concept)
- **Rationale:** Concept dependency queries are frequent (DAG validation), but quiz data is static

#### 2a.2.1 `plans` Table

```sql
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic VARCHAR(200) NOT NULL,
    exam_date DATE,
    hours_per_day INTEGER NOT NULL DEFAULT 2,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',  -- active, archived, completed
    
    CONSTRAINT hours_valid CHECK (hours_per_day >= 1 AND hours_per_day <= 8),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
);
```

**Why:** Core plan metadata. Status column allows soft deletes and plan lifecycle tracking.

---

#### 2a.2.2 `concepts` Table

```sql
CREATE TABLE concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_plan_id (plan_id),
    UNIQUE (plan_id, name)
);
```

**Why:** Decouples concepts from plans. Multiple plans can have concepts with the same name but different dependencies.

---

#### 2a.2.3 `edges` Table (Dependency Graph)

```sql
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    from_concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    to_concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_plan_id (plan_id),
    INDEX idx_from (from_concept_id),
    INDEX idx_to (to_concept_id),
    UNIQUE (plan_id, from_concept_id, to_concept_id),
    CHECK (from_concept_id != to_concept_id)  -- No self-loops
);
```

**Why:** Normalized edges enable:
- Efficient DAG validation with networkx
- Topological sort for scheduling
- Cycle detection
- Prerequisite queries

---

#### 2a.2.4 `concept_content` Table

```sql
CREATE TABLE concept_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id UUID NOT NULL UNIQUE REFERENCES concepts(id) ON DELETE CASCADE,
    explanation TEXT NOT NULL,
    quiz JSONB NOT NULL DEFAULT '[]',
    resources JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_concept_id (concept_id)
);
```

**JSONB Structure for `quiz`:**
```json
[
  {
    "type": "mcq",
    "question": "What is X?",
    "options": ["A", "B", "C"],
    "answer": "B"
  },
  {
    "type": "short_answer",
    "question": "Explain Y",
    "answer": "..."
  }
]
```

**JSONB Structure for `resources`:**
```json
[
  {
    "type": "video",
    "title": "...",
    "url": "https://..."
  },
  {
    "type": "docs",
    "title": "...",
    "url": "https://..."
  }
]
```

**Why:** JSONB allows:
- Schema flexibility (different quiz formats possible)
- PostgreSQL indexing on nested fields
- Easy serialization to Pydantic models
- Natural JSON response format for API

---

#### 2a.2.5 `progress` Table (User Study Progress)

```sql
CREATE TABLE progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'untouched',
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_plan_concept (plan_id, concept_id),
    UNIQUE (plan_id, concept_id),
    CHECK (status IN ('untouched', 'learned', 'struggling', 'skipped'))
);
```

**Why:** Decouples concept metadata from study progress. Enables:
- Multi-user support (add user_id later)
- Progress analytics
- Resetting progress without modifying concepts
- Query optimization (separate indices)

---

#### 2a.2.6 `schedule` Table (Study Calendar)

```sql
CREATE TABLE schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    day INTEGER NOT NULL,
    priority VARCHAR(50) NOT NULL DEFAULT 'medium',
    
    INDEX idx_plan_week (plan_id, week),
    UNIQUE (plan_id, concept_id),
    CHECK (week >= 1),
    CHECK (day >= 1 AND day <= 7),
    CHECK (priority IN ('high', 'medium', 'low'))
);
```

**Why:** Schedule is time-dependent and might be adjusted by adaptive replanning. Separate table allows:
- Efficient week/day queries for calendar view
- Easy schedule regeneration
- Analytics on study pacing

---

#### 2a.2.7 `schedule_history` Table (Audit Trail)

```sql
CREATE TABLE schedule_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES plans(id),
    original_schedule JSONB NOT NULL,
    new_schedule JSONB NOT NULL,
    reason VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_plan_id (plan_id),
    INDEX idx_created_at (created_at)
);
```

**Why:** Track adaptive replanning changes for analytics and debugging.

---

### 2a.3 SQLAlchemy Models

Location: `backend/app/models/database.py`

```python
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, CheckConstraint, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel

Base = declarative_base()

class Plan(Base):
    __tablename__ = "plans"
    
    id: Column[UUID] = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    topic: Column[str] = Column(String(200), nullable=False)
    exam_date: Column[datetime] = Column(DateTime, nullable=True)
    hours_per_day: Column[int] = Column(Integer, nullable=False, default=2)
    status: Column[str] = Column(String(50), nullable=False, default='active')
    created_at: Column[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: Column[datetime] = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    concepts: relationship("Concept", back_populates="plan", cascade="all, delete-orphan")
    edges: relationship("Edge", back_populates="plan", cascade="all, delete-orphan")
    progress: relationship("Progress", back_populates="plan", cascade="all, delete-orphan")
    schedule: relationship("Schedule", back_populates="plan", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint('hours_per_day >= 1 AND hours_per_day <= 8'),
        Index('idx_created_at', 'created_at'),
        Index('idx_status', 'status'),
    )


class Concept(Base):
    __tablename__ = "concepts"
    
    id: Column[UUID] = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('plans.id', ondelete='CASCADE'), nullable=False)
    name: Column[str] = Column(String(200), nullable=False)
    description: Column[str] = Column(Text)
    created_at: Column[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    
    plan: relationship("Plan", back_populates="concepts")
    content: relationship("ConceptContent", back_populates="concept", uselist=False, cascade="all, delete-orphan")
    outgoing_edges: relationship("Edge", foreign_keys="Edge.from_concept_id", back_populates="from_concept")
    incoming_edges: relationship("Edge", foreign_keys="Edge.to_concept_id", back_populates="to_concept")
    progress: relationship("Progress", back_populates="concept", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('plan_id', 'name'),
        Index('idx_plan_id', 'plan_id'),
    )


class Edge(Base):
    __tablename__ = "edges"
    
    id: Column[UUID] = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('plans.id', ondelete='CASCADE'), nullable=False)
    from_concept_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False)
    to_concept_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False)
    created_at: Column[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    
    plan: relationship("Plan", back_populates="edges")
    from_concept: relationship("Concept", foreign_keys=[from_concept_id], back_populates="outgoing_edges")
    to_concept: relationship("Concept", foreign_keys=[to_concept_id], back_populates="incoming_edges")
    
    __table_args__ = (
        UniqueConstraint('plan_id', 'from_concept_id', 'to_concept_id'),
        Index('idx_plan_id', 'plan_id'),
        Index('idx_from', 'from_concept_id'),
        Index('idx_to', 'to_concept_id'),
        CheckConstraint('from_concept_id != to_concept_id'),
    )


class ConceptContent(Base):
    __tablename__ = "concept_content"
    
    id: Column[UUID] = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    concept_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False, unique=True)
    explanation: Column[str] = Column(Text, nullable=False)
    quiz: Column[list] = Column(JSONB, nullable=False, default=[])
    resources: Column[list] = Column(JSONB, nullable=False, default=[])
    created_at: Column[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: Column[datetime] = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    concept: relationship("Concept", back_populates="content")
    
    __table_args__ = (
        Index('idx_concept_id', 'concept_id'),
    )


class Progress(Base):
    __tablename__ = "progress"
    
    id: Column[UUID] = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('plans.id', ondelete='CASCADE'), nullable=False)
    concept_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False)
    status: Column[str] = Column(String(50), nullable=False, default='untouched')
    last_updated: Column[datetime] = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    plan: relationship("Plan", back_populates="progress")
    concept: relationship("Concept", back_populates="progress")
    
    __table_args__ = (
        UniqueConstraint('plan_id', 'concept_id'),
        Index('idx_plan_concept', 'plan_id', 'concept_id'),
        CheckConstraint("status IN ('untouched', 'learned', 'struggling', 'skipped')"),
    )


class Schedule(Base):
    __tablename__ = "schedule"
    
    id: Column[UUID] = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('plans.id', ondelete='CASCADE'), nullable=False)
    concept_id: Column[UUID] = Column(PG_UUID(as_uuid=True), ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False)
    week: Column[int] = Column(Integer, nullable=False)
    day: Column[int] = Column(Integer, nullable=False)
    priority: Column[str] = Column(String(50), nullable=False, default='medium')
    
    plan: relationship("Plan", back_populates="schedule")
    
    __table_args__ = (
        UniqueConstraint('plan_id', 'concept_id'),
        Index('idx_plan_week', 'plan_id', 'week'),
        CheckConstraint('week >= 1'),
        CheckConstraint('day >= 1 AND day <= 7'),
        CheckConstraint("priority IN ('high', 'medium', 'low')"),
    )
```

---

### 2a.4 Pydantic Request/Response Schemas

Location: `backend/app/schemas/db_schemas.py`

```python
from pydantic import BaseModel, Field
from datetime import date, datetime
from uuid import UUID
from typing import Optional, List

# ============ Plan Schemas ============

class PlanCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    exam_date: Optional[date] = None
    hours_per_day: int = Field(ge=1, le=8, default=2)

class PlanUpdate(BaseModel):
    exam_date: Optional[date] = None
    hours_per_day: Optional[int] = Field(ge=1, le=8, default=None)
    status: Optional[str] = None

class PlanResponse(BaseModel):
    id: UUID
    topic: str
    exam_date: Optional[date]
    hours_per_day: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ============ Concept Schemas ============

class ConceptCreate(BaseModel):
    name: str
    description: str

class ConceptResponse(BaseModel):
    id: UUID
    plan_id: UUID
    name: str
    description: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============ Edge Schemas ============

class EdgeCreate(BaseModel):
    from_concept_id: UUID
    to_concept_id: UUID

class EdgeResponse(BaseModel):
    id: UUID
    plan_id: UUID
    from_concept_id: UUID
    to_concept_id: UUID
    
    class Config:
        from_attributes = True

# ============ Content Schemas ============

class QuizQuestion(BaseModel):
    type: str  # "mcq" or "short_answer"
    question: str
    options: Optional[List[str]] = None
    answer: str

class Resource(BaseModel):
    type: str  # "video", "docs", "article"
    title: str
    url: str

class ConceptContentCreate(BaseModel):
    explanation: str
    quiz: List[QuizQuestion] = []
    resources: List[Resource] = []

class ConceptContentResponse(BaseModel):
    id: UUID
    concept_id: UUID
    explanation: str
    quiz: List[dict]
    resources: List[dict]
    
    class Config:
        from_attributes = True

# ============ Progress Schemas ============

class ProgressUpdate(BaseModel):
    status: str  # "untouched", "learned", "struggling", "skipped"

class ProgressResponse(BaseModel):
    id: UUID
    plan_id: UUID
    concept_id: UUID
    status: str
    last_updated: datetime
    
    class Config:
        from_attributes = True

# ============ Schedule Schemas ============

class ScheduleItemResponse(BaseModel):
    id: UUID
    plan_id: UUID
    concept_id: UUID
    week: int
    day: int
    priority: str
    
    class Config:
        from_attributes = True

# ============ Full Plan Response (for PlanView) ============

class PlanFullResponse(BaseModel):
    id: UUID
    topic: str
    exam_date: Optional[date]
    hours_per_day: int
    created_at: datetime
    
    graph: dict  # { concepts: [...], edges: [...] }
    schedule: List[dict]
    content: dict  # { concept_id: content_data }
    progress: dict  # { concept_id: status }
    
    class Config:
        from_attributes = True
```

---

### 2a.5 Database Connection & Session Management

Location: `backend/app/database.py`

```python
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/conceptra"
)

# Async engine for high-concurrency scenarios
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", False),
    poolclass=NullPool,  # Disable pooling for serverless (add later)
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    """Dependency for FastAPI route handlers"""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Initialize database tables"""
    from app.models.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """Close database connection"""
    await engine.dispose()
```

---

### 2a.6 CRUD Repository Pattern

Location: `backend/app/repositories/plan_repository.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, insert, update, delete
from app.models.database import Plan, Concept, Edge, ConceptContent, Progress, Schedule
from app.schemas.db_schemas import PlanCreate, PlanUpdate, ProgressUpdate
from uuid import UUID
from datetime import datetime

class PlanRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, plan: PlanCreate) -> Plan:
        """Create a new plan"""
        db_plan = Plan(
            topic=plan.topic,
            exam_date=plan.exam_date,
            hours_per_day=plan.hours_per_day,
        )
        self.db.add(db_plan)
        await self.db.commit()
        await self.db.refresh(db_plan)
        return db_plan
    
    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        """Get plan with all relationships loaded"""
        result = await self.db.execute(
            select(Plan)
            .where(Plan.id == plan_id)
            .options(
                selectinload(Plan.concepts),
                selectinload(Plan.edges),
                selectinload(Plan.progress),
                selectinload(Plan.schedule),
            )
        )
        return result.unique().scalar_one_or_none()
    
    async def get_all_active(self) -> list[Plan]:
        """Get all active plans"""
        result = await self.db.execute(
            select(Plan)
            .where(Plan.status == 'active')
            .order_by(Plan.created_at.desc())
        )
        return result.scalars().all()
    
    async def update(self, plan_id: UUID, plan_update: PlanUpdate) -> Plan | None:
        """Update plan"""
        db_plan = await self.get_by_id(plan_id)
        if not db_plan:
            return None
        
        for key, value in plan_update.model_dump(exclude_unset=True).items():
            setattr(db_plan, key, value)
        
        await self.db.commit()
        await self.db.refresh(db_plan)
        return db_plan
    
    async def delete(self, plan_id: UUID) -> bool:
        """Delete plan (cascade deletes all related data)"""
        result = await self.db.execute(
            delete(Plan).where(Plan.id == plan_id)
        )
        await self.db.commit()
        return result.rowcount > 0

class ProgressRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def update_status(self, plan_id: UUID, concept_id: UUID, status: str) -> Progress | None:
        """Update concept status"""
        result = await self.db.execute(
            select(Progress)
            .where((Progress.plan_id == plan_id) & (Progress.concept_id == concept_id))
        )
        db_progress = result.scalar_one_or_none()
        
        if not db_progress:
            # Create new progress entry
            db_progress = Progress(
                plan_id=plan_id,
                concept_id=concept_id,
                status=status,
            )
            self.db.add(db_progress)
        else:
            db_progress.status = status
        
        await self.db.commit()
        await self.db.refresh(db_progress)
        return db_progress
    
    async def get_progress(self, plan_id: UUID) -> dict[UUID, str]:
        """Get all progress for a plan"""
        result = await self.db.execute(
            select(Progress)
            .where(Progress.plan_id == plan_id)
        )
        return {p.concept_id: p.status for p in result.scalars().all()}
```

---

## Phase 2b: API Endpoints & CRUD Routes

### 2b.1 New Endpoints

Location: `backend/app/api/routes/plans_db.py`

```
NEW ENDPOINTS:

POST   /api/v2/plans              → Create plan (from topic)
GET    /api/v2/plans/{id}         → Get full plan (with graph, schedule, content)
GET    /api/v2/plans              → List all plans
PATCH  /api/v2/plans/{id}         → Update plan (exam_date, hours_per_day)
DELETE /api/v2/plans/{id}         → Delete plan

GET    /api/v2/plans/{id}/graph   → Get just concept graph
GET    /api/v2/plans/{id}/schedule → Get just schedule
GET    /api/v2/plans/{id}/progress → Get user progress

PATCH  /api/v2/plans/{plan_id}/concepts/{concept_id}/progress  → Update concept status
GET    /api/v2/plans/{plan_id}/concepts/{concept_id}/content   → Get concept details

(Phase 1 endpoints still work for backward compatibility)
```

### 2b.2 Plan Creation Flow

```
POST /api/v2/plans {topic, exam_date, hours_per_day}
  ↓
Check if topic matches fixture
  ↓
If YES:
  - Load fixture data
  - Create plan in DB
  - Insert concepts, edges, content, schedule
  - Return plan ID
  
If NO:
  - Queue for AI generation (Phase 2c)
  - Create empty plan with status="pending"
  - Return plan ID (client polls for completion)
```

---

## Phase 2c: Connect React Frontend (No Breaking Changes)

### Why This Is Critical

The frontend currently works perfectly. We must **not break the UI** when switching from fixtures to database.

### Strategy: Dual API Versions

**Phase 1 API remains unchanged** — `/api/plans` still works with fixtures
**Phase 2 API parallel** — `/api/v2/plans` uses database

Frontend gets a config flag to switch:

```typescript
// frontend/.env.local
VITE_API_VERSION=v2  // or "v1" for fixtures
```

### 2c.1 API Client Update

Location: `frontend/src/api/client.ts`

```typescript
import type {
  ConceptContent,
  CreatePlanRequest,
  CreatePlanResponse,
  Plan,
} from '../types'

const API_VERSION = import.meta.env.VITE_API_VERSION || 'v1'
const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const API_ENDPOINT = `${API_BASE}/${API_VERSION}`

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function createPlan(body: CreatePlanRequest): Promise<CreatePlanResponse> {
  return request<CreatePlanResponse>(`${API_ENDPOINT}/plans`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getPlan(id: string): Promise<Plan> {
  return request<Plan>(`${API_ENDPOINT}/plans/${id}`)
}

export function updatePlanProgress(
  planId: string,
  conceptId: string,
  status: string,
): Promise<any> {
  return request(`${API_ENDPOINT}/plans/${planId}/concepts/${conceptId}/progress`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export function getConceptContent(
  planId: string,
  conceptId: string,
): Promise<ConceptContent> {
  return request<ConceptContent>(`${API_ENDPOINT}/plans/${planId}/concepts/${conceptId}/content`)
}
```

### 2c.2 Zero UI Changes Required

The frontend `PlanView.tsx` and components work identically because the API response format is unchanged:

```typescript
// Response format (identical in v1 and v2)
{
  id: UUID,
  topic: string,
  exam_date: date,
  hours_per_day: number,
  graph: { concepts, edges },
  schedule: [{ concept_id, week, day, priority }],
  content: { concept_id: { explanation, quiz, resources } },
  created_at: datetime
}
```

**Testing:** 
1. Set `VITE_API_VERSION=v1` → Tests with fixtures
2. Set `VITE_API_VERSION=v2` → Tests with database
3. Both show identical UI → Zero visual changes

---

## Phase 2d: AI Pipeline with Mistral

### 3d.1 Ollama Setup

```bash
# Install Ollama (Mac)
brew install ollama

# Pull Qwen3:4b (not Mistral for RAM constraints)
ollama pull qwen3:4b

# Start service (localhost:11434)
ollama serve
```

### 3d.2 AI Generation Endpoint

Location: `backend/app/api/routes/generation.py`

```
POST /api/v2/plans/generate
  {
    topic: string,
    exam_date: date,
    hours_per_day: number,
    num_concepts: integer (default 8),
  }

Response:
  {
    plan_id: UUID,
    status: "pending" | "completed" | "failed"
  }

Flow:
  1. Create empty plan (status="pending")
  2. Call Ollama with prompt
  3. Parse response with Pydantic validation
  4. Check DAG validity (networkx)
  5. Generate schedule (topological sort)
  6. Insert into database
  7. Update plan status="completed"
```

---

## Phase 2d.1 Prompt Engineering for Concept Generation

```python
CONCEPT_GENERATION_PROMPT = """
You are an educational curriculum designer. Generate a study plan for "{topic}".

Requirements:
1. Create exactly {num_concepts} core concepts
2. Concepts must form a directed acyclic graph (DAG)
3. Each concept must have 1-2 prerequisites maximum
4. Output MUST be valid JSON

Output JSON schema:
{{
  "concepts": [
    {{
      "id": "c1",
      "name": "Concept Name",
      "description": "One sentence description"
    }}
  ],
  "edges": [
    {{
      "from_id": "c1",
      "to_id": "c2"
    }}
  ]
}}

Topic: {topic}
Generate the JSON now:
"""
```

### 2d.2 Pydantic Validation for AI Responses

```python
from pydantic import BaseModel, validator
from typing import List
import networkx as nx
from uuid import UUID

class AIGeneratedConcept(BaseModel):
    id: str
    name: str
    description: str
    
    @validator('id')
    def validate_id(cls, v):
        if not v.startswith('c'):
            raise ValueError('Concept ID must start with "c"')
        return v

class AIGeneratedEdge(BaseModel):
    from_id: str
    to_id: str

class AIConceptResponse(BaseModel):
    concepts: List[AIGeneratedConcept]
    edges: List[AIGeneratedEdge]
    
    @validator('edges')
    def validate_dag(cls, edges, values):
        """Ensure generated graph is acyclic"""
        if 'concepts' not in values:
            return edges
        
        # Build networkx DAG
        G = nx.DiGraph()
        for c in values['concepts']:
            G.add_node(c.id)
        
        for e in edges:
            G.add_edge(e.from_id, e.to_id)
        
        # Check for cycles
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError('Generated graph contains cycles!')
        
        return edges
```

### 2d.3 AI Integration Service

```python
# backend/app/services/ai_service.py

import httpx
import json
from app.schemas.ai_schemas import AIConceptResponse
from pydantic import ValidationError

class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def generate_concepts(
        self,
        topic: str,
        num_concepts: int = 8,
    ) -> AIConceptResponse:
        """Generate concepts from topic using Ollama"""
        prompt = CONCEPT_GENERATION_PROMPT.format(
            topic=topic,
            num_concepts=num_concepts,
        )
        
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json={"model": "qwen3:4b", "prompt": prompt, "stream": False},
        )
        
        response.raise_for_status()
        data = response.json()
        
        # Extract JSON from response
        response_text = data.get("response", "")
        json_str = response_text[response_text.find('{'):response_text.rfind('}')+1]
        parsed = json.loads(json_str)
        
        # Validate with Pydantic
        try:
            return AIConceptResponse.model_validate(parsed)
        except ValidationError as e:
            raise ValueError(f"AI response validation failed: {e}")
```

---

## Phase 2d.4 Explanation & Quiz Generation

```python
EXPLANATION_PROMPT = """
Generate a clear, educational explanation for this concept in 2-3 sentences:

Concept: {concept_name}
Description: {concept_description}

Explanation:
"""

QUIZ_PROMPT = """
Generate 3 quiz questions for this concept:
- 2 multiple choice (4 options each)
- 1 short answer

Concept: {concept_name}
Explanation: {explanation}

Output as JSON:
{{
  "quiz": [
    {{
      "type": "mcq",
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "answer": "A"
    }}
  ]
}}
"""

RESOURCES_PROMPT = """
Find 3 educational resources for {concept_name}.
Return YouTube videos, documentation, and articles.

Output as JSON:
{{
  "resources": [
    {{"type": "video", "title": "...", "url": "https://..."}},
    {{"type": "docs", "title": "...", "url": "https://..."}}
  ]
}}
"""
```

---

## Phase 2e: Testing Strategy

### 2e.1 Database Tests

```python
# backend/tests/test_db.py

@pytest.mark.asyncio
async def test_create_plan():
    db = AsyncSessionLocal()
    repo = PlanRepository(db)
    
    plan = await repo.create(PlanCreate(
        topic="OS",
        exam_date=date(2026, 7, 15),
        hours_per_day=2
    ))
    
    assert plan.id is not None
    assert plan.topic == "OS"
    assert plan.status == "active"

@pytest.mark.asyncio
async def test_dag_validation():
    """Ensure cycle detection works"""
    db = AsyncSessionLocal()
    
    # Create plan with circular dependency
    plan = await PlanRepository(db).create(...)
    
    # Add cycle: c1 -> c2 -> c3 -> c1
    # Should fail validation
```

### 2e.2 API Integration Tests

```python
# backend/tests/test_api.py

@pytest.mark.asyncio
async def test_create_plan_api(client):
    response = await client.post(
        "/api/v2/plans",
        json={
            "topic": "Operating Systems",
            "exam_date": "2026-07-15",
            "hours_per_day": 2
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data

@pytest.mark.asyncio
async def test_get_plan_api(client):
    # Create plan first
    create_response = await client.post("/api/v2/plans", json={...})
    plan_id = create_response.json()["id"]
    
    # Retrieve it
    get_response = await client.get(f"/api/v2/plans/{plan_id}")
    
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["graph"]["concepts"] is not None
    assert data["schedule"] is not None
```

---

## Phase 2 Implementation Timeline

| Week | Task | Deliverable |
|------|------|-------------|
| **Week 1** | DB Design + SQLAlchemy Models | Working migrations, test DB creation |
| **Week 2** | CRUD Repository + API Endpoints | v2 API fully functional |
| **Week 3** | React Integration | Frontend switching to DB without breaking |
| **Week 4** | Ollama Setup + Prompt Engineering | Basic concept generation working |
| **Week 5** | Validation + Error Handling | Pydantic validation, retry logic |
| **Week 6** | DAG Validation + Schedule Gen | networkx integration, topological sort |
| **Week 7** | Content Generation (Explanations, Quiz, Resources) | Full plan generation end-to-end |
| **Week 8** | Testing + Polish | Unit tests, integration tests, docs |

---

## Phase 3: Production Features & Advanced Learning Optimization ✅

We have fully implemented and verified all Phase 3 objectives, transitioning Conceptra from a single-session generator into a complete, personalized study companion.

### Features Completed
- **Clerk Authentication Integration:** Secured the application using Clerk. Verified RS256 JWT tokens on the backend using Clerk's JWKS endpoint. Supported plan claiming (binding anonymous plans to users on sign-up) and user-owned dashboard lists.
- **AI-Driven Adaptive Replanning:** Built a schedule optimizer utilizing `networkx.descendants()` to locate struggling concept dependencies and redistributed remaining concepts using Groq Llama-3.3-70b-versatile, maintaining audit trails in `schedule_history`.
- **Spaced Repetition System (SRS):** Built a flashcard review pipeline utilizing the SM-2 algorithm. Introduced interactive review decks with confidence grading (1-5) to dynamically update study intervals.
- **Progress Analytics Dashboard:** Designed SVG progress meters, completion projections, and pacing stats dynamically calculated from database progress logs.
- **SSE Streaming Generation:** Developed a Server-Sent Events stream using Redis PubSub (with database polling fallback) that renders concept-by-concept loading screens with animations as the AI designs the study plan.
- **Export Study Materials:** Installed `reportlab` to compile and serve printable PDF study guides. Built pure-python RFC 5545 iCalendar `.ics` feed serialization for calendar subscriptions.

---

## Remaining Phases & Future Roadmap

To turn Conceptra into a market-leading study intelligence platform, we will tackle the remaining features across three distinct phases, built one-by-one.

### Phase 4: Collaborative Workspaces & Social Study Features 🚀 (Next up)
**Goal:** Empower students to study together, share knowledge, and build community around curated study guides.

#### 4.1 Key Feature Architecture & Routes
1. **Shared Study Plans:** Allow users to share links or collaborate on plans (read-only/write access).
   * `POST /api/v2/plans/{plan_id}/share` -> Generates a secure share link with permission scope (`view_only` or `collaborator`).
   * `GET /api/v2/plans/shared/{token}` -> Endpoint to access the shared plan and render in readonly mode, with a CTA to sign in and import/fork the plan.
2. **Global Community Library:** A directory where users can publish high-quality, generated study plans for anyone to search, upvote, and fork.
   * `GET /api/v2/library` -> List public study plans with sorting options (`trending`, `top_upvoted`, `newest`) and query search filters (`category`, `topic`).
   * `POST /api/v2/plans/{plan_id}/publish` -> Change a plan's status to public and index it in the global directory.
   * `POST /api/v2/plans/{plan_id}/fork` -> Clone a plan's graph structures, schedules, and explanations into the current user's profile under a new plan UUID.
3. **Study Rooms / Groups:** Invite friends to study the same concepts, tracking group velocity and dashboard rankings.
   * `POST /api/v2/groups` -> Create a collaborative study group.
   * `POST /api/v2/groups/{group_id}/invite` -> Generate invite link or trigger username search invitation.
   * `GET /api/v2/groups/{group_id}/dashboard` -> Returns leaderboard ranking of study progress across members (ranking by concepts completed/learned).

#### 4.2 Proposed Database Schema Changes:
```sql
CREATE TABLE collaborative_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    created_by VARCHAR(128) NOT NULL, -- Clerk User ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE group_members (
    group_id UUID REFERENCES collaborative_groups(id) ON DELETE CASCADE,
    clerk_user_id VARCHAR(128) NOT NULL,
    role VARCHAR(50) DEFAULT 'member', -- owner, admin, member
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, clerk_user_id)
);

CREATE TABLE shared_plans (
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    group_id UUID REFERENCES collaborative_groups(id) ON DELETE CASCADE,
    permission VARCHAR(50) DEFAULT 'view', -- view, edit
    PRIMARY KEY (plan_id, group_id)
);

CREATE TABLE plan_upvotes (
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    clerk_user_id VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (plan_id, clerk_user_id)
);
```

#### 4.3 UI/UX Layout Mockups & Components:
- **`CommunityLibrary.tsx`**: A dashboard grid displaying cards of public plans, showing name, description, tags, author name, and number of upvotes. Features tabs to toggle between "Trending" and "My Library". Includes a fork CTA on each card.
- **`GroupDashboard.tsx`**: Renders group progress as horizontal bar charts comparing member study velocity. Includes a real-time message stream component in the sidebar displaying event alerts (e.g. *"Alice has mastered 'Dynamic Programming' in the Algorithms Group"*).
- **`Sidebar/ShareModal`**: Popover on the PlanView sidebar allowing users to select visibility (Private, Public Library, or Shared Group) and click a button to copy invite links.

#### 4.4 Tactics & Step-by-Step Execution:
1. **Step 4.1: Database Migrations:** Establish groups, members, upvotes, and share schemas. Optimize query performance by indexing `plan_upvotes(plan_id)` and `group_members(clerk_user_id)`.
2. **Step 4.2: Shared Workspace & Group APIs:** Build backend routes for group management, membership, plan sharing, and upvoting.
3. **Step 4.3: Community Library Page:** Develop the community discovery UI with category categorization, search routing, and duplicate cloning ("Forking") logic.
4. **Step 4.4: Leaderboard & Activity Feed:** Build WebSocket sync support to emit study progress updates to active group members, rendering notifications and refreshing leaderboard logs.

---

### Phase 5: Conversational AI Learning Tools (Active Tutor Chat) 🔮
**Goal:** Transform the static explanation panel into an active conversational tutor that explains complex concepts, grades open-ended quizzes, and customizes content on the fly.

#### 5.1 Key Feature Architecture & LLM Prompts
1. **Active Tutor Chat Drawer:** Let students toggle from standard definitions into a conversational tutor window.
   * Prompting Context: When the conversation starts, prime the LLM with system logs detailing the student's progress status, exam date, and plan details:
     ```text
     You are "Conceptra Tutor", a world-class teacher. 
     The student is studying: {concept_name}. 
     Description: {concept_description}. 
     Their current status is: {concept_status}.
     Help explain this concept in response to their questions. Avoid answering unrelated topics. 
     If they ask for sample code, write elegant syntax with step-by-step notes.
     ```
2. **Dynamic Flashcard Extension:** Let users request additional practice questions to test themselves.
   * `POST /api/v2/plans/{plan_id}/concepts/{concept_id}/quiz/extend` -> Triggers Groq to generate 3 additional practice flashcards tailored specifically to the topics discussed in the tutor chat.
3. **LLM-Based Soft Grading Engine:** Move from strict string equality on quiz answer submissions to AI soft grading.
   * When checking a short-answer quiz, instead of comparing exact strings, send the user's response to the LLM:
     ```text
     Question: {question}
     Reference Answer: {answer}
     Student Response: {student_response}
     
     Grade the student response on a scale of 0-100. Provide a short 1-sentence comment explaining what was correct and what was missing. 
     Return valid JSON matching: {"score": 85, "explanation": "You correctly stated X, but forgot to mention Y."}
     ```
4. **Syllabus PDF Highlight Overlay:**
   * When syllabus files are uploaded, track character offsets and coordinate mappings. Show a split-pane layout: on the left, the rendered PDF canvas; on the right, the ConceptPanel with links. Clicking "Show Source" on a concept highlights the extracted paragraphs on the PDF page.

#### 5.2 Proposed Database Schema Changes:
```sql
CREATE TABLE concept_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id VARCHAR(128) NOT NULL,
    concept_id UUID REFERENCES concepts(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- user, assistant
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_concept (clerk_user_id, concept_id)
);
```

#### 5.3 Tactics & Step-by-Step Execution:
1. **Step 5.1: Conversational Chat API:** Implement the DB-backed chat messaging endpoint with pagination and sliding chat message history limits.
2. **Step 5.2: Tutor Chat UI:** Integrate an expandable chatbot pane inside `ConceptPanel.tsx`. Build markdown rendering support (e.g. `react-markdown` and syntax highlighters for code blocks).
3. **Step 5.3: Soft Grading Engine:** Integrate Groq API callbacks for grading short-answer quizzes. Provide a detailed grading scorecard indicating areas of misunderstanding.
4. **Step 5.4: Split PDF Viewer:** Implement a custom PDF canvas interface using `pdfjs-dist` to overlay highlighted segments corresponding to concept extractions.

---

### Phase 6: Cloud Production Deployment, Performance, and Monitoring 🔮
**Goal:** Transition from a local development workspace into a secure, scaled, auto-recovering multi-cloud deployment with metrics logging and alert diagnostics.

#### 6.1 Multi-Container Architecture Configuration
1. **Nginx Proxy Configuration:**
   Nginx acts as the single gateway ingress, serving React files and proxying requests to the backend server:
   ```nginx
   server {
       listen 80;
       server_name app.conceptra.com;

       location / {
           root /usr/share/nginx/html;
           try_files $uri $uri/ /index.html;
       }

       location /api {
           proxy_pass http://api-backend:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
       
       #  SSE connection optimization
       location ~ ^/api/v2/plans/[a-f0-9-]+/stream$ {
           proxy_pass http://api-backend:8000;
           proxy_set_header Host $host;
           proxy_set_header Connection '';
           proxy_http_version 1.1;
           chunked_transfer_encoding off;
           proxy_buffering off;
           proxy_read_timeout 600s;
       }
   }
   ```
2. **Gunicorn Production Setup:**
   Run the ASGI application with `uvicorn.workers.UvicornWorker` inside container settings:
   `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120`

#### 6.2 Caching & Invalidation Strategy (Redis)
- **Caching endpoints:** Cache analytical boards `/analytics` and read-only maps `/plans/{id}`.
- **Cache Invalidation rules:**
  - Invalidate `/analytics` and `/plans/{id}` whenever concept progress status is updated (`PATCH /progress`).
  - Invalidate plan caches whenever a schedule is replanned (`POST /replan`).
  - Set TTL of 1 hour on dynamic endpoints.

#### 6.3 Deployment & Infrastructure Diagram (AWS Fargate)
```
          HTTPS Request
               ↓
     Application Load Balancer (ALB)
          /         \
   Frontend Container  Backend Container (FastAPI)
   (Nginx & React)     (Gunicorn/Uvicorn ASGI)
                           /         \
            RDS Postgres DB           ElastiCache Redis
            (ACID storage)            (PubSub & Cache)
```

#### 6.4 Tactics & Step-by-Step Execution:
1. **Step 6.1: Docker & Nginx Orchestration:** Write multi-stage Dockerfiles optimizing asset builds (minimizing React bundle sizes). Write docker-compose files mimicking production orchestration for local QA checks.
2. **Step 6.2: CI/CD Pipeline Build:** Set up GitHub Actions workflow:
   - Run type checks (`tsc --noEmit`) and pytest suites.
   - Build docker tags, push them to AWS ECR, and execute a rolling container update deployment command.
3. **Step 6.3: Provisioning Cloud Services (IaC):** Write Terraform templates to provision secure subnets, ALB routes, Postgres DB instances, and serverless compute clusters.
4. **Step 6.4: Monitoring & Diagnostics Integration:** Configure Prometheus metrics routes (`/metrics`) inside FastAPI. Add Sentry logging capture to trigger notifications to Discord/Slack on pipeline generation failures.

---

## Tactical Execution Plan: Proceeding Phase-by-Phase

To execute this roadmap efficiently and maintain stability:

1. **Step-by-Step Isolation:** We will proceed with **one phase at a time**.
2. **Branching Strategy:** Each task in the roadmap will be developed on a feature branch (e.g., `feature/phase-4-collaboration`) and merged into `main` only after passing typescript verification and backend tests.
3. **Database Consistency:** Database migration scripts (Alembic) will be run and tested for backward compatibility on existing plans before backend endpoints are merged.
4. **Visual Testing:** Design iterations will be validated visually first using the `generate_image` mockup tool and iterated on with stakeholders before locking in CSS systems.

---

This Master Roadmap ensures that Conceptra scales sustainably from a simple study guide generator into a globally collaborative, AI-powered active study companion.
