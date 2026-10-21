"""Synthetic demo data generator (fixed seed => reproducible). Fictional store, NOT real results."""
import numpy as np, pandas as pd
from datetime import datetime, timedelta
from .models import Product, SaleLine, AppState

SEED = 42
END_DATE = datetime(2026, 10, 18)   # last day of demo data
DAYS = 90
# id, name, category, unit, price, cost, popularity, stock, reorder
PRODUCTS = [
 ("P01","Sona Masoori Rice 5kg","Rice & Grains","bag",320,285,5,40,15),
 ("P02","Basmati Rice 1kg","Rice & Grains","pack",130,105,4,35,12),
 ("P03","Poha 500g","Rice & Grains","pack",48,38,2,25,8),
 ("P04","Toor Dal 1kg","Pulses","pack",165,140,5,30,15),
 ("P05","Chana Dal 1kg","Pulses","pack",110,92,3,22,10),
 ("P06","Moong Dal 1kg","Pulses","pack",135,112,3,18,10),
 ("P07","Wheat Atta 5kg","Flour & Staples","bag",245,215,5,5,15),
 ("P08","Sugar 1kg","Flour & Staples","pack",46,40,6,60,20),
 ("P09","Salt 1kg","Flour & Staples","pack",22,17,4,50,15),
 ("P10","Sunflower Oil 1L","Cooking Oil","bottle",150,132,6,28,15),
 ("P11","Groundnut Oil 1L","Cooking Oil","bottle",210,185,3,14,8),
 ("P12","Milk 500ml","Dairy","pouch",27,25,9,12,25),
 ("P13","Curd 400g","Dairy","cup",35,30,5,0,10),
 ("P14","Paneer 200g","Dairy","pack",85,72,2,10,5),
 ("P15","Bread","Packaged Foods","loaf",40,34,6,14,10),
 ("P16","Instant Noodles","Packaged Foods","pack",14,11,7,80,30),
 ("P17","Pickle 300g","Packaged Foods","jar",95,70,2,16,6),
 ("P18","Glucose Biscuits","Snacks","pack",10,8,9,120,40),
 ("P19","Potato Chips","Snacks","pack",20,15,7,70,25),
 ("P20","Namkeen Mixture 200g","Snacks","pack",45,34,3,20,8),
 ("P21","Tea Powder 250g","Beverages","pack",120,98,5,26,10),
 ("P22","Coffee Powder 100g","Beverages","jar",160,125,2,15,6),
 ("P23","Soft Drink 750ml","Beverages","bottle",40,33,5,40,15),
 ("P24","Bath Soap","Household","bar",38,30,5,45,15),
 ("P25","Detergent Powder 1kg","Household","pack",110,88,3,9,10),
 ("P26","Dishwash Liquid 500ml","Household","bottle",99,78,2,20,6),
]
SUPPLIERS = ["Sri Lakshmi Traders","Vijaya Wholesale","Annapurna Distributors"]

def build_sales_frame() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows, tx = [], 0
    weights = np.array([p[6] for p in PRODUCTS], float)
    for d in range(DAYS):
        day = END_DATE - timedelta(days=DAYS - 1 - d)
        weekend = day.weekday() >= 5
        n_tx = int(rng.normal(34 if weekend else 26, 5) + d * 0.05)   # busier weekends, slow growth
        for _ in range(max(n_tx, 8)):
            tx += 1
            hour = int(np.clip(rng.normal(14, 4), 7, 21))
            ts = day.replace(hour=hour, minute=int(rng.integers(0, 60)))
            picks = rng.choice(len(PRODUCTS), size=int(rng.integers(1, 5)), replace=False, p=weights / weights.sum())
            for k, i in enumerate(picks, 1):
                p = PRODUCTS[i]
                rows.append(dict(line_id=f"T{tx:05d}-{k}", transaction_id=f"T{tx:05d}", sold_at=ts,
                                 product_id=p[0], quantity=int(rng.integers(1, 4)),
                                 unit_price=float(p[4]), unit_cost=float(p[5])))
    return pd.DataFrame(rows)

def seed_database(db, reset=False):
    """Create demo data. Runs only when empty unless reset=True."""
    if reset:
        db.query(SaleLine).delete(); db.query(Product).delete(); db.query(AppState).delete()
    if db.query(Product).count() > 0:
        return False
    for i, p in enumerate(PRODUCTS):
        db.add(Product(id=p[0], name=p[1], category=p[2], unit=p[3], selling_price=p[4], unit_cost=p[5],
                       stock=p[7], reorder_level=p[8], supplier=SUPPLIERS[i % 3]))
    db.flush()
    for r in build_sales_frame().to_dict("records"):
        db.add(SaleLine(**r))
    db.add(AppState(key="demo_data", value="true"))
    db.commit()
    return True
