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

"""ISO 20022 financial message modeling for OpenEAGO agent transactions.

Implements canonical structures for:
  - pacs.008.001.10: Financial Institutional Customer Credit Transfer
  - pacs.002.001.12: Financial Institutional Payment Status Report
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import uuid
import xml.sax.saxutils as saxutils
from typing import Optional, Dict, Any


class ClearingStatus(str, Enum):
    ACCP = "ACCP"  # Accepted Customer Profile / Settled
    RJCT = "RJCT"  # Rejected by Policy or Compliance
    PDNG = "PDNG"  # Pending Consensus / DAG Ordering


@dataclass
class Pacs008Message:
    """Represents an ISO 20022 pacs.008.001.10 customer credit transfer."""
    message_id: str
    debtor_agent: str
    debtor_account: str
    creditor_agent: str
    creditor_account: str
    amount: float
    currency: str = "USD"
    settlement_method: str = "CLRG"
    clearing_system: str = "SYNAPTIC-L1"
    purpose_code: str = "GDDS"
    end_to_end_id: str = field(default_factory=lambda: f"E2E-{uuid.uuid4().hex[:12].upper()}")
    creation_date_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        debtor_agent: str,
        debtor_account: str,
        creditor_agent: str,
        creditor_account: str,
        amount: float,
        currency: str = "USD",
        purpose_code: str = "GDDS",
    ) -> "Pacs008Message":
        msg_id = f"PACS008-{uuid.uuid4().hex[:16].upper()}"
        return cls(
            message_id=msg_id,
            debtor_agent=debtor_agent,
            debtor_account=debtor_account,
            creditor_agent=creditor_agent,
            creditor_account=creditor_account,
            amount=amount,
            currency=currency,
            purpose_code=purpose_code,
        )

    def payload_hash(self) -> str:
        """Compute SHA-256 canonical hash of the message for L1 execution plan."""
        canonical = json.dumps(
            {
                "msg_id": self.message_id,
                "dbtr": self.debtor_account,
                "cdtr": self.creditor_account,
                "amt": f"{self.amount:.2f}",
                "ccy": self.currency,
                "e2e": self.end_to_end_id,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_xml(self) -> str:
        """Serialize into ISO 20022 XML representation with secure XML entity escaping."""
        esc_msg_id = saxutils.escape(self.message_id)
        esc_cre_dt = saxutils.escape(self.creation_date_time)
        esc_e2e = saxutils.escape(self.end_to_end_id)
        esc_dbtr = saxutils.escape(self.debtor_agent)
        esc_dbtr_acct = saxutils.escape(self.debtor_account)
        esc_cdtr = saxutils.escape(self.creditor_agent)
        esc_cdtr_acct = saxutils.escape(self.creditor_account)
        esc_purp = saxutils.escape(self.purpose_code)
        esc_ccy = saxutils.escape(self.currency)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.10">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>{esc_msg_id}</MsgId>
      <CreDtTm>{esc_cre_dt}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf>
        <SttlmMtd>{self.settlement_method}</SttlmMtd>
        <ClrSys><Prtry>{self.clearing_system}</Prtry></ClrSys>
      </SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <EndToEndId>{esc_e2e}</EndToEndId>
      </PmtId>
      <IntrBkSttlmAmt Ccy="{esc_ccy}">{self.amount:.2f}</IntrBkSttlmAmt>
      <Dbtr><Nm>{esc_dbtr}</Nm></Dbtr>
      <DbtrAcct><Id><Othr><Id>{esc_dbtr_acct}</Id></Othr></Id></DbtrAcct>
      <Cdtr><Nm>{esc_cdtr}</Nm></Cdtr>
      <CdtrAcct><Id><Othr><Id>{esc_cdtr_acct}</Id></Othr></Id></CdtrAcct>
      <Purp><Cd>{esc_purp}</Cd></Purp>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""


@dataclass
class Pacs002Receipt:
    """Represents an ISO 20022 pacs.002.001.12 Payment Status Report (Audit Anchor)."""
    receipt_id: str
    original_message_id: str
    original_end_to_end_id: str
    status: ClearingStatus
    reason_code: str
    reason_details: str
    l1_tx_hash: str
    l1_lane_index: int
    l1_checkpoint_height: int
    l1_state_root: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "original_message_id": self.original_message_id,
            "original_end_to_end_id": self.original_end_to_end_id,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "reason_details": self.reason_details,
            "l1_telemetry": {
                "tx_hash": self.l1_tx_hash,
                "lane_index": self.l1_lane_index,
                "checkpoint_height": self.l1_checkpoint_height,
                "state_root": self.l1_state_root,
            },
            "timestamp": self.timestamp,
        }

    def to_xml(self) -> str:
        """Serialize into ISO 20022 XML representation for regulatory auditing."""
        esc_rcpt_id = saxutils.escape(self.receipt_id)
        esc_ts = saxutils.escape(self.timestamp)
        esc_orig_msg = saxutils.escape(self.original_message_id)
        esc_orig_e2e = saxutils.escape(self.original_end_to_end_id)
        esc_rsn_cd = saxutils.escape(self.reason_code)
        esc_rsn_dtl = saxutils.escape(self.reason_details)
        esc_tx_hash = saxutils.escape(self.l1_tx_hash)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.12">
  <FIToFIPmtStsRpt>
    <GrpHdr>
      <MsgId>{esc_rcpt_id}</MsgId>
      <CreDtTm>{esc_ts}</CreDtTm>
    </GrpHdr>
    <OrgnlGrpInfAndSts>
      <OrgnlMsgId>{esc_orig_msg}</OrgnlMsgId>
      <OrgnlMsgNmId>pacs.008.001.10</OrgnlMsgNmId>
      <GrpSts>{self.status.value}</GrpSts>
    </OrgnlGrpInfAndSts>
    <TxInfAndSts>
      <OrgnlEndToEndId>{esc_orig_e2e}</OrgnlEndToEndId>
      <TxSts>{self.status.value}</TxSts>
      <StsRsnInf>
        <Rsn><Cd>{esc_rsn_cd}</Cd></Rsn>
        <AddtlInf>{esc_rsn_dtl}</AddtlInf>
      </StsRsnInf>
      <ClrSysRef>{esc_tx_hash}</ClrSysRef>
    </TxInfAndSts>
  </FIToFIPmtStsRpt>
</Document>"""
