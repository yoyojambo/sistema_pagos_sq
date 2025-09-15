#!/usr/bin/env python3
"""
Simple, explainable rules engine for Card-Not-Present (CNP) authorization decisions.

Inputs: CSV with columns:
- transaction_id (int/str)
- amount_mxn (float)
- customer_txn_30d (int)   -> purchase frequency in last 30 days
- geo_state (str)
- device_type (str)        -> "mobile" / "desktop"
- chargeback_count (int)   -> historical chargebacks for this customer/merchant pair or customer
- hour (int)               -> 0..23
- product_type (str)       -> "digital" / "physical" / "subscription"
- latency_ms (int)         -> time to authenticate/collect info; very high can be bot/test signals
- user_reputation (str)    -> "trusted" / "recurrent" / "new" / "high_risk"
- device_fingerprint_risk (str) -> "low" / "medium" / "high"
- ip_risk (str)            -> "low" / "medium" / "high"
- email_risk (str)         -> "low" / "medium" / "high" / "new_domain"
- bin_country (str)        -> card country
- ip_country (str)         -> country resolved from IP

Output:
- decision: "ACCEPTED", "IN_REVIEW", "REJECTED"
- risk_score: integer
- reasons: semicolon-separated triggers

Run:
    python decision_engine.py --input /path/to/transactions.csv --output /path/to/decisions.csv

Notes:
- Thresholds are intentionally conservative for demo; adjust to your business.
- This engine is deterministic and explainable. You can A/B test rule toggles.
"""

import argparse
import pandas as pd
from typing import Dict, Any, List

DECISION_ACCEPTED = "ACCEPTED"
DECISION_IN_REVIEW = "IN_REVIEW"   # e.g., 3DS challenge or manual review
DECISION_REJECTED = "REJECTED"

DEFAULT_CONFIG = {
    "amount_thresholds": {
        "digital": 2500,
        "physical": 6000,
        "subscription": 1500,
        "_default": 4000
    },
    "latency_ms_extreme": 2500,
    "chargeback_hard_block": 2,
    "score_weights": {
        "ip_risk": {"low": 0, "medium": 2, "high": 4},
        "email_risk": {"low": 0, "medium": 1, "high": 3, "new_domain": 2},
        "device_fingerprint_risk": {"low": 0, "medium": 2, "high": 4},
        "user_reputation": {"trusted": -2, "recurrent": -1, "new": 0, "high_risk": 4},
        "night_hour": 1,
        "geo_mismatch": 2,
        "high_amount": 2,
        "latency_extreme": 2,
        "new_user_high_amount": 2,
    },
    "score_to_decision": {
        "reject_at": 8,
        "review_at": 4
    }
}

def is_night(hour: int) -> bool:
    return hour >= 22 or hour <= 5

def high_amount(amount: float, product_type: str, thresholds: Dict[str, Any]) -> bool:
    t = thresholds.get(product_type, thresholds.get("_default"))
    return amount >= t

def assess_row(row: pd.Series, cfg: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    reasons: List[str] = []

    # 1) Hard blocks
    if int(row.get("chargeback_count", 0)) >= cfg["chargeback_hard_block"] and str(row.get("ip_risk", "low")).lower() == "high":
        reasons.append("hard_block:chargebacks>=2+ip_high")
        return {"decision": DECISION_REJECTED, "risk_score": 100, "reasons": ";".join(reasons)}  # short-circuit

    # 2) Base scoring from categorical risks
    for field, mapping in [("ip_risk", cfg["score_weights"]["ip_risk"]),
                           ("email_risk", cfg["score_weights"]["email_risk"]),
                           ("device_fingerprint_risk", cfg["score_weights"]["device_fingerprint_risk"])]:
        val = str(row.get(field, "low")).lower()
        add = mapping.get(val, 0)
        score += add
        if add:
            reasons.append(f"{field}:{val}(+{add})")

    # 3) Reputation
    rep = str(row.get("user_reputation", "new")).lower()
    rep_add = cfg["score_weights"]["user_reputation"].get(rep, 0)
    score += rep_add
    if rep_add:
        reasons.append(f"user_reputation:{rep}({('+' if rep_add>=0 else '')}{rep_add})")

    # 4) Night hour
    hr = int(row.get("hour", 12))
    if is_night(hr):
        add = cfg["score_weights"]["night_hour"]
        score += add
        reasons.append(f"night_hour:{hr}(+{add})")

    # 5) Geo/IP-BIN mismatch
    bin_c = str(row.get("bin_country", "")).upper()
    ip_c  = str(row.get("ip_country", "")).upper()
    if bin_c and ip_c and bin_c != ip_c:
        add = cfg["score_weights"]["geo_mismatch"]
        score += add
        reasons.append(f"geo_mismatch:{bin_c}!={ip_c}(+{add})")

    # 6) High amount for product type
    amount = float(row.get("amount_mxn", 0.0))
    ptype = str(row.get("product_type", "_default")).lower()
    if high_amount(amount, ptype, cfg["amount_thresholds"]):
        add = cfg["score_weights"]["high_amount"]
        score += add
        reasons.append(f"high_amount:{ptype}:{amount}(+{add})")
        # new user + high amount
        if rep == "new":
            add2 = cfg["score_weights"]["new_user_high_amount"]
            score += add2
            reasons.append(f"new_user_high_amount(+{add2})")

    # 7) Extreme latency
    lat = int(row.get("latency_ms", 0))
    if lat >= cfg["latency_ms_extreme"]:
        add = cfg["score_weights"]["latency_extreme"]
        score += add
        reasons.append(f"latency_extreme:{lat}ms(+{add})")

    # 8) Bonus: frequent legit customers slightly reduce score
    freq = int(row.get("customer_txn_30d", 0))
    if rep in ("recurrent", "trusted") and freq >= 3 and score > 0:
        score -= 1
        reasons.append("frequency_buffer(-1)")

    # 9) Map score to decision
    if score >= cfg["score_to_decision"]["reject_at"]:
        decision = DECISION_REJECTED
    elif score >= cfg["score_to_decision"]["review_at"]:
        decision = DECISION_IN_REVIEW
    else:
        decision = DECISION_ACCEPTED

    return {"decision": decision, "risk_score": int(score), "reasons": ";".join(reasons)}

def run(input_csv: str, output_csv: str, config: Dict[str, Any] = None) -> pd.DataFrame:
    cfg = config or DEFAULT_CONFIG
    df = pd.read_csv(input_csv)
    results = []
    for _, row in df.iterrows():
        res = assess_row(row, cfg)
        results.append(res)
    out = df.copy()
    out["decision"] = [r["decision"] for r in results]
    out["risk_score"] = [r["risk_score"] for r in results]
    out["reasons"] = [r["reasons"] for r in results]
    out.to_csv(output_csv, index=False)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=False, default="transactions_examples.csv", help="Path to input CSV")
    ap.add_argument("--output", required=False, default="decisions.csv", help="Path to output CSV")
    args = ap.parse_args()
    out = run(args.input, args.output)
    print(out.head().to_string(index=False))

if __name__ == "__main__":
    main()
