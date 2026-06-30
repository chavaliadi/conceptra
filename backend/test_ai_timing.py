import asyncio
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.ai_service import extract_concepts, build_graph, generate_content

async def run_test():
    topic = "Introduction to Python"
    print(f"--- Starting full AI pipeline timing test for topic: '{topic}' ---\n")
    
    total_start = time.time()

    print("Stage 1: Extracting concepts...")
    t1 = time.time()
    response = await extract_concepts(topic, num_concepts=8)
    concepts = response.concepts
    t2 = time.time()
    print(f"  ✅ Done in {t2 - t1:.2f}s. ({len(concepts)} concepts extracted)")

    print("\nStage 2: Building dependency graph...")
    t3 = time.time()
    edges = await build_graph(concepts)
    t4 = time.time()
    print(f"  ✅ Done in {t4 - t3:.2f}s. ({len(edges)} edges generated)")

    print("\nStage 4: Generating content (concurrent)...")
    t5 = time.time()
    content = await generate_content(concepts)
    t6 = time.time()
    print(f"  ✅ Done in {t6 - t5:.2f}s. ({len(content)} concepts with content)")

    total = t6 - total_start
    print(f"\n--- ✅ Total pipeline time: {total:.2f}s ---")
    print(f"\nBreakdown:")
    print(f"  Stage 1 (Extraction):  {t2 - t1:.2f}s")
    print(f"  Stage 2 (Graph):       {t4 - t3:.2f}s")
    print(f"  Stage 4 (Content):     {t6 - t5:.2f}s")

if __name__ == "__main__":
    asyncio.run(run_test())
