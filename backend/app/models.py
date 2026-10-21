"""Tables: products (also holds stock), sale_lines (one row per product per transaction), app_state."""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from .database import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    selling_price = Column(Float, nullable=False)
    unit_cost = Column(Float, nullable=False)
    supplier = Column(String)
    stock = Column(Float, nullable=False, default=0)
    reorder_level = Column(Float, nullable=False, default=0)

class SaleLine(Base):
    __tablename__ = "sale_lines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    line_id = Column(String, unique=True, nullable=False)  # used to block duplicate imports
    transaction_id = Column(String, index=True, nullable=False)
    sold_at = Column(DateTime, index=True, nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    unit_cost = Column(Float, nullable=False)

class AppState(Base):
    __tablename__ = "app_state"
    key = Column(String, primary_key=True)
    value = Column(String)
