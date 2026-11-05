from __future__ import annotations

import unittest
from dataclasses import replace

from g4f.rocksoul_contracts import (
    AcceptanceCriterion,
    ContractValidationError,
    ExecutionBudget,
    RiskLevel,
    WorkItem,
    WorkStatus,
    validate_status_transition,
)


def criterion(**overrides):
    values = {
        "criterion_id": "deliverable_exists",
        "description": "The requested deliverable exists and is readable.",
        "verification_method": "artifact_test",
        "required": True,
    }
    values.update(overrides)
    return AcceptanceCriterion(**values)


def work_item(**overrides):
    values = {
        "work_id": "work-001",
        "goal": "Produce a verified deliverable.",
        "acceptance_criteria": (criterion(),),
        "created_at": "2026-11-06T00:00:00+07:00",
    }
    values.update(overrides)
    return WorkItem(**values)


class ExecutionBudgetTests(unittest.TestCase):
    def test_accepts_bounded_budget(self):
        budget = ExecutionBudget(max_wall_time_seconds=30, max_attempts=4, max_repairs=1, max_tokens=8000, max_cost_usd=0.5)
        self.assertEqual(ExecutionBudget.from_dict(budget.to_dict()), budget)

    def test_rejects_non_finite_or_unbounded_time(self):
        for value in (0, -1, float("inf"), float("nan"), 86401, True):
            with self.subTest(value=value), self.assertRaises(ContractValidationError):
                ExecutionBudget(max_wall_time_seconds=value)

    def test_rejects_invalid_integer_budgets(self):
        for kwargs in ({"max_attempts": 0}, {"max_attempts": True}, {"max_repairs": -1}, {"max_repairs": 11}, {"max_tokens": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ContractValidationError):
                ExecutionBudget(**kwargs)

    def test_rejects_unknown_budget_fields(self):
        with self.assertRaises(ContractValidationError):
            ExecutionBudget.from_dict({"max_attempts": 2, "unbounded": True})


class WorkItemTests(unittest.TestCase):
    def test_round_trip_is_canonical_and_digest_is_stable(self):
        item = work_item(permissions=("filesystem.read", "network.search"))
        restored = WorkItem.from_dict(item.to_dict())
        self.assertEqual(restored, item)
        self.assertEqual(restored.contract_digest, item.contract_digest)
        self.assertEqual(len(item.contract_digest), 64)

    def test_requires_at_least_one_required_acceptance_criterion(self):
        with self.assertRaises(ContractValidationError):
            work_item(acceptance_criteria=(criterion(required=False),))

    def test_rejects_empty_or_missing_acceptance_criteria(self):
        for criteria in ((), []):
            with self.subTest(criteria=criteria), self.assertRaises(ContractValidationError):
                work_item(acceptance_criteria=criteria)

    def test_rejects_excessive_criteria_and_permissions(self):
        with self.assertRaises(ContractValidationError):
            work_item(acceptance_criteria=tuple(
                criterion(criterion_id=f"criterion-{index}") for index in range(101)
            ))
        with self.assertRaises(ContractValidationError):
            work_item(permissions=tuple(f"capability.{index}" for index in range(101)))

    def test_rejects_duplicate_criterion_ids(self):
        with self.assertRaises(ContractValidationError):
            work_item(acceptance_criteria=(criterion(), criterion()))

    def test_rejects_unknown_fields_at_every_contract_level(self):
        payload = work_item().to_dict()
        payload["silent_success"] = True
        with self.assertRaises(ContractValidationError):
            WorkItem.from_dict(payload)
        payload = work_item().to_dict()
        payload["budget"]["unbounded"] = True
        with self.assertRaises(ContractValidationError):
            WorkItem.from_dict(payload)
        payload = work_item().to_dict()
        payload["acceptance_criteria"][0]["judge_itself"] = True
        with self.assertRaises(ContractValidationError):
            WorkItem.from_dict(payload)

    def test_high_and_critical_risk_require_human_approval(self):
        for risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            self.assertTrue(work_item(risk=risk).human_approval_required)
            with self.subTest(risk=risk), self.assertRaises(ContractValidationError):
                work_item(risk=risk, human_approval_required=False)

    def test_permissions_are_exact_and_deny_by_default(self):
        self.assertEqual(work_item().permissions, ())
        for permission in ("*", "filesystem.*", "Network.Search", "bad permission"):
            with self.subTest(permission=permission), self.assertRaises(ContractValidationError):
                work_item(permissions=(permission,))

    def test_rejects_duplicate_permissions(self):
        with self.assertRaises(ContractValidationError):
            work_item(permissions=("filesystem.read", "filesystem.read"))

    def test_timestamps_must_be_timezone_aware_and_deadline_future(self):
        with self.assertRaises(ContractValidationError):
            work_item(created_at="2026-11-06T00:00:00")
        with self.assertRaises(ContractValidationError):
            work_item(deadline_at="2026-11-05T23:59:59+07:00")

    def test_schema_version_is_explicit(self):
        with self.assertRaises(ContractValidationError):
            work_item(schema_version=2)
        with self.assertRaises(ContractValidationError):
            work_item(schema_version=1.0)
        payload = work_item().to_dict()
        del payload["schema_version"]
        with self.assertRaises(ContractValidationError):
            WorkItem.from_dict(payload)


class WorkLifecycleTests(unittest.TestCase):
    def test_happy_path_requires_verification_before_acceptance(self):
        sequence = ("planning", "ready", "running", "verifying", "accepted")
        current = WorkStatus.PENDING
        for target in sequence:
            current = validate_status_transition(current, target)
        self.assertEqual(current, WorkStatus.ACCEPTED)

    def test_execution_cannot_jump_directly_to_accepted(self):
        with self.assertRaises(ContractValidationError):
            validate_status_transition(WorkStatus.RUNNING, WorkStatus.ACCEPTED)

    def test_terminal_states_cannot_restart(self):
        for terminal in (WorkStatus.ACCEPTED, WorkStatus.REJECTED, WorkStatus.CANCELLED, WorkStatus.EXPIRED):
            with self.subTest(terminal=terminal), self.assertRaises(ContractValidationError):
                validate_status_transition(terminal, WorkStatus.RUNNING)

    def test_unverified_and_uncertain_require_reverification_for_acceptance(self):
        with self.assertRaises(ContractValidationError):
            validate_status_transition(WorkStatus.UNVERIFIED, WorkStatus.ACCEPTED)
        self.assertEqual(validate_status_transition(WorkStatus.UNVERIFIED, WorkStatus.VERIFYING), WorkStatus.VERIFYING)
        self.assertEqual(validate_status_transition(WorkStatus.UNCERTAIN, WorkStatus.VERIFYING), WorkStatus.VERIFYING)

    def test_blocked_work_can_resume_only_at_pending(self):
        self.assertEqual(validate_status_transition(WorkStatus.BLOCKED, WorkStatus.PENDING), WorkStatus.PENDING)
        with self.assertRaises(ContractValidationError):
            validate_status_transition(WorkStatus.BLOCKED, WorkStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
