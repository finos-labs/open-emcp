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
from sdk.synaptic_client import SynapticL1Client
from sdk.iso20022_messages import Pacs008Message


class TestSynapticIntegration(unittest.TestCase):
    def test_2048_lane_distribution(self):
        client = SynapticL1Client()
        lanes = set()
        for i in range(100):
            msg = Pacs008Message.create(
                debtor_agent=f"agent-{i}",
                debtor_account=f"syn1qaccount{i:04d}",
                creditor_agent="vendor",
                creditor_account="syn1qvendor",
                amount=10.0 + i,
            )
            lane = client._calculate_lane(msg.debtor_account, msg.payload_hash())
            self.assertTrue(0 <= lane < 2048)
            lanes.add(lane)
        # 100 distinct random messages must spread across at least 70 unique lanes
        self.assertGreater(len(lanes), 70)

    def test_lane_determinism(self):
        client = SynapticL1Client()
        msg = Pacs008Message.create(
            debtor_agent="agent-fixed",
            debtor_account="syn1qfixedaddress1234567890",
            creditor_agent="vendor-fixed",
            creditor_account="syn1qvendorfixed",
            amount=500.0,
        )
        lane1 = client._calculate_lane(msg.debtor_account, msg.payload_hash())
        lane2 = client._calculate_lane(msg.debtor_account, msg.payload_hash())
        self.assertEqual(lane1, lane2)

    def test_state_root_progression(self):
        client = SynapticL1Client()
        start_height = client.current_height

        msg1 = Pacs008Message.create("agent-1", "syn1q01", "vendor", "syn1qv01", 100.0)
        res1 = client.submit_settlement(msg1, True, "Approved")
        self.assertEqual(res1.receipt.l1_checkpoint_height, start_height + 1)

        msg2 = Pacs008Message.create("agent-2", "syn1q02", "vendor", "syn1qv02", 200.0)
        res2 = client.submit_settlement(msg2, True, "Approved")
        self.assertEqual(res2.receipt.l1_checkpoint_height, start_height + 2)

        # Roots must be distinct
        self.assertNotEqual(res1.receipt.l1_state_root, res2.receipt.l1_state_root)
        self.assertEqual(client.state_root_history[start_height + 1], res1.receipt.l1_state_root)
        self.assertEqual(client.state_root_history[start_height + 2], res2.receipt.l1_state_root)


if __name__ == "__main__":
    unittest.main()
