"""Pure pandas business calculations. No database or web code here, so they are easy to test.
Expected columns: line_id, transaction_id, sold_at, product_id, product_name, category,
quantity, unit_price, unit_cost."""
import pandas as pd

def add_line_values(df):
    df = df.copy()
    df["revenue"] = df["quantity"] * df["unit_price"]
    df["cost"] = df["quantity"] * df["unit_cost"]
    df["profit"] = df["revenue"] - df["cost"]
    return df

def filter_sales(df, start=None, end=None, category=None):
    """Same filter rules used by every metric. end date is inclusive."""
    if start is not None:
        df = df[df["sold_at"] >= pd.Timestamp(start)]
    if end is not None:
        df = df[df["sold_at"] < pd.Timestamp(end) + pd.Timedelta(days=1)]
    if category:
        df = df[df["category"] == category]
    return df

def compute_kpis(df):
    df = add_line_values(df)
    revenue, cost = float(df["revenue"].sum()), float(df["cost"].sum())
    profit = revenue - cost
    tx = int(df["transaction_id"].nunique())
    return {
        "revenue": round(revenue, 2), "cogs": round(cost, 2), "gross_profit": round(profit, 2),
        "gross_margin_pct": round(profit / revenue * 100, 2) if revenue > 0 else None,
        "units_sold": float(df["quantity"].sum()), "transactions": tx,
        "avg_transaction_value": round(revenue / tx, 2) if tx > 0 else None,
    }

def pct_change(current, previous):
    """None when the baseline is missing or zero (no invalid percentages)."""
    if current is None or previous is None or previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)

def previous_period(start, end):
    """Equal-length period immediately before [start, end]."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    length = (end - start).days + 1
    prev_end = start - pd.Timedelta(days=1)
    return prev_end - pd.Timedelta(days=length - 1), prev_end

def time_series(df, freq="D"):
    """freq: D daily, W weekly, M monthly."""
    if df.empty:
        return []
    df = add_line_values(df)
    rule = {"D": "D", "W": "W-MON", "M": "MS"}[freq]
    g = df.set_index("sold_at").resample(rule)[["revenue", "profit"]].sum().reset_index()
    return [{"period": r.sold_at.strftime("%Y-%m-%d"), "revenue": round(r.revenue, 2),
             "gross_profit": round(r.profit, 2)} for r in g.itertuples()]

def category_summary(df):
    if df.empty:
        return []
    df = add_line_values(df)
    g = df.groupby("category").agg(revenue=("revenue", "sum"), gross_profit=("profit", "sum"),
                                   units=("quantity", "sum")).reset_index()
    total = g["revenue"].sum()
    g["revenue_share_pct"] = (g["revenue"] / total * 100).round(1) if total > 0 else 0
    return g.sort_values("revenue", ascending=False).round(2).to_dict("records")

def product_performance(df):
    if df.empty:
        return []
    df = add_line_values(df)
    g = df.groupby(["product_id", "product_name", "category"]).agg(
        units_sold=("quantity", "sum"), revenue=("revenue", "sum"), gross_profit=("profit", "sum")).reset_index()
    g["margin_pct"] = (g["gross_profit"] / g["revenue"] * 100).where(g["revenue"] > 0).round(2)
    return g.round(2).to_dict("records")
