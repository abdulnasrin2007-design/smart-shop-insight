"""FastAPI routes. Business logic lives in the other modules; routes only fetch, call, and return."""
import logging
from datetime import date, timedelta
from typing import Optional
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from .database import Base, engine, get_db, SessionLocal
from .models import Product, SaleLine, AppState
from . import calculations as calc, importer, inventory as inv, insights, seed

log = logging.getLogger("smart_shop")
app = FastAPI(title="Smart Shop Insights API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed.seed_database(db)       # only seeds when the database is empty

@app.exception_handler(Exception)
def unexpected(request: Request, exc: Exception):
    log.exception("Unhandled error")  # details stay in the server log
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server."})

# ---------- helpers ----------
def load_sales(db: Session) -> pd.DataFrame:
    q = select(SaleLine.line_id, SaleLine.transaction_id, SaleLine.sold_at, SaleLine.product_id,
               Product.name.label("product_name"), Product.category, SaleLine.quantity,
               SaleLine.unit_price, SaleLine.unit_cost).join(Product, Product.id == SaleLine.product_id)
    return pd.read_sql(q, db.connection(), parse_dates=["sold_at"])

def resolve_period(df, days, start, end):
    """Presets count back from the latest sale date in the data, so demo data always has a view."""
    if start and end:
        if start > end:
            raise HTTPException(400, "Start date must be on or before end date.")
        return pd.Timestamp(start), pd.Timestamp(end)
    last = df["sold_at"].max().normalize() if not df.empty else pd.Timestamp(date.today())
    return last - pd.Timedelta(days=days - 1), last

class Filters:
    def __init__(self, days: int = Query(30, ge=1, le=3650), start: Optional[date] = None,
                 end: Optional[date] = None, category: Optional[str] = None):
        self.days, self.start, self.end, self.category = days, start, end, category

def period_data(db, f: Filters):
    df = load_sales(db)
    s, e = resolve_period(df, f.days, f.start, f.end)
    cur = calc.filter_sales(df, s, e, f.category)
    ps, pe = calc.previous_period(s, e)
    prev = calc.filter_sales(df, ps, pe, f.category)
    return df, cur, prev, s, e

def inventory_rows(db, df, cover_days=14):
    last30 = calc.filter_sales(df, df["sold_at"].max().normalize() - pd.Timedelta(days=29)) if not df.empty else df
    daily = (last30.groupby("product_id")["quantity"].sum() / 30).to_dict() if not last30.empty else {}
    rows = []
    for p in db.query(Product).order_by(Product.name):
        rows.append({"id": p.id, "name": p.name, "category": p.category, "unit": p.unit, "stock": p.stock,
                     "reorder_level": p.reorder_level, "unit_cost": p.unit_cost, "supplier": p.supplier,
                     "status": inv.stock_status(p.stock, p.reorder_level),
                     "suggested_reorder": inv.suggested_reorder(daily.get(p.id), p.stock, cover_days)})
    return rows

# ---------- endpoints ----------
@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.query(Product).count()
    return {"status": "ok"}

@app.get("/api/meta")
def meta(db: Session = Depends(get_db)):
    df = load_sales(db)
    demo = db.get(AppState, "demo_data") is not None
    return {"store_name": "Lakshmi Provision Store (fictional)", "is_demo_data": demo,
            "min_date": df["sold_at"].min().date().isoformat() if not df.empty else None,
            "max_date": df["sold_at"].max().date().isoformat() if not df.empty else None,
            "categories": sorted(df["category"].unique().tolist()) if not df.empty else []}

@app.get("/api/dashboard")
def dashboard(f: Filters = Depends(), db: Session = Depends(get_db)):
    df, cur, prev, s, e = period_data(db, f)
    k, pk = calc.compute_kpis(cur), calc.compute_kpis(prev)
    perf = calc.product_performance(cur)
    return {"period": {"start": s.date().isoformat(), "end": e.date().isoformat()},
            "kpis": k, "previous_kpis": pk,
            "changes": {"revenue": calc.pct_change(k["revenue"], pk["revenue"]),
                        "gross_profit": calc.pct_change(k["gross_profit"], pk["gross_profit"]),
                        "units_sold": calc.pct_change(k["units_sold"], pk["units_sold"]),
                        "transactions": calc.pct_change(k["transactions"], pk["transactions"])},
            "daily": calc.time_series(cur), "categories": calc.category_summary(cur),
            "top_by_revenue": sorted(perf, key=lambda p: -p["revenue"])[:5],
            "top_by_profit": sorted(perf, key=lambda p: -p["gross_profit"])[:5],
            "attention": [i for i in inventory_rows(db, df) if i["status"] != "healthy"]}

@app.get("/api/sales/timeseries")
def timeseries(freq: str = Query("D", pattern="^[DWM]$"), f: Filters = Depends(), db: Session = Depends(get_db)):
    _, cur, _, _, _ = period_data(db, f)
    return calc.time_series(cur, freq)

@app.get("/api/products")
def products(f: Filters = Depends(), db: Session = Depends(get_db)):
    df, cur, _, _, _ = period_data(db, f)
    perf = {p["product_id"]: p for p in calc.product_performance(cur)}
    out = []
    for r in inventory_rows(db, df):
        p = perf.get(r["id"], {})
        out.append({"id": r["id"], "name": r["name"], "category": r["category"], "stock": r["stock"],
                    "unit_cost": r["unit_cost"], "selling_price": db.get(Product, r["id"]).selling_price,
                    "units_sold": p.get("units_sold", 0), "revenue": p.get("revenue", 0),
                    "gross_profit": p.get("gross_profit", 0), "margin_pct": p.get("margin_pct")})
    return out

@app.get("/api/transactions")
def transactions(f: Filters = Depends(), search: str = "", page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    _, cur, _, _, _ = period_data(db, f)
    cur = calc.add_line_values(cur)
    if search:
        cur = cur[cur["product_name"].str.contains(search, case=False) | cur["transaction_id"].str.contains(search, case=False)]
    cur = cur.sort_values("sold_at", ascending=False)
    page_df = cur.iloc[(page - 1) * page_size: page * page_size].copy()
    page_df["sold_at"] = page_df["sold_at"].dt.strftime("%Y-%m-%d %H:%M")
    return {"total": len(cur), "page": page, "page_size": page_size,
            "rows": page_df.round(2).to_dict("records")}

@app.get("/api/inventory")
def inventory_list(cover_days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    return inventory_rows(db, load_sales(db), cover_days)

class InventoryUpdate(BaseModel):
    stock: Optional[float] = Field(None, ge=0)
    reorder_level: Optional[float] = Field(None, ge=0)

@app.patch("/api/inventory/{product_id}")
def inventory_update(product_id: str, body: InventoryUpdate, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found.")
    if body.stock is None and body.reorder_level is None:
        raise HTTPException(400, "Provide stock or reorder_level.")
    if body.stock is not None: p.stock = body.stock
    if body.reorder_level is not None: p.reorder_level = body.reorder_level
    db.commit()
    return {"id": p.id, "stock": p.stock, "reorder_level": p.reorder_level, "status": inv.stock_status(p.stock, p.reorder_level)}

@app.get("/api/demo")
def demo_status(db: Session = Depends(get_db)):
    return {"is_demo_data": db.get(AppState, "demo_data") is not None, "sale_lines": db.query(SaleLine).count()}

@app.post("/api/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    seed.seed_database(db, reset=True)
    return {"status": "reset", "sale_lines": db.query(SaleLine).count()}

@app.get("/api/import/template", response_class=PlainTextResponse)
def template():
    return PlainTextResponse(importer.TEMPLATE, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=sales_template.csv"})

async def _run_validation(file: UploadFile, db: Session):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Only .csv files are supported.")
    try:
        df = importer.read_csv(await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    known = {p.id for p in db.query(Product.id)}
    existing = {r[0] for r in db.query(SaleLine.line_id)}
    return df, importer.validate(df, known, existing)

@app.post("/api/import/validate")
async def import_validate(file: UploadFile = File(...), db: Session = Depends(get_db)):
    df, (clean, errors, dups) = await _run_validation(file, db)
    return {"total_rows": len(df), "accepted": len(clean), "rejected": len(errors), "duplicates": dups,
            "errors": errors[:200], "preview": df.head(5).to_dict("records")}

@app.post("/api/import/commit")
async def import_commit(file: UploadFile = File(...), db: Session = Depends(get_db)):
    df, (clean, errors, dups) = await _run_validation(file, db)
    try:
        for r in clean.to_dict("records"):
            db.add(SaleLine(**r))
        db.commit()                  # all accepted rows are saved together or not at all
    except Exception:
        db.rollback(); log.exception("Import failed")
        raise HTTPException(500, "Import failed; nothing was saved.")
    if len(clean) > 0:
        state = db.get(AppState, "demo_data")
        if state: db.delete(state); db.commit()   # imported data means it's no longer pure demo data
    return {"total_rows": len(df), "accepted": len(clean), "rejected": len(errors), "duplicates": dups, "errors": errors[:200]}

@app.get("/api/insights")
def get_insights(f: Filters = Depends(), db: Session = Depends(get_db)):
    df, cur, prev, s, e = period_data(db, f)
    label = f"{s.date()} to {e.date()}"
    return insights.build_insights(calc.compute_kpis(cur), calc.compute_kpis(prev), calc.category_summary(cur),
                                   calc.product_performance(cur), inventory_rows(db, df), label)
