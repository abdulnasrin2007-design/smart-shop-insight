import io, pandas as pd, pytest
from fastapi.testclient import TestClient
from app import calculations as c, inventory as inv, importer, insights
from app.main import app

def sample():
    # 2 transactions: T1 has two lines. Revenue 2*100+1*50+3*10=280; cost 2*60+1*30+3*5=165; profit 115
    return pd.DataFrame([
        dict(line_id="a", transaction_id="T1", sold_at="2026-01-01 10:00", product_id="X", product_name="Rice", category="Grains", quantity=2, unit_price=100, unit_cost=60),
        dict(line_id="b", transaction_id="T1", sold_at="2026-01-01 10:00", product_id="Y", product_name="Dal", category="Pulses", quantity=1, unit_price=50, unit_cost=30),
        dict(line_id="c", transaction_id="T2", sold_at="2026-01-03 12:00", product_id="Z", product_name="Soap", category="Home", quantity=3, unit_price=10, unit_cost=5)
    ]).assign(sold_at=lambda d: pd.to_datetime(d.sold_at))

def test_kpis_manual_example():
    k = c.compute_kpis(sample())
    assert (k["revenue"], k["cogs"], k["gross_profit"]) == (280, 165, 115)
    assert k["gross_margin_pct"] == round(115 / 280 * 100, 2)
    assert k["transactions"] == 2 and k["avg_transaction_value"] == 140 and k["units_sold"] == 6

def test_date_and_category_filters():
    df = sample()
    assert len(c.filter_sales(df, "2026-01-01", "2026-01-01")) == 2      # end date inclusive
    assert len(c.filter_sales(df, category="Pulses")) == 1

def test_empty_and_zero_revenue():
    k = c.compute_kpis(sample().iloc[0:0])
    assert k["revenue"] == 0 and k["gross_margin_pct"] is None and k["avg_transaction_value"] is None

def test_pct_change_needs_baseline():
    assert c.pct_change(120, 100) == 20.0
    assert c.pct_change(50, 0) is None and c.pct_change(50, None) is None

def test_previous_period_same_length():
    s, e = c.previous_period("2026-01-08", "2026-01-14")
    assert (s.date().isoformat(), e.date().isoformat()) == ("2026-01-01", "2026-01-07")

def test_inventory_rules():
    assert inv.stock_status(0, 5) == "out_of_stock"
    assert inv.stock_status(5, 5) == "low" and inv.stock_status(6, 5) == "healthy"
    assert inv.suggested_reorder(2, 10, 14) == 18 and inv.suggested_reorder(0, 10) is None

def test_csv_validation_reports_bad_rows_and_duplicates():
    csv = ("line_id,transaction_id,sold_at,product_id,quantity,unit_price,unit_cost\n"
           "1,T1,2026-01-01,P01,2,10,5\n"        # ok
           "1,T1,2026-01-01,P01,2,10,5\n"        # duplicate in file
           "2,T1,not-a-date,P01,2,10,5\n"        # bad date
           "3,T1,2026-01-01,P01,-1,10,5\n"       # negative quantity
           "4,T1,2026-01-01,NOPE,1,10,5\n")      # unknown product
    clean, errors, dups = importer.validate(importer.read_csv(csv.encode()), {"P01"}, set())
    assert len(clean) == 1 and dups == 1 and len(errors) == 3
    _, errs, _ = importer.validate(pd.DataFrame({"a": ["1"]}), {"P01"}, set())
    assert "Missing required" in errs[0]["message"]

def test_insights_insufficient_data_and_conditions():
    empty = c.compute_kpis(sample().iloc[0:0])
    assert insights.build_insights(empty, empty, [], [], [], "p")[0]["title"] == "Not enough data"
    df = sample()
    out = insights.build_insights(c.compute_kpis(df), empty, c.category_summary(df), c.product_performance(df),
                                  [{"id": "X", "name": "Rice", "status": "low"}], "p")
    titles = " ".join(i["title"] for i in out)
    assert "Rice earned the most revenue" in titles and "reorder level" in titles
    assert "Revenue increased" not in titles          # no baseline => no change claim

# ---- real integration tests against a temporary SQLite database ----
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as cl:
        yield cl

def test_dashboard_consistency(client):
    d = client.get("/api/dashboard?days=30").json()
    assert d["kpis"]["revenue"] == pytest.approx(sum(x["revenue"] for x in d["daily"]), abs=1)
    assert d["kpis"]["revenue"] == pytest.approx(sum(x["revenue"] for x in d["categories"]), abs=1)
    assert d["kpis"]["gross_profit"] == pytest.approx(d["kpis"]["revenue"] - d["kpis"]["cogs"], abs=0.01)

def test_api_errors(client):
    assert client.get("/api/dashboard?start=2026-02-01&end=2026-01-01").status_code == 400
    assert client.get("/api/dashboard?start=banana&end=2026-01-01").status_code == 422
    assert client.patch("/api/inventory/P01", json={"stock": -3}).status_code == 422
    assert client.patch("/api/inventory/NOPE", json={"stock": 3}).status_code == 404
    r = client.post("/api/import/validate", files={"file": ("x.txt", b"hi")})
    assert r.status_code == 415

def test_inventory_update_persists(client):
    assert client.patch("/api/inventory/P01", json={"stock": 3, "reorder_level": 10}).json()["status"] == "low"
    row = [i for i in client.get("/api/inventory").json() if i["id"] == "P01"][0]
    assert row["stock"] == 3

def test_import_commit_and_duplicate_block(client):
    csv = b"line_id,transaction_id,sold_at,product_id,quantity,unit_price,unit_cost\nNEW-1,N1,2026-10-19 10:00,P01,2,320,285\n"
    first = client.post("/api/import/commit", files={"file": ("a.csv", csv)}).json()
    second = client.post("/api/import/commit", files={"file": ("a.csv", csv)}).json()
    assert first["accepted"] == 1 and second["accepted"] == 0 and second["duplicates"] == 1

def test_reset_demo(client):
    assert client.post("/api/demo/reset").json()["status"] == "reset"
    assert client.get("/api/demo").json()["is_demo_data"] is True
