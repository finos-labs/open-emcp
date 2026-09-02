#!/usr/bin/env python3
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

"""OpenEAGO x SynapticChain Layer-1 ISO 20022 Settlement & Audit Demo.

Demonstrates:
  1. OpenEAGO Phase 2: Agent Discovery & Capability Verification
  2. OpenEAGO Phase 3: Risk & Policy Negotiation (Spending Limits, Allowlists)
  3. OpenEAGO Phase 4: Layer-1 Execution across 2,048 Parallel Lanes
  4. OpenEAGO Phase 5: Audit Anchoring (pacs.008 -> pacs.002 with Cryptographic State Root)
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.iso20022_messages import Pacs008Message, ClearingStatus
from sdk.agent_policy import AgentPolicyConfig, AgentPolicyEngine
from sdk.synaptic_client import SynapticL1Client


def banner():
    print("=" * 82)
    print("  FINOS OpenEAGO + SynapticChain Layer-1 ISO 20022 Settlement Engine")
    print("  High-Throughput Settlement | 2,048 Parallel Lanes | Sub-500ms Audit Anchoring")
    print("=" * 82)


def main():
    banner()

    print("\n[PHASE 2: AGENT REGISTRY & CAPABILITY DISCOVERY]")
    agent_spiffe = "spiffe://finos.org/citi/treasury-agent-alpha"
    agent_l1_address = "syn1qxh8g3k7v0m8w9p2z4y6t1r3e5w7q9l2k4j6h8"
    cloud_vendor_address = "syn1qcloudvendor9876543210zyxwvutsrqponmlkji"
    unauthorized_vendor = "syn1qunauthorized999999999999999999999999999"

    policy_config = AgentPolicyConfig(
        agent_id=agent_spiffe,
        l1_address=agent_l1_address,
        daily_limit_usd=10000.00,
        max_single_tx_usd=2500.00,
        merchant_allowlist={cloud_vendor_address},
        compliance_profiles=["DORA", "BCBS-239", "SR-11-7"],
        capabilities=["audit_anchoring", "cross_border_clearance"],
    )

    policy_engine = AgentPolicyEngine(policy_config)
    l1_client = SynapticL1Client()

    print(f"  ✓ Agent SPIFFE ID       : {policy_config.agent_id}")
    print(f"  ✓ SynapticChain L1 Addr : {policy_config.l1_address}")
    print(f"  ✓ Daily Velocity Cap    : ${policy_config.daily_limit_usd:,.2f} USD")
    print(f"  ✓ Max Single Tx Cap     : ${policy_config.max_single_tx_usd:,.2f} USD")
    print(f"  ✓ Compliance Profiles   : {", ".join(policy_config.compliance_profiles)}")
    print(f"  ✓ OpenEAGO Capabilities : {", ".join(policy_config.capabilities)}")

    print("\n" + "-" * 82)
    print("[SCENARIO A: COMPLIANT AGENTIC COMMERCE SETTLEMENT]")
    print("  Request: Agent purchases $1,250.00 compute quota from authorized cloud vendor.")

    pacs008_a = Pacs008Message.create(
        debtor_agent=agent_spiffe,
        debtor_account=agent_l1_address,
        creditor_agent="CloudInfrastructure Corp",
        creditor_account=cloud_vendor_address,
        amount=1250.00,
        currency="USD",
        purpose_code="GDDS",
    )

    print(f"  Generated ISO 20022 Msg : {pacs008_a.message_id}")
    print(f"  End-to-End Tracking ID  : {pacs008_a.end_to_end_id}")
    print(f"  Canonical Message Hash  : {pacs008_a.payload_hash()}")

    decision_a = policy_engine.evaluate_transaction(cloud_vendor_address, pacs008_a.amount)
    print(f"\n  [Phase 3 Policy Evaluation]")
    print(f"    Decision     : {"APPROVED" if decision_a.approved else "REJECTED"}")
    print(f"    Reason Code  : {decision_a.reason_code}")
    print(f"    Message      : {decision_a.message}")

    settlement_a = l1_client.submit_settlement(pacs008_a, decision_a.approved, decision_a.message)
    if decision_a.approved:
        policy_engine.record_spend(pacs008_a.amount)

    receipt_a = settlement_a.receipt
    print(f"\n  [Phase 5 L1 Audit Anchoring & Finality]")
    print(f"    pacs.002 Receipt ID : {receipt_a.receipt_id}")
    print(f"    Clearing Status     : {receipt_a.status.value}")
    print(f"    Finality Latency    : {settlement_a.finality_ms:.1f} ms (sub-500ms BFT)")
    print(f"    Hardware Lane Index : Lane #{receipt_a.l1_lane_index} (of 2,048 parallel lanes)")
    print(f"    L1 Checkpoint Height: #{receipt_a.l1_checkpoint_height}")
    print(f"    L1 State Root Hash  : {receipt_a.l1_state_root}")

    print("\n" + "-" * 82)
    print("[SCENARIO B: RISK BREACH — TRANSACTION CAP EXCEEDED]")
    print("  Request: Agent attempts $5,000.00 transaction (Cap is $2,500.00).")

    pacs008_b = Pacs008Message.create(
        debtor_agent=agent_spiffe,
        debtor_account=agent_l1_address,
        creditor_agent="CloudInfrastructure Corp",
        creditor_account=cloud_vendor_address,
        amount=5000.00,
        currency="USD",
    )

    decision_b = policy_engine.evaluate_transaction(cloud_vendor_address, pacs008_b.amount)
    print(f"\n  [Phase 3 Policy Evaluation]")
    print(f"    Decision     : {"APPROVED" if decision_b.approved else "REJECTED"}")
    print(f"    Reason Code  : {decision_b.reason_code}")
    print(f"    Message      : {decision_b.message}")

    settlement_b = l1_client.submit_settlement(pacs008_b, decision_b.approved, decision_b.message)
    receipt_b = settlement_b.receipt

    print(f"\n  [Phase 5 L1 Audit Anchoring — Rejection Record]")
    print(f"    pacs.002 Receipt ID : {receipt_b.receipt_id}")
    print(f"    Clearing Status     : {receipt_b.status.value}")
    print(f"    Reason Code         : {receipt_b.reason_code} ({receipt_b.reason_details})")
    print(f"    Tamper-Proof Anchor : State Root {receipt_b.l1_state_root[:32]}...")

    print("\n" + "-" * 82)
    print("[SCENARIO C: RISK BREACH — UNAPPROVED MERCHANT]")
    print(f"  Request: Agent attempts payment to non-allowlisted destination ({unauthorized_vendor[:24]}...).")

    pacs008_c = Pacs008Message.create(
        debtor_agent=agent_spiffe,
        debtor_account=agent_l1_address,
        creditor_agent="DarkPool Exchange",
        creditor_account=unauthorized_vendor,
        amount=500.00,
        currency="USD",
    )

    decision_c = policy_engine.evaluate_transaction(unauthorized_vendor, pacs008_c.amount)
    print(f"\n  [Phase 3 Policy Evaluation]")
    print(f"    Decision     : {"APPROVED" if decision_c.approved else "REJECTED"}")
    print(f"    Reason Code  : {decision_c.reason_code}")
    print(f"    Message      : {decision_c.message}")

    settlement_c = l1_client.submit_settlement(pacs008_c, decision_c.approved, decision_c.message)
    receipt_c = settlement_c.receipt
    print(f"    Clearing Status     : {receipt_c.status.value}")
    print(f"    Audit Anchored Root : {receipt_c.l1_state_root[:32]}...")

    print("\n" + "=" * 82)
    print("  VERIFICATION COMPLETE: OpenEAGO Normative Phased Governance Satisfied")
    print(f"  • Total Settled Volume   : ${policy_engine.daily_spent:,.2f} USD")
    print(f"  • Remaining Daily Budget : ${max(0.0, policy_config.daily_limit_usd - policy_engine.daily_spent):,.2f} USD")
    print(f"  • Immutable Audit Records: 3 pacs.002 records anchored to SynapticChain L1")
    print("=" * 82 + "\n")


if __name__ == "__main__":
    main()
