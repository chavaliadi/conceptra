import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.database import AsyncSessionLocal
from sqlalchemy import text

async def query_db():
    print("Connecting to DB...")
    async with AsyncSessionLocal() as db:
        # Check plans
        plans = await db.execute(text("SELECT id, topic, status, created_at FROM plans ORDER BY created_at DESC LIMIT 5"))
        plan_list = plans.fetchall()
        print("\n--- Recent Plans ---")
        for row in plan_list:
            print(f"ID: {row[0]} | Topic: '{row[1]}' | Status: {row[2]} | Created: {row[3]}")
            
        if not plan_list:
            print("No plans found.")
            return

        latest_plan_id = plan_list[0][0]
        
        # Check concepts for the latest plan
        concepts = await db.execute(text(f"SELECT c.id, c.name, cc.resources, cc.explanation FROM concepts c JOIN concept_content cc ON c.id = cc.concept_id WHERE c.plan_id = '{latest_plan_id}'"))
        print(f"\n--- Concepts & Resources for latest plan ({latest_plan_id}) ---")
        for row in concepts.fetchall():
            print(f"Concept: '{row[1]}'")
            print(f"  Explanation: {row[3][:100]}...")
            print(f"  Resources: {row[2]}")

asyncio.run(query_db())
