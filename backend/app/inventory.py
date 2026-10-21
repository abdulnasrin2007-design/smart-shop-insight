"""Inventory rules. Low: stock <= reorder level. Out: stock == 0. Healthy: stock > reorder level."""
import math

def stock_status(stock, reorder_level):
    if stock <= 0:
        return "out_of_stock"
    return "low" if stock <= reorder_level else "healthy"

def suggested_reorder(avg_daily_units, stock, cover_days=14):
    """ASSUMPTION (user-configurable cover_days): order enough to cover that many days at the
    recent average daily sales. An estimate from past sales, not guaranteed demand.
    Returns None when there is no sales history."""
    if avg_daily_units is None or avg_daily_units <= 0:
        return None
    return max(0, math.ceil(avg_daily_units * cover_days - stock))
