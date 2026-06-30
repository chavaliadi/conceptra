# Conceptra — Final Product Plan & Detailed Workflow

**One-sentence definition (README-ready):**
> Conceptra transforms an unstructured course syllabus into a personalized learning system by constructing a dependency graph, tracking concept mastery over time, and continuously adapting a student's study plan based on performance rather than completion.

Every decision below is tested against that sentence. If a feature doesn't make it truer, it's a supporting feature, not core.

---

## 1. Why this shape (recap of the design debate)

Four rounds of review converged on the same core insight from different angles:

- Explanations, video-finding, and book recommendations are commodity LLM tasks — ChatGPT/Gemini/Claude/Perplexity already do them. Competing there is a losing position.
- What none of them do: **hold state about one specific student over time** — their mastery, their weak spots, their schedule, their actual exam syllabus. That state is Conceptra's moat.
- The LLM should be **a service the system calls**, not the center of the system. The database is the source of truth; the LLM enriches it.

This reframes the build: stop asking *"what can the LLM generate?"* and start asking *"what data should I own that a chatbot doesn't?"*

---

## 2. Architecture — Three Layers

```
┌─────────────────────────────────────────────┐
│  LAYER 1 — KNOWLEDGE LAYER  (built per-syllabus, mostly static) │
│  Syllabus → Concepts → Dependency DAG → Difficulty → Readings    │
└─────────────────────────────────────────────┘
                      │  (read-only reference)
                      ▼
┌─────────────────────────────────────────────┐
│  LAYER 2 — STUDENT LAYER  (changes every day, per student)       │
│  Mastery → Quiz Attempts → Confidence → SM-2 Schedule → Weak Areas│
└─────────────────────────────────────────────┘
                      │  (consumed by)
                      ▼
┌─────────────────────────────────────────────┐
│  LAYER 3 — AI LAYER  (stateless, queries Layers 1 & 2)            │
│  Tutor Q&A → Concept Explanation → Edge Explanation → Resources  │
└─────────────────────────────────────────────┘
```

**Rule of thumb:** Layer 1 is built once per syllabus and rarely changes. Layer 2 mutates constantly and is the actual product. Layer 3 never stores anything — every call reads from 1 and 2 and returns text. If you're ever unsure where new logic belongs, ask: "does this change per-student, per-day?" → Layer 2. "Is this true regardless of who's studying?" → Layer 1. "Is this just language generation with no memory?" → Layer 3.

---

## 3. Data Model

### Layer 1 — Knowledge Layer

```
Syllabus
├── id
├── subject_domain          ("Computer Networks", "DSA", ...) — inferred once at extraction
├── source_book(s)           [{book, edition}]  — e.g. Tanenbaum 5th + Forouzan 4th
├── raw_text
└── uploaded_at

Concept
├── id
├── syllabus_id (FK)
├── name
├── difficulty               enum: easy | medium | hard   (LLM-assigned default)
├── difficulty_source        enum: llm_assigned | observed_adjusted   (defaults to llm_assigned — column exists now so difficulty can later evolve from real aggregate student mastery data, NOT built in v1)
├── content_generation_version   int, default 1   (bumped only on a deliberate, user-triggered regeneration — never auto-invalidated on a timer; preserves reproducibility without silent overwrites)
├── source_hint              [{source, chapter, edition}] | null   — "source" is free text, NOT assumed to be a textbook (this exact syllabus cites "Notes I shared" and "PPT I have shared" as valid sources alongside Tanenbaum/Forouzan — the field has to match that, not assume every source has a chapter number)
├── is_inferred_reading      bool   — True if source_hint was null and reading list is general knowledge fallback
├── recommended_reading      [{source, chapter, edition}]
└── UNIQUE(syllabus_id, name)   ← prevents duplicate concept rows on re-upload

ConceptDependency   (the DAG — just two columns + a confidence score, NOT a graph database)
├── concept_id (FK)
├── depends_on_concept_id (FK)
├── confidence               float (0-1)  — LLM-assigned certainty this edge is real
├── source                   enum: llm_inferred | seeded_from_prior_graph | user_edited
└── CHECK: insert-time cycle detection (topological sort) — reject any edge that creates a cycle

ConceptResource
├── concept_id (FK)
├── type                     "video" | "article" | "docs"
├── platform                 free text (NOT enum) — e.g. "Neso Academy", "NPTEL", anything the LLM names
├── query                    search keywords (LLM-generated, never a raw URL)
└── resolved_url             computed server-side at insert time, never re-computed per request
```

