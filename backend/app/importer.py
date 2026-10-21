"""CSV pipeline: Read -> Validate -> Clean -> (Store in main.py). Invalid rows are reported, never dropped silently.
Duplicate policy: a row whose line_id already exists in the database, or repeats earlier in the file, is
skipped and counted as a duplicate."""
import io
import pandas as pd

REQUIRED = ["line_id", "transaction_id", "sold_at", "product_id", "quantity", "unit_price", "unit_cost"]
TEMPLATE = ("line_id,transaction_id,sold_at,product_id,quantity,unit_price,unit_cost\n"
            "NEW-0001-1,NEW-0001,2026-10-19 10:30,P01,2,320,285\n"
            "NEW-0001-2,NEW-0001,2026-10-19 10:30,P12,3,27,25\n")

def read_csv(content: bytes):
    try:
        return pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception:
        raise ValueError("The file could not be read as CSV. Save it as a comma-separated .csv file.")

def validate(df, known_products: set, existing_line_ids: set):
    """Returns (clean_df, errors, duplicates). errors: [{row, field, message}] (row = spreadsheet row number)."""
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return pd.DataFrame(), [{"row": 0, "field": ", ".join(missing),
                                 "message": "Missing required column(s). Download the template to see the expected layout."}], 0
    errors, good, seen, dups = [], [], set(), 0
    for i, r in enumerate(df.to_dict("records"), start=2):
        def bad(field, msg): errors.append({"row": i, "field": field, "message": msg})
        if any(str(r[c]).strip() == "" for c in REQUIRED):
            bad("row", "A required value is empty."); continue
        lid = r["line_id"].strip()
        if lid in existing_line_ids or lid in seen:
            dups += 1; continue
        ts = pd.to_datetime(r["sold_at"], errors="coerce")
        if pd.isna(ts): bad("sold_at", "Not a valid date (use YYYY-MM-DD HH:MM)."); continue
        try:
            qty, price, cost = float(r["quantity"]), float(r["unit_price"]), float(r["unit_cost"])
        except ValueError:
            bad("number", "Quantity, price and cost must be numbers."); continue
        if qty <= 0: bad("quantity", "Quantity must be greater than zero."); continue
        if price < 0 or cost < 0: bad("price/cost", "Price and cost cannot be negative."); continue
        if r["product_id"].strip() not in known_products:
            bad("product_id", f"Unknown product '{r['product_id']}'. Add it to the catalogue first."); continue
        seen.add(lid)
        good.append(dict(line_id=lid, transaction_id=r["transaction_id"].strip(), sold_at=ts.to_pydatetime(),
                         product_id=r["product_id"].strip(), quantity=qty, unit_price=price, unit_cost=cost))
    return pd.DataFrame(good), errors, dups
