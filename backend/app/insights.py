"""Rule-based 'Smart Insights'. Each statement is only produced when the numbers support it. Not AI."""
from .calculations import pct_change

def build_insights(kpis, prev_kpis, categories, products, inventory, period_label):
    if kpis["transactions"] == 0:
        return [{"title": "Not enough data", "detail": f"No sales found for {period_label}.",
                 "why": "Insights need sales records.", "action": "Choose a wider date range or import data.", "level": "info"}]
    out = []
    top = max(products, key=lambda p: p["revenue"])
    out.append({"title": f"{top['product_name']} earned the most revenue",
                "detail": f"₹{top['revenue']:,.2f} in {period_label}.", "why": "Your biggest earner drives cash flow.",
                "action": "Keep it well stocked.", "level": "info"})
    if categories:
        c = categories[0]
        out.append({"title": f"{c['category']} is the largest category",
                    "detail": f"{c['revenue_share_pct']}% of revenue in {period_label}.",
                    "why": "Shows where sales are concentrated.", "action": "Review pricing and supply for this category.", "level": "info"})
    ch = pct_change(kpis["revenue"], prev_kpis["revenue"])
    if ch is not None and ch != 0:
        out.append({"title": f"Revenue {'increased' if ch > 0 else 'declined'} by {abs(ch)}%",
                    "detail": f"Compared with the previous equal-length period (₹{prev_kpis['revenue']:,.2f}).",
                    "why": "Tracks the direction of sales.", "action": "Check which products changed most." if ch < 0 else "Note what worked.",
                    "level": "warning" if ch < 0 else "good"})
    m, pm = kpis["gross_margin_pct"], prev_kpis["gross_margin_pct"]
    if m is not None and pm is not None and abs(m - pm) >= 0.1:
        out.append({"title": f"Gross margin {'rose' if m > pm else 'fell'} to {m}%",
                    "detail": f"Previous period: {pm}%. This is gross margin, before operating costs.",
                    "why": "Margin shows how much of each sale is left after product cost.", "action": "Review costs and prices.",
                    "level": "good" if m > pm else "warning"})
    flagged = [i for i in inventory if i["status"] != "healthy"]
    if flagged:
        out.append({"title": f"{len(flagged)} product(s) at or below reorder level",
                    "detail": ", ".join(i["name"] for i in flagged[:5]), "why": "Stock-outs lose sales.",
                    "action": "Review current stock and supplier availability before ordering.", "level": "warning"})
    flagged_ids = {i["id"] for i in flagged}
    for p in sorted(products, key=lambda x: -x["units_sold"])[:5]:
        if p["product_id"] in flagged_ids:
            out.append({"title": f"{p['product_name']} sells fast and stock is low",
                        "detail": f"{p['units_sold']:.0f} units sold in {period_label}.", "why": "Popular items running low risk stock-outs.",
                        "action": "Prioritise restocking.", "level": "warning"})
    return out
