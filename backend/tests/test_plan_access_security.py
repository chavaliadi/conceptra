import asyncio
import unittest
from uuid import uuid4
from fastapi import HTTPException
from app.api.routes.deps import verify_plan_access

class MockPlan:
    def __init__(self, clerk_user_id=None, is_public=False):
        self.id = uuid4()
        self.clerk_user_id = clerk_user_id
        self.is_public = is_public

class TestPlanAccessSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_owner_can_access_and_mutate(self):
        plan = MockPlan(clerk_user_id="user_owner", is_public=False)
        user = {"sub": "user_owner"}
        # Read
        await verify_plan_access(plan, user, is_mutation=False)
        # Mutation
        await verify_plan_access(plan, user, is_mutation=True)

    async def test_non_owner_blocked_from_private_plan(self):
        plan = MockPlan(clerk_user_id="user_owner", is_public=False)
        attacker = {"sub": "user_attacker"}
        with self.assertRaises(HTTPException) as ctx:
            await verify_plan_access(plan, attacker, is_mutation=False)
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_non_owner_cannot_mutate_public_plan(self):
        plan = MockPlan(clerk_user_id="user_owner", is_public=True)
        other_user = {"sub": "user_other"}
        # Read is allowed
        await verify_plan_access(plan, other_user, is_mutation=False)
        # Mutation is forbidden
        with self.assertRaises(HTTPException) as ctx:
            await verify_plan_access(plan, other_user, is_mutation=True)
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_unclaimed_plan_auto_claimed_by_first_authenticated_user(self):
        plan = MockPlan(clerk_user_id=None, is_public=False)
        user = {"sub": "user_claimant"}
        await verify_plan_access(plan, user, is_mutation=False)
        self.assertEqual(plan.clerk_user_id, "user_claimant")

    async def test_unauthenticated_cannot_mutate_unclaimed_plan(self):
        plan = MockPlan(clerk_user_id=None, is_public=False)
        with self.assertRaises(HTTPException) as ctx:
            await verify_plan_access(plan, None, is_mutation=True)
        self.assertEqual(ctx.exception.status_code, 401)

if __name__ == "__main__":
    unittest.main()