### Layer 2 — Student Layer

```
ConceptMastery
├── student_id (FK)
├── concept_id (FK)
├── mastery_pct              float 0-100   — derived, NOT user-entered, NOT LLM-guessed
├── retention_pct            float 0-100   — decays over time since last review
├── confidence_level          float 0-1     — from MCQ confidence slider, blended with correctness
├── attempts_count
├── last_reviewed_at
├── next_review_at            (SM-2 output)
├── ease_factor                (SM-2 internal state)
├── interval_days              (SM-2 internal state)
└── UNIQUE(student_id, concept_id)

QuizAttempt
├── id
├── student_id (FK)
├── concept_id (FK)
├── question_text             (LLM-generated MCQ)
├── options                   [4 choices]
├── correct_option_index
├── selected_option_index
├── is_correct                 bool  — objective, computed by comparing indices, NOT LLM-graded
├── confidence_reported        float 0-1   — student's self-rated confidence slider, captured separately
├── response_time_ms           int   — free behavioral signal, captured now; not used in the v1 mastery blend, but available if confidence is later split into knowledge/behavioral/retention components
└── answered_at

StudySessionView   (DERIVED, not a stored table for v1 — see §5.9)
└── reconstructed by grouping QuizAttempt rows where gap between consecutive
    timestamps < 30 minutes; rendered as a report, not persisted.
```

### Layer 3 — AI Layer
Stateless. No tables. Every function takes `(concept, student_mastery_record)` as input and returns text. Nothing here is ever the source of truth for anything in Layer 1 or 2 — it only reads.

---

## 4. End-to-End Workflow

### Phase 0 — Upload
1. Student uploads syllabus PDF via `/upload-syllabus`.
2. Request **must** be `multipart/form-data` (file upload) — the API client's header-merge logic must NOT force `Content-Type: application/json` onto this request, or the upload silently breaks. (This was a real bug caught earlier — see §6.10.)
3. Text extracted from PDF, passed as `syllabus_text` through `_create_plan_logic` → background worker. Add an explicit test asserting this string survives all three hops — it's exactly the kind of kwarg that quietly becomes `None` in a future refactor.

### Phase 1 — Concept Extraction (Layer 1)
1. Single LLM call over `syllabus_text` returns a list of `ExtractedConcept` objects: `name`, `subject_domain`, `source_hint` (nullable), `difficulty`.
2. **Why `source_hint` is optional, not forced:** this exact syllabus names "Tanenbaum 5th, Forouzan 4th" per section — extract that faithfully. A syllabus with no book hints shouldn't force the LLM to invent a fake chapter number. If absent → `null`, and `is_inferred_reading = True` downstream so the UI can label it "general reference" instead of pretending it's exam-specific.
3. **Dedup pass:** when two books map to the same concept cluster (as Tanenbaum ch.1 + Forouzan ch.1-2 do here), merge into **one** concept row with two entries in `recommended_reading` — never emit duplicate concept rows because two books happen to cover the same topic.
4. **Difficulty tagging happens here, not later** — it feeds the deterministic study-time calculation in Phase 3 and the dependency-confidence weighting in Phase 2.

### Phase 2 — Dependency DAG (Layer 1)
1. LLM proposes a **candidate** set of edges (`depends_on`) between concepts, with a confidence score per edge — never trusted blindly.
2. Run a topological-sort / cycle check on insert. Any edge that would create a cycle is rejected outright, never stored.
3. **Seeding, not canonical reuse:** if a previously-validated graph exists for a similar `(book, edition)` pairing, feed it into the LLM's prompt as a prior reference — this improves consistency on repeat subjects without committing to a canonical-graph merge/dedup system (rejected as over-scoped for v1 — different universities' syllabi on the *same* edition still cover near-identical structure, so this is a quality boost, not a correctness requirement).
4. Graph is **per-syllabus** by default. No cross-university canonical table. No graph database — `ConceptDependency` is two foreign keys and a float. Render with React Flow on the frontend; that's sufficient, and interviewers care that you understand *why it's a DAG*, not which database stores it.
5. User-editable in a later version (student says "no, CRC doesn't depend on Hamming" → edge deleted, `source = user_edited`) — flagged as Nice-to-Have, not required for v1.

