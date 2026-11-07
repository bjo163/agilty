from __future__ import annotations

import unittest

from g4f.api.limits import PrincipalLimiter


class PrincipalLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_rate_bucket_refills_and_is_per_principal(self):
        limiter = PrincipalLimiter(requests_per_minute=1, max_in_flight=2)
        self.assertEqual(await limiter.acquire("principal-a", now=100.0), (True, 0.0))
        allowed, retry = await limiter.acquire("principal-a", now=100.0)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 60.0)
        self.assertEqual(await limiter.acquire("principal-b", now=100.0), (True, 0.0))
        await limiter.release("principal-a")
        self.assertEqual(await limiter.acquire("principal-a", now=160.0), (True, 0.0))

    async def test_concurrency_permit_is_held_until_release(self):
        limiter = PrincipalLimiter(requests_per_minute=20, max_in_flight=1)
        self.assertEqual(await limiter.acquire("principal", now=10.0), (True, 0.0))
        allowed, retry = await limiter.acquire("principal", now=10.0)
        self.assertFalse(allowed)
        self.assertEqual(retry, 1.0)
        await limiter.release("principal")
        self.assertEqual(await limiter.acquire("principal", now=10.0), (True, 0.0))

    async def test_release_is_safe_and_does_not_underflow(self):
        limiter = PrincipalLimiter()
        await limiter.release("missing")
        await limiter.acquire("principal", now=1.0)
        await limiter.release("principal")
        await limiter.release("principal")
        state = await limiter.snapshot("principal")
        self.assertEqual(state["in_flight"], 0)

    async def test_principal_cardinality_is_bounded(self):
        limiter = PrincipalLimiter(requests_per_minute=10, max_in_flight=1, max_principals=100)
        for index in range(105):
            await limiter.acquire(f"principal-{index}", now=float(index))
            await limiter.release(f"principal-{index}")
        self.assertLessEqual(len(limiter._states), 100)

    async def test_invalid_limits_are_rejected(self):
        for kwargs in (
            {"requests_per_minute": True},
            {"requests_per_minute": 0},
            {"max_in_flight": 0},
            {"max_principals": 10},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PrincipalLimiter(**kwargs)


if __name__ == "__main__":
    unittest.main()
