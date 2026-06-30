import httpx
import time
import asyncio
from uuid import UUID

async def test_upload():
    print("--- Starting Backend API Upload & Propagation Verification ---")
    
    # Check if backend server is running on port 8000
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get("http://localhost:8000/health")
            print(f"Backend Health Check: {res.status_code}")
    except Exception as e:
        print(f"Backend health check failed: {e}. Please ensure uvicorn is running on port 8000.")
        return

    url = "http://localhost:8000/api/v2/plans/upload-syllabus"
    pdf_path = "/Users/srinivasch/Documents/Projects/Conceptra/test_syllabus.pdf"
    
    print(f"\nUploading syllabus file: {pdf_path}")
    files = {"file": ("test_syllabus.pdf", open(pdf_path, "rb"), "application/pdf")}
    data = {"exam_date": "2026-07-30T00:00:00Z", "hours_per_day": "3"}
    
    async with httpx.AsyncClient() as client:
        # Perform multipart/form-data upload
        response = await client.post(url, data=data, files=files, timeout=60.0)
        
    print(f"Upload Response Code: {response.status_code}")
    if response.status_code != 201:
        print(f"Upload failed: {response.text}")
        return
        
    plan_data = response.json()
    plan_id = plan_data.get("id")
    print(f"Plan created successfully. Plan ID: {plan_id}")
    
    # Wait for background generation
    print("\nWaiting 15 seconds for background generation to complete...")
    await asyncio.sleep(15.0)
    
    # Connect directly to DB and check results
    from app.database import AsyncSessionLocal
    from app.models.database import Plan, Concept, Edge, Progress, QuizAttempt
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    async with AsyncSessionLocal() as db:
        plan = await db.get(Plan, UUID(plan_id))
        if not plan:
            print("Plan not found in database!")
            return
            
        print(f"\nPlan status in DB: '{plan.status}'")
        print(f"Plan Inferred Subject Domain: '{plan.subject_domain}'")
        print(f"Plan Detected Textbooks: {plan.source_books}")
        
        # Load concepts
        stmt = select(Concept).where(Concept.plan_id == UUID(plan_id)).options(selectinload(Concept.content))
        res = await db.execute(stmt)
        concepts = res.scalars().all()
        
        print(f"\n--- Extracted Concepts ({len(concepts)}) ---")
        for c in concepts:
            print(f"- {c.name} (Difficulty: {c.difficulty})")
            if c.source_hint:
                print(f"  Source Hint: {c.source_hint}")
            if c.content:
                print(f"  Analogy/Tip excerpt: {c.content.explanation[:120]}...")
                print(f"  Quiz questions count: {len(c.content.quiz)}")
                print(f"  Resolved Resources: {c.content.resources}")
                
        # Load edges
        stmt_edges = select(Edge).where(Edge.plan_id == UUID(plan_id))
        res_edges = await db.execute(stmt_edges)
        edges = res_edges.scalars().all()
        print(f"\n--- Dependency DAG Edges ({len(edges)}) ---")
        for e in edges:
            print(f"  Edge: from_concept_id={e.from_concept_id} -> to_concept_id={e.to_concept_id} (confidence={e.confidence}, source={e.source})")
            
        # Load progress records
        stmt_progress = select(Progress).where(Progress.plan_id == UUID(plan_id))
        res_progress = await db.execute(stmt_progress)
        progress = res_progress.scalars().all()
        print(f"\n--- Progress Records ({len(progress)}) ---")
        for p in progress:
            print(f"  Concept progress: id={p.concept_id}, status='{p.status}', mastery_pct={p.mastery_pct}%, ease_factor={p.ease_factor}")

if __name__ == "__main__":
    asyncio.run(test_upload())
