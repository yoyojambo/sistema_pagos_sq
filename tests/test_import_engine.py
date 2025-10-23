import pandas as pd
import tempfile
import os
import decision_engine as de

# pytest entiende tmp_path y creara un directorio para testear el archivo
def test_run_creates_output_csv(tmp_path):
    input_file = tmp_path / "input.csv"
    output_file = tmp_path / "output.csv"

    df_in = pd.DataFrame([{
        "amount_mxn": 3000,
        "customer_txn_30d": 1,
        "chargeback_count": 0,
        "hour": 12,
        "product_type": "digital",
        "latency_ms": 100,
        "user_reputation": "new",
        "device_fingerprint_risk": "medium",
        "ip_risk": "low",
        "email_risk": "low",
        "bin_country": "MX",
        "ip_country": "MX",
    }])
    df_in.to_csv(input_file, index=False)

    # correr el engine
    result_df = de.run(str(input_file), str(output_file))

    # verificar que se creo el archivo
    assert output_file.exists()

    # checar columnas
    for col in ["decision", "risk_score", "reasons"]:
        assert col in result_df.columns

    # sanity check
    assert result_df.iloc[0]["decision"] in ("ACCEPTED", "IN_REVIEW", "REJECTED")
    assert isinstance(result_df.iloc[0]["risk_score"], int)
    assert isinstance(result_df.iloc[0]["reasons"], str)

def test_import_engine():
    import decision_engine as de
    assert isinstance(de.DEFAULT_CONFIG, dict)
