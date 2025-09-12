"""
SQLAlchemy Models for Warehouse Transfer Planning Tool
"""
from sqlalchemy import Column, String, Integer, DateTime, Date, Boolean, Text, ForeignKey, Enum
from sqlalchemy.types import DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional
import enum

Base = declarative_base()

class SKUStatus(enum.Enum):
    ACTIVE = "Active"
    DEATH_ROW = "Death Row"
    DISCONTINUED = "Discontinued"

class OrderStatus(enum.Enum):
    ORDERED = "ordered"
    SHIPPED = "shipped"
    RECEIVED = "received"
    CANCELLED = "cancelled"

class OrderType(enum.Enum):
    SUPPLIER = "supplier"
    TRANSFER = "transfer"

class Warehouse(enum.Enum):
    BURNABY = "burnaby"
    KENTUCKY = "kentucky"

class SKU(Base):
    __tablename__ = 'skus'
    
    sku_id = Column(String(50), primary_key=True)
    description = Column(String(255), nullable=False)
    supplier = Column(String(100))
    status = Column(Enum(SKUStatus), default=SKUStatus.ACTIVE)
    cost_per_unit = Column(DECIMAL(10, 2))
    transfer_multiple = Column(Integer, default=50)
    abc_code = Column(String(1), default='C')
    xyz_code = Column(String(1), default='Z')
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    inventory = relationship("InventoryCurrent", back_populates="sku", uselist=False)
    sales_history = relationship("MonthlySales", back_populates="sku")
    stockout_dates = relationship("StockoutDate", back_populates="sku")
    pending_inventory = relationship("PendingInventory", back_populates="sku")
    transfer_history = relationship("TransferHistory", back_populates="sku")

class InventoryCurrent(Base):
    __tablename__ = 'inventory_current'
    
    sku_id = Column(String(50), ForeignKey('skus.sku_id', ondelete='CASCADE'), primary_key=True)
    burnaby_qty = Column(Integer, default=0)
    kentucky_qty = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sku = relationship("SKU", back_populates="inventory")
    
    @property
    def stock_status(self):
        """Determine stock status based on Kentucky quantity"""
        if self.kentucky_qty == 0:
            return "OUT_OF_STOCK"
        elif self.kentucky_qty < 100:
            return "LOW_STOCK"
        else:
            return "IN_STOCK"
    
    @property
    def total_inventory(self):
        """Total inventory across both warehouses"""
        return (self.burnaby_qty or 0) + (self.kentucky_qty or 0)

class MonthlySales(Base):
    __tablename__ = 'monthly_sales'
    
    year_month = Column(String(7), primary_key=True)  # Format: '2024-01'
    sku_id = Column(String(50), ForeignKey('skus.sku_id', ondelete='CASCADE'), primary_key=True)
    burnaby_sales = Column(Integer, default=0)
    kentucky_sales = Column(Integer, default=0)
    burnaby_stockout_days = Column(Integer, default=0)
    kentucky_stockout_days = Column(Integer, default=0)
    corrected_demand_burnaby = Column(DECIMAL(10, 2), default=0)
    corrected_demand_kentucky = Column(DECIMAL(10, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sku = relationship("SKU", back_populates="sales_history")
    
    @property
    def total_sales(self):
        """Total sales across both warehouses"""
        return (self.burnaby_sales or 0) + (self.kentucky_sales or 0)
    
    @property
    def kentucky_availability_rate(self):
        """Calculate availability rate for Kentucky warehouse"""
        if self.kentucky_stockout_days == 0:
            return 1.0
        days_in_month = 30  # Simplified - could use calendar.monthrange for exact days
        return max(0, (days_in_month - self.kentucky_stockout_days) / days_in_month)
    
    def calculate_corrected_demand(self, warehouse: str = 'kentucky') -> float:
        """Calculate stockout-corrected demand for specified warehouse"""
        if warehouse == 'kentucky':
            sales = self.kentucky_sales or 0
            stockout_days = self.kentucky_stockout_days or 0
        else:
            sales = self.burnaby_sales or 0
            stockout_days = self.burnaby_stockout_days or 0
        
        if stockout_days == 0 or sales == 0:
            return float(sales)
        
        days_in_month = 30
        availability_rate = (days_in_month - stockout_days) / days_in_month
        
        if availability_rate < 1.0:
            # Apply 30% floor to prevent overcorrection
            correction_factor = max(availability_rate, 0.3)
            corrected = sales / correction_factor
            
            # Cap at 50% increase for very low availability
            if availability_rate < 0.3:
                corrected = min(corrected, sales * 1.5)
            
            return round(corrected, 2)
        
        return float(sales)

class StockoutDate(Base):
    __tablename__ = 'stockout_dates'
    
    sku_id = Column(String(50), ForeignKey('skus.sku_id', ondelete='CASCADE'), primary_key=True)
    warehouse = Column(Enum(Warehouse), primary_key=True)
    stockout_date = Column(Date, primary_key=True)
    is_resolved = Column(Boolean, default=False)
    resolved_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sku = relationship("SKU", back_populates="stockout_dates")

class PendingInventory(Base):
    __tablename__ = 'pending_inventory'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id', ondelete='CASCADE'), nullable=False)
    quantity = Column(Integer, nullable=False)
    destination = Column(Enum(Warehouse), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_arrival = Column(Date, nullable=False)
    actual_arrival = Column(Date)
    order_type = Column(Enum(OrderType), default=OrderType.SUPPLIER)
    status = Column(Enum(OrderStatus), default=OrderStatus.ORDERED)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sku = relationship("SKU", back_populates="pending_inventory")

class TransferHistory(Base):
    __tablename__ = 'transfer_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id', ondelete='CASCADE'), nullable=False)
    recommended_qty = Column(Integer, nullable=False)
    actual_qty = Column(Integer, default=0)
    recommendation_date = Column(Date, nullable=False)
    transfer_date = Column(Date)
    burnaby_qty_before = Column(Integer)
    kentucky_qty_before = Column(Integer)
    reason = Column(String(255))
    corrected_demand = Column(DECIMAL(10, 2))
    coverage_days = Column(Integer)
    abc_class = Column(String(1))
    xyz_class = Column(String(1))
    created_by = Column(String(50), default='system')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sku = relationship("SKU", back_populates="transfer_history")

# Pydantic models for API serialization
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class SKUBase(BaseModel):
    sku_id: str
    description: str
    supplier: Optional[str] = None
    status: str = "Active"
    cost_per_unit: Optional[float] = None
    transfer_multiple: int = 50
    abc_code: str = "C"
    xyz_code: str = "Z"
    category: Optional[str] = None

class SKUResponse(SKUBase):
    burnaby_qty: int = 0
    kentucky_qty: int = 0
    stock_status: str
    last_updated: Optional[datetime] = None

class MonthlySalesResponse(BaseModel):
    year_month: str
    sku_id: str
    burnaby_sales: int = 0
    kentucky_sales: int = 0
    burnaby_stockout_days: int = 0
    kentucky_stockout_days: int = 0
    corrected_demand_kentucky: float = 0
    total_sales: int = 0

class TransferRecommendation(BaseModel):
    sku_id: str
    description: str
    current_kentucky_qty: int
    current_burnaby_qty: int
    corrected_monthly_demand: float
    recommended_transfer_qty: int
    coverage_months: float
    priority: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    reason: str
    abc_class: str
    xyz_class: str
    transfer_multiple: int
    
class DashboardMetrics(BaseModel):
    out_of_stock: int
    low_stock: int
    total_inventory_value: float
    current_month_sales: int
    stockout_affected_skus: int

class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    alerts: List[dict]
    timestamp: str