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
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sdk.iso20022_messages import Pacs008Message, ClearingStatus
from sdk.synaptic_client import SynapticL1Client


class TestISO20022Settlement(unittest.TestCase):
    def setUp(self):
        self.client = SynapticL1Client()
        self.msg = Pacs008Message.create(
            debtor_agent="spiffe://finos.org/citi/treasury-01",
            debtor_account="syn1qagent11111111111111111111111111111",
            creditor_agent="Cloud Services LLC",
            creditor_account="syn1qcloud22222222222222222222222222222",
            amount=750.0,
            currency="USD",
        )

    def test_pacs008_hashing_and_xml(self):
        msg_hash = self.msg.payload_hash()
        self.assertEqual(len(msg_hash), 64)
        xml = self.msg.to_xml()
        self.assertIn("<FIToFICstmrCdtTrf>", xml)
        self.assertIn(self.msg.message_id, xml)
        self.assertIn("750.00", xml)

        # Validate that XML parses properly with ElementTree
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, "{urn:iso:std:iso:20022:tech:xsd:pacs.008.001.10}Document")

    def test_xml_escaping_security(self):
        malicious_msg = Pacs008Message.create(
            debtor_agent="Agent <Injection> & Co",
            debtor_account="syn1qtest",
            creditor_agent="Merchant \"Malicious\" & Partners",
            creditor_account="syn1qmerchant",
            amount=100.0,
        )
        xml = malicious_msg.to_xml()
        self.assertNotIn("<Injection>", xml)
        self.assertIn("&lt;Injection&gt; &amp; Co", xml)
        self.assertIn("&amp; Partners", xml)

        # Must parse without XMLSyntaxError
        root = ET.fromstring(xml)
        self.assertIsNotNone(root)

    def test_payload_hash_sensitivity(self):
        hash1 = self.msg.payload_hash()
        # Modifying amount changes hash
        self.msg.amount = 750.01
        hash2 = self.msg.payload_hash()
        self.assertNotEqual(hash1, hash2)

    def test_successful_settlement(self):
        res = self.client.submit_settlement(self.msg, policy_approved=True, policy_reason="Approved")
        self.assertEqual(res.receipt.status, ClearingStatus.ACCP)
        self.assertEqual(res.receipt.reason_code, "ACTC")
        self.assertTrue(res.receipt.l1_tx_hash.startswith("0x"))
        self.assertGreaterEqual(res.receipt.l1_lane_index, 0)
        self.assertLess(res.receipt.l1_lane_index, 2048)

        xml = res.receipt.to_xml()
        self.assertIn("<FIToFIPmtStsRpt>", xml)
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, "{urn:iso:std:iso:20022:tech:xsd:pacs.002.001.12}Document")

    def test_rejected_settlement_audit_anchor(self):
        res = self.client.submit_settlement(self.msg, policy_approved=False, policy_reason="Cap Exceeded")
        self.assertEqual(res.receipt.status, ClearingStatus.RJCT)
        self.assertEqual(res.receipt.reason_code, "NARR")
        self.assertEqual(len(res.receipt.l1_state_root), 64)

        receipt_dict = res.receipt.to_dict()
        self.assertEqual(receipt_dict["status"], "RJCT")
        self.assertIn("l1_telemetry", receipt_dict)
        self.assertEqual(receipt_dict["l1_telemetry"]["lane_index"], res.receipt.l1_lane_index)


if __name__ == "__main__":
    unittest.main()
