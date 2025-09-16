
import pandas as pd
import sys, os

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(ROOT, ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import decision_engine as de

def make_row(**kwargs):
    defaults = dict(
        transaction_id=1,
        amount_mxn=300.0,
        customer_txn_30d=0,
        geo_state="Nuevo León",
        device_type="mobile",
        chargeback_count=0,
        hour=12,
        product_type="digital",
        latency_ms=120,
        user_reputation="new",
        device_fingerprint_risk="low",
        ip_risk="low",
        email_risk="low",
        bin_country="MX",
        ip_country="MX",
    )
    defaults.update(kwargs)
    return pd.Series(defaults)

def test_accept_basic_low_risk():
    row = make_row(
        amount_mxn=250.0,
        user_reputation="trusted",
        customer_txn_30d=10,
        device_fingerprint_risk="low",
        ip_risk="low",
        email_risk="low",
        hour=10,
    )
    res = de.assess_row(row, de.DEFAULT_CONFIG)
    assert res["decision"] == "ACCEPTED"
    assert res["risk_score"] <= 3

def test_in_review_new_user_high_amount_night():
    row = make_row(
        amount_mxn=5200.0,
        product_type="digital",
        user_reputation="new",
        ip_risk="medium",
        email_risk="new_domain",
        hour=23
    )
    res = de.assess_row(row, de.DEFAULT_CONFIG)
    assert res["decision"] == "IN_REVIEW"
    assert 4 <= res["risk_score"] < 8
    assert "high_amount" in res["reasons"]

def test_reject_hard_block_chargebacks_and_ip_high():
    row = make_row(
        chargeback_count=2,
        ip_risk="high"
    )
    res = de.assess_row(row, de.DEFAULT_CONFIG)
    assert res["decision"] == "REJECTED"
    assert "hard_block" in res["reasons"] or res["risk_score"] >= 100
