# Copyright 2026 Synaptics-Lab
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sdk.agent_policy import AgentPolicyConfig, AgentPolicyEngine


class TestAgentPolicy(unittest.TestCase):
    def setUp(self):
        self.config = AgentPolicyConfig(
            agent_id="spiffe://finos.org/agent/unit-test",
            l1_address="syn1qtestagent0000000000000000000000000000",
            daily_limit_usd=5000.0,
            max_single_tx_usd=1000.0,
            merchant_allowlist={"syn1qmerchant001", "syn1qmerchant002"},
            compliance_profiles=["DORA", "BCBS-239"],
            capabilities=["audit_anchoring", "cross_border_clearance"],
        )
        self.engine = AgentPolicyEngine(self.config)

    def test_compliant_transaction(self):
        decision = self.engine.evaluate_transaction("syn1qmerchant001", 500.0)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.reason_code, "POLICY_PASSED")

    def test_exact_limit_boundaries(self):
        # Exactly 1000.0 should pass
        decision = self.engine.evaluate_transaction("syn1qmerchant001", 1000.0)
        self.assertTrue(decision.approved)

        # 1000.01 should fail
        decision = self.engine.evaluate_transaction("syn1qmerchant001", 1000.01)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.reason_code, "SINGLE_LIMIT_EXCEEDED")

    def test_daily_limit_exhaustion(self):
        self.engine.record_spend(4500.0)
        # 500.0 should pass (total 5000.0 == limit)
        decision = self.engine.evaluate_transaction("syn1qmerchant001", 500.0)
        self.assertTrue(decision.approved)

        # 500.01 should fail
        decision = self.engine.evaluate_transaction("syn1qmerchant001", 500.01)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.reason_code, "DAILY_LIMIT_EXCEEDED")

    def test_day_rollover_reset(self):
        # Day 1: Spend full budget
        self.engine.record_spend(5000.0, override_day="2026-09-01")
        decision_day1 = self.engine.evaluate_transaction("syn1qmerchant001", 100.0, override_day="2026-09-01")
        self.assertFalse(decision_day1.approved)

        # Day 2: Budget should reset
        decision_day2 = self.engine.evaluate_transaction("syn1qmerchant001", 500.0, override_day="2026-09-02")
        self.assertTrue(decision_day2.approved)
        self.assertEqual(self.engine.daily_spent, 0.0)

    def test_invalid_amounts(self):
        for invalid in [0.0, -10.0, float("nan"), float("inf"), float("-inf")]:
            decision = self.engine.evaluate_transaction("syn1qmerchant001", invalid)
            self.assertFalse(decision.approved)
            self.assertEqual(decision.reason_code, "INVALID_AMOUNT")

    def test_merchant_allowlist_management(self):
        # Initially not allowlisted
        decision = self.engine.evaluate_transaction("syn1qnewvendor", 200.0)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.reason_code, "MERCHANT_NOT_ALLOWLISTED")

        # Allow vendor
        self.engine.allow_merchant("syn1qnewvendor")
        decision = self.engine.evaluate_transaction("syn1qnewvendor", 200.0)
        self.assertTrue(decision.approved)

        # Revoke vendor
        self.engine.revoke_merchant("syn1qnewvendor")
        decision = self.engine.evaluate_transaction("syn1qnewvendor", 200.0)
        self.assertFalse(decision.approved)

    def test_policy_update_versioning(self):
        self.assertEqual(self.config.policy_version, 1)
        self.engine.update_policy(daily_limit=20000.0, max_single_tx=5000.0)
        self.assertEqual(self.config.policy_version, 2)
        self.assertEqual(self.config.daily_limit_usd, 20000.0)
        self.assertEqual(self.config.max_single_tx_usd, 5000.0)

        # Now $4,000 transaction passes
        decision = self.engine.evaluate_transaction("syn1qmerchant001", 4000.0)
        self.assertTrue(decision.approved)

    def test_deactivated_agent(self):
        self.config.active = False
        decision = self.engine.evaluate_transaction("syn1qmerchant001", 100.0)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.reason_code, "AGNT_REVOKED")


if __name__ == "__main__":
    unittest.main()
