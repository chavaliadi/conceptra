# Conceptra Phase 2: Production Database & AI Pipeline
## Detailed Implementation Plan

**Last Updated:** June 15, 2026
**Project:** Conceptra - Study Intelligence Tool
**Status:** Phase 2 Planning (Ready for Development)

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

## Phase 3: Production Features

### 3.1 Planned Features (Not Phase 2)

- **User Authentication** (JWT tokens, session management)
- **Multi-User Support** (user profiles, plan sharing)
- **Analytics Dashboard** (progress tracking, learning insights)
- **Spaced Repetition** (SRS algorithm integration)
- **Export Functionality** (PDF, JSON export)
- **Adaptive Replanning** (AI-powered schedule adjustment)
- **Caching Layer** (Redis for frequently accessed plans)
- **Advanced Search** (full-text search across concepts)

### 3.2 Deployment Considerations (Future)

- Docker containerization
- CI/CD pipeline (GitHub Actions)
- AWS/GCP deployment
- Horizontal scaling (load balancing)
- Database backups and disaster recovery

---

## Why This Order Matters

### Problem: The Spaghetti Test
If you build AI first, then realize the database is wrong, you have to:
1. Rewrite AI prompts
2. Rewrite database schema
3. Rewrite API responses
4. Rewrite frontend integration

You're touching every layer simultaneously = exponential debugging.

### Solution: The Layered Approach
```
Layer 1: Database (stable baseline)
         ↑ Test this before moving on
Layer 2: CRUD API (proven data flow)
         ↑ Test this before moving on
Layer 3: React Integration (UI verified)
         ↑ Test this before moving on
Layer 4: AI Pipeline (final layer)
         ↑ Everything below is rock solid
```

If AI breaks, you immediately know it's the AI. Not the database. Not the API. **Just the AI.**

---

## Recruiting Value

This architecture demonstrates:

1. **Systems Design** — Normalized schema, indexed queries, DAG reasoning
2. **API Design** — Versioning strategy, Pydantic validation, repository pattern
3. **Software Engineering** — Separation of concerns, layered testing, error handling
4. **AI/ML** — Prompt engineering, response validation, retry logic
5. **Database** — Schema design, migrations, query optimization

**Interview Question You'll Be Ready For:**
> "Walk us through your Conceptra architecture."

**Your Answer:**
> "I built it in layers. First, a normalized PostgreSQL schema with concepts, edges, and content. Then FastAPI CRUD endpoints with Pydantic validation. Then I connected React to use database instead of fixtures—zero UI changes. Finally, I plugged Ollama + Qwen3:4b into a generation endpoint with networkx DAG validation. Each layer was independently testable, so debugging was isolated."

That's a **hiring conversation**, not a rejection.

---

## Summary

**Phase 1:** ✅ Working UI with fixtures
**Phase 2:** Build production database and AI pipeline layer-by-layer
**Phase 3:** Multi-user features, analytics, deployment

The key principle: **Isolate failure points through layered architecture.**

Good luck!