### Phase 3 — Difficulty & Study Time (Layer 1)
1. Each concept already has a `difficulty` tag from Phase 1.
2. Study time is **computed in code, never asked of the LLM as a final number**:
   ```
   easy → 30 min, medium → 60 min, hard → 90 min
   total_hours = sum(per-concept estimate) / 60
   ```
3. This mirrors the resource-resolver principle used throughout this plan: **let the LLM tag, let your code compute.** Never let the LLM output a final aggregate number directly — it's an unverifiable guess dressed up as data.

### Phase 4 — Resources (Layer 1, deliberately small — 10% of effort)
1. LLM outputs `{type, platform, query}` per resource — never a raw URL. `platform` is **free text**, not an enum (see §5.3 for why), drawn loosely from a subject-scoped "preferred sources" hint built from a registry.
2. **Two-tier resolution, server-side, at insert time:**
   - **Tier 1 (verified registry):** a plain config dict (`platform_registry.py`) mapping known platform names → exact URL templates (YouTube search for Neso Academy/Gate Smashers/Abdul Bari/etc., Wikipedia *search* endpoint — never a guessed slug — for Wikipedia, Google `site:` search for GeeksforGeeks, etc.). Adding a new platform = one dict entry, zero schema/redeploy.
   - **Tier 2 (safe fallback):** anything not in the registry never 404s — it degrades to a type-aware generic search (video → YouTube search, article/docs → Google search). This tier is what actually eliminates the original Rickroll/hallucinated-URL problem; the registry is a quality layer on top of a foundation that's already 100% safe.
3. Every Tier-2 fallback is logged (`platform`, `query`). Periodically reviewing these logs is the registry's **growth loop** — frequently-seen unmapped platforms (e.g. "NPTEL" showing up repeatedly) get promoted into Tier 1. The system improves from real usage instead of a static upfront list.
4. Query strings are URL-encoded (`quote_plus`) before template insertion — unencoded spaces/special characters literally break the resulting URL.
5. **Explicitly capped scope:** no ranking engine, no "best video" discovery, no 300-platform registry, no YouTube Data API calls to fetch a single "verified" video. This is a deliberate, permanent boundary — not a v1 simplification to revisit later. Resources stay supporting, not core.

### Phase 5 — Quiz Generation (Layer 2 input)
1. Per concept, LLM generates 3–5 multiple-choice questions with 4 options each and a marked correct index.
2. **Why MCQ, not free-text + LLM grading:** free-text grading reintroduces the exact unreliability this whole plan has been eliminating elsewhere (grading consistency varies call to call; a correctly-phrased-differently answer can be marked wrong). MCQ has an objective ground truth — comparing `selected_option_index == correct_option_index` needs no LLM judgment call at grading time.
3. **Why MCQ, not pure self-rated recall (0–5 self-rating):** self-rated confidence alone is a known failure mode — students reliably overrate their own recall ("I think I know CRC" → clicks 5 → couldn't actually solve an exam problem). Pure self-report would feed false-positive mastery straight into the scheduler.
4. **The fix — capture both signals separately, on every question:**
   - Objective: was the selected option actually correct? (binary, no ambiguity)
   - Subjective: a confidence slider, captured alongside the answer, before or after seeing correctness
5. This gives the hybrid signal the design debate converged on, without adding LLM-based answer grading as a new unreliable dependency.

### Phase 6 — Mastery & SM-2 Scheduling (Layer 2 — the actual product)
1. Use the **SM-2 spaced-repetition algorithm** (open-source, well-documented — do not invent custom scheduling math).
2. Mastery update blends correctness and confidence rather than using either alone:
   - Correct + high confidence → mastery rises significantly (genuine knowledge)
   - Correct + low confidence → mastery rises slightly (lucky guess or shaky recall)
   - Incorrect + high confidence → **strongest negative signal** — this is the exact "thought I knew it, didn't" case that motivated the hybrid design
   - Incorrect + low confidence → mastery drops, but the student already knew they were unsure
3. SM-2 outputs `ease_factor`, `interval_days`, and `next_review_at` per concept per student — this is what drives the scheduler in Phase 7. A missed question on a concept doesn't wait for "next week"; SM-2 naturally pulls `next_review_at` forward.
4. `retention_pct` decays as a function of time since `last_reviewed_at` — gives the weak-topic dashboard a live, not just point-in-time, signal.

### Phase 7 — Adaptive Scheduler / Revision Planner (Layer 2 → Layer 3 surface)
1. Query: for the logged-in student, pull all `ConceptMastery` rows where `next_review_at <= today`, ordered by ascending `mastery_pct` (weakest first) and respecting `ConceptDependency` ordering (don't surface a concept whose prerequisite hasn't been studied yet).
2. This is largely a query + a calendar/list view over existing SM-2 state — low *new* engineering risk once Phase 6 is solid.
3. This is the feature that most directly answers "why not ChatGPT" — a chat window has no `next_review_at` for you, and never will, because it holds no state between sessions.

### Phase 8 — Weak-Topic Dashboard (Layer 2 surface)
1. Aggregate query over `ConceptMastery`: lowest mastery_pct, lowest retention_pct, highest incorrect-while-confident count.
2. Low engineering risk — it's a `SELECT ... ORDER BY` and a chart, not new logic. Don't over-invest here; the value is in the underlying data (Phase 6), not the visualization.

### Phase 9 — AI Tutor (Layer 3, stateless for v1)
1. Input per call: `(concept content, student's current ConceptMastery record)`. Output: a grounded explanation or answer.
2. **Explicitly scoped as stateless Q&A** — no persistent multi-turn conversational memory across sessions for v1. That's a real, much larger feature (true conversational memory) and is not required to make the core "why not ChatGPT" argument, since the *system* already remembers the student via Layer 2 — the tutor doesn't need to remember the conversation, it needs to know the student's mastery, which it already has.
3. Because the tutor is grounded in the student's actual mastery record, it can do things a raw ChatGPT session structurally can't without being manually told: e.g. proactively flag "you've gotten this wrong twice with high confidence — let's slow down here," without the student having to surface that themselves.

---

## 5. Locked Design Decisions — What and Why (quick-reference)

| # | Decision | Why |
|---|---|---|
| 5.1 | **Mastery, not Progress** | "80% complete" is a vanity metric. "80% complete, 42% quiz accuracy, declining retention" is the number that makes the scheduler meaningful and makes Conceptra defensible. |
| 5.2 | **Three-layer split (Knowledge / Student / AI)** | Knowledge is built once and is near-static; Student state mutates daily and is the real product; AI is stateless and only ever reads from the other two. Prevents the LLM from re-becoming the center of the project. |
| 5.3 | **`platform` is free text + two-tier resolver, not a hardcoded enum** | A fixed 9-value enum is subject-blind (great for Computer Networks, useless for DSA/DBMS/ML syllabi) and can't grow without a redeploy. Free text + a registry-with-fallback gets unlimited coverage while still guaranteeing zero broken links — coverage and reliability aren't actually in tension once the resolver has a safe fallback tier. |
| 5.4 | **Study time & total hours computed in code, not asked of the LLM** | A bare numeric estimate from the LLM is an unverifiable guess. Tag difficulty (LLM), compute the sum (code) — same principle as the resource resolver: LLM tags, code computes. |
| 5.5 | **MCQ + separate confidence slider, not pure self-rated recall, not LLM-graded free text** | Pure self-rating lets students overrate themselves (false-positive mastery). LLM-graded free text reintroduces grading-consistency risk into a system built around eliminating exactly that kind of unreliability. MCQ gives an objective ground truth; the confidence slider supplies the subjective signal separately. |
| 5.6 | **Per-syllabus dependency graph, seeded (not merged) from prior similar graphs** | A true canonical graph shared across universities/editions is a real research problem (different curricula, different terminology, unclear merge/split rules) — over-scoped for v1. Per-syllabus by default, with an optional similarity-seeded prompt for consistency, gets most of the benefit without the canonical-graph maintenance burden. |
| 5.7 | **No graph database** | `ConceptDependency` is two foreign keys, a confidence float, and a cycle check at insert time. Neo4j/embeddings would be solving a problem this scale doesn't have. |
| 5.8 | **AI Tutor is stateless for v1** | The system's "memory" already lives in Layer 2 (mastery records); the tutor doesn't need its own separate conversational memory to be meaningfully better than a raw chatbot. Multi-turn tutor memory is a clearly larger, separately-scoped future feature. |
| 5.9 | **No dedicated "Study Session" table for v1** | Most of the value (what was covered today, average score) can be *derived* from timestamped `QuizAttempt` rows grouped by a time-gap rule, with zero new schema. The parts that genuinely can't be derived — a deliberate reflection-text field, an explicit start/stop estimated-vs-actual flow — are real new scope and are listed as Nice-to-Have, not silently folded into the Foundation phase. |
| 5.10 | **Resources stay ~10% of total effort, permanently** | Ranking "the best video" requires competing with Google/YouTube's own ranking infrastructure — an unwinnable and unnecessary fight. A reliable, ever-growing fallback resolver is sufficient; a discovery/ranking engine is explicitly out of scope, not deferred. |
| 5.11 | **`UNIQUE(syllabus_id, concept_name)` constraint, upsert on re-upload** | Without it, re-uploading a corrected syllabus PDF (which will happen during iteration) silently duplicates the entire concept list instead of updating it in place. |
| 5.12 | **API client header merge must check for `FormData`** | Forcing `Content-Type: application/json` onto every request breaks the syllabus upload itself, which needs browser-set `multipart/form-data` boundaries. This is the one bug that could re-break the feature the whole plan is built around. |
| 5.13 | **Generated explanatory content (analogy, exam tip, summary) stored permanently — no TTL cache, no auto-regeneration** | Consistency matters here the same way reliable resource links did: a student should see the same explanation every time they open a concept, not a different one per view because a background cache expired. `content_generation_version` exists so content *can* be deliberately regenerated later via an explicit action, without ever committing to silent, timer-based invalidation. |
| 5.14 | **`difficulty_source` and `content_generation_version` added as schema columns now, not built as features** | Lets difficulty evolve from real observed mastery data later, and lets explanation content be intentionally regenerated later — both with zero future migration. Cost: two columns, zero v1 build days. |
| 5.15 | **`response_time_ms` captured on every `QuizAttempt` now, unused in v1 logic** | Splitting confidence into knowledge/behavioral/retention components is a legitimate later idea. Capturing the raw signal now means it's available retroactively without needing students to re-answer old questions. |
| 5.16 | **`source_hint` / `recommended_reading` use a free-text `source` field, not a "book"-only field — but stay structured, not flattened to one string** | This exact syllabus cites "Notes I shared" and "PPT I have shared" as valid sources alongside Tanenbaum/Forouzan — a field that assumes every source is a textbook with a chapter number doesn't match the real input. Kept as `{source, chapter, edition}` rather than a single string because `source + edition` is still the matching key used for dependency-graph seeding (§5.6) — full flattening would quietly break that earlier decision. |

---

## 6. Roadmap with Honest Estimates

| Phase | Feature | Estimate | Risk notes |
|---|---|---|---|
| 1 | Syllabus parsing (already mostly built) | 1–2 days | Low |
| 2 | Concept extraction + dedupe + subject_domain + source_hint | 2–3 days | Low — mostly spec'd already |
| 3 | Dependency DAG (candidate edges → confidence → cycle check → store) | 3–4 days | Medium. Excludes the user-editable graph UI — that's a separate v1.1 ticket |
| 4 | Difficulty tagging + deterministic study-time calc | 1 day | Low — pure code, no LLM call needed beyond existing difficulty tag |
| 5 | Resource registry + two-tier resolver (finish what's designed, then stop) | 1–2 days | Low — fully spec'd already |
| 6 | MCQ generation (3–5 per concept) | 2–3 days | Medium — quality of distractors needs spot-checking |
| 7 | Mastery update logic (correctness × confidence blend) + SM-2 wiring | 3–4 days | Medium — SM-2 itself is free/open-source, this is integration work |
| 8 | Adaptive scheduler (query + ordering by mastery + dependency) | 2–3 days | Low-medium |
| 9 | Weak-topic dashboard | 1–2 days | Low |
| 10 | AI Tutor (stateless Q&A grounded on concept + mastery) | 2–3 days | Low-medium — pin the stateless scope hard, or this silently grows |
| — | **Total — core build** | **~18–25 focused days** | Treat as your flagship; plan time-split accordingly against your other ~15 portfolio projects |
| Nice-to-have | User-editable DAG edges | +2–3 days | Defer past v1 |
| Nice-to-have | Reflection-text / explicit session start-stop UI | +2–3 days | Defer past v1 |
| Skip for v1 | Resource ranking/discovery engine, canonical cross-university graphs, multi-turn tutor memory, OCR, collaboration/social features | — | Explicitly out of scope, not "later" |

---

## 7. File-by-File Technical Breakdown

| File | Responsibility |
|---|---|
| `ai_schemas.py` | `ExtractedConcept`, `ConceptDependencyCandidate`, `AIResource` (`platform: str`, validated), `QuizQuestion`, `BookReference` |
| `app/core/platform_registry.py` (new) | Plain dict of verified platforms → URL templates + subject tags; `get_preferred_platforms(subject_domain)` |
| `ai_service.py` | `extract_concepts(syllabus_text)`, `propose_dependency_edges(concepts)`, `generate_quiz(concept)` — each a focused, single-purpose LLM call |
| `app/services/scheduler.py` (new) | SM-2 implementation, mastery-update blending logic |
| `plans_v2.py` | `resolve_resource_url()` (two-tier, URL-encoded, never raises), cycle-check on DAG insert, `syllabus_text` propagation, upsert on `(syllabus_id, concept_name)` |
| `client.ts` | Header merge that excludes forced `Content-Type` when `body instanceof FormData` |

---

## 8. Verification Plan

- **Resolver:** every registry entry resolves correctly; unmapped platform falls back per-type and never raises; casing/fuzzy variants resolve.
- **Header fix:** a `FormData` request must never end up with `Content-Type: application/json`.
- **Propagation:** `syllabus_text` reaches the background worker — explicit assertion at all 3 hops.
- **Idempotency:** re-upload the same syllabus twice → concept count unchanged, no duplicate rows.
- **DAG integrity:** attempting to insert an edge that creates a cycle is rejected, not stored.
- **Mastery blend:** unit-test all four correctness×confidence quadrants produce the expected directional mastery change (especially: incorrect+high-confidence produces the largest drop).
- **SM-2 correctness:** spot-check `next_review_at` against known SM-2 reference outputs for a few manually-traced attempt sequences.
- **Study-time determinism:** same difficulty tags always produce the same total-hours number — no LLM variance in the final figure.
- **Manual end-to-end:** upload this exact syllabus PDF → confirm `source_hint` populates with both Tanenbaum and Forouzan chapter references on the dual-sourced topics, confirm the dependency graph renders sensibly in React Flow, complete a few quizzes and confirm mastery/retention move in the expected direction, confirm a missed-with-high-confidence question pulls `next_review_at` forward rather than pushing it back.

---

## 9. The pitch, condensed

If asked "why not just use ChatGPT," the honest answer this whole plan is built to support:

> *ChatGPT can explain CRC. It can't tell you that you've answered three CRC questions wrong while feeling confident each time, that your retention on it is dropping, and that it should show up in tomorrow's review instead of next week's — because it doesn't remember you between messages. Conceptra does, because it's built around a student model, not a chat window.*

---

## 10. Architecture Freeze

This document is the final architecture pass. Four independent design reviews converged on the same shape across rounds 2–4, with each successive round finding smaller and smaller issues — that convergence is itself the signal this is done, not a reason to run a fifth round.

**From here, no further redesign sessions** — only concrete implementation problems hit while building (a bug, a schema that doesn't fit a real edge case, a query that's too slow) justify reopening this document. A new idea that isn't blocking actual code goes into a dated backlog note below, not into another planning round.

**v2 backlog (explicitly not now):**
- User-editable dependency-graph edges
- Reflection-text / explicit session start-stop UI
- Confidence split into knowledge / behavioral / retention sub-scores (raw `response_time_ms` already being captured to support this later)
- Difficulty re-calibration from aggregate observed mastery data (`difficulty_source` column already in place to support this later)
- Multi-turn AI Tutor memory
- Resource ranking/discovery, canonical cross-university graphs, OCR, social/collaboration features — permanently out of scope, not deferred

The next deliverable from here is code: Phase 1 (syllabus parsing, already mostly built) and Phase 2 (dependency DAG) first, in that order.
