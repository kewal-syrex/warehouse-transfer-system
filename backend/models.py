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
    expected_arrival = Column(Date)  # Made nullable for flexible date handling
    actual_arrival = Column(Date)
    order_type = Column(Enum(OrderType), default=OrderType.SUPPLIER)
    status = Column(Enum(OrderStatus), default=OrderStatus.ORDERED)
    lead_time_days = Column(Integer, default=120)  # Default 4 months
    is_estimated = Column(Boolean, default=True)   # Whether arrival date is estimated
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sku = relationship("SKU", back_populates="pending_inventory")

    @property
    def calculated_arrival_date(self):
        """Calculate arrival date based on expected_arrival or order_date + lead_time"""
        from datetime import timedelta
        if self.expected_arrival:
            return self.expected_arrival
        return self.order_date + timedelta(days=self.lead_time_days)

    @property
    def days_until_arrival(self):
        """Calculate days until arrival from today"""
        from datetime import date
        arrival_date = self.calculated_arrival_date
        return (arrival_date - date.today()).days

    @property
    def is_overdue(self):
        """Check if order is overdue"""
        from datetime import date
        if self.status in ['received', 'cancelled']:
            return False
        return self.calculated_arrival_date < date.today()

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
from pydantic import BaseModel, Field, validator
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

class SKUUpdateRequest(BaseModel):
    """
    Request model for updating SKU master data
    All fields are optional - only provided fields will be updated
    """
    description: Optional[str] = None
    supplier: Optional[str] = None
    cost_per_unit: Optional[float] = None
    status: Optional[str] = None
    transfer_multiple: Optional[int] = None
    abc_code: Optional[str] = None
    xyz_code: Optional[str] = None
    category: Optional[str] = None

    @validator('description')
    def validate_description(cls, v):
        if v is not None and (len(v.strip()) == 0 or len(v) > 255):
            raise ValueError('Description must be 1-255 characters long')
        return v.strip() if v else v

    @validator('supplier')
    def validate_supplier(cls, v):
        if v is not None and len(v) > 100:
            raise ValueError('Supplier name must be 100 characters or less')
        return v.strip() if v else v

    @validator('cost_per_unit')
    def validate_cost_per_unit(cls, v):
        if v is not None and (v <= 0 or v > 99999.99):
            raise ValueError('Cost per unit must be between 0.01 and 99999.99')
        return round(v, 2) if v is not None else v

    @validator('status')
    def validate_status(cls, v):
        if v is not None and v not in ['Active', 'Death Row', 'Discontinued']:
            raise ValueError('Status must be Active, Death Row, or Discontinued')
        return v

    @validator('transfer_multiple')
    def validate_transfer_multiple(cls, v):
        if v is not None and (v <= 0 or v > 9999):
            raise ValueError('Transfer multiple must be between 1 and 9999')
        return v

    @validator('abc_code')
    def validate_abc_code(cls, v):
        if v is not None and v.upper() not in ['A', 'B', 'C']:
            raise ValueError('ABC code must be A, B, or C')
        return v.upper() if v else v

    @validator('xyz_code')
    def validate_xyz_code(cls, v):
        if v is not None and v.upper() not in ['X', 'Y', 'Z']:
            raise ValueError('XYZ code must be X, Y, or Z')
        return v.upper() if v else v

    @validator('category')
    def validate_category(cls, v):
        if v is not None and len(v) > 50:
            raise ValueError('Category must be 50 characters or less')
        return v.strip() if v else v

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

# Pending Inventory Pydantic Models
class PendingInventoryBase(BaseModel):
    """
    Base model for pending inventory operations
    """
    sku_id: str = Field(..., description="SKU identifier")
    quantity: int = Field(..., gt=0, description="Quantity to be received")
    destination: str = Field(..., description="Destination warehouse (burnaby/kentucky)")
    order_date: date = Field(..., description="Date the order was placed")
    expected_arrival: Optional[date] = Field(None, description="Expected arrival date (optional)")
    order_type: str = Field(default="supplier", description="Order type (supplier/transfer)")
    status: str = Field(default="ordered", description="Order status")
    lead_time_days: int = Field(default=120, ge=1, le=365, description="Lead time in days")
    is_estimated: bool = Field(default=True, description="Whether arrival date is estimated")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")

    @validator('destination')
    def validate_destination(cls, v):
        if v.lower() not in ['burnaby', 'kentucky']:
            raise ValueError('Destination must be burnaby or kentucky')
        return v.lower()

    @validator('order_type')
    def validate_order_type(cls, v):
        if v.lower() not in ['supplier', 'transfer']:
            raise ValueError('Order type must be supplier or transfer')
        return v.lower()

    @validator('status')
    def validate_status(cls, v):
        if v.lower() not in ['ordered', 'shipped', 'received', 'cancelled']:
            raise ValueError('Status must be ordered, shipped, received, or cancelled')
        return v.lower()

class PendingInventoryCreate(PendingInventoryBase):
    """
    Model for creating new pending inventory records
    """
    pass

class PendingInventoryUpdate(BaseModel):
    """
    Model for updating pending inventory records
    All fields are optional - only provided fields will be updated
    """
    quantity: Optional[int] = Field(None, gt=0, description="Quantity to be received")
    destination: Optional[str] = Field(None, description="Destination warehouse")
    order_date: Optional[date] = Field(None, description="Date the order was placed")
    expected_arrival: Optional[date] = Field(None, description="Expected arrival date")
    order_type: Optional[str] = Field(None, description="Order type (supplier/transfer)")
    status: Optional[str] = Field(None, description="Order status")
    lead_time_days: Optional[int] = Field(None, ge=1, le=365, description="Lead time in days")
    is_estimated: Optional[bool] = Field(None, description="Whether arrival date is estimated")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")

class PendingInventoryResponse(PendingInventoryBase):
    """
    Model for pending inventory responses
    """
    id: int = Field(..., description="Unique identifier")
    actual_arrival: Optional[date] = Field(None, description="Actual arrival date")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Computed fields
    calculated_arrival_date: date = Field(..., description="Calculated arrival date")
    days_until_arrival: int = Field(..., description="Days until arrival")
    is_overdue: bool = Field(..., description="Whether order is overdue")

    class Config:
        from_attributes = True

class PendingInventorySummary(BaseModel):
    """
    Summary model for pending inventory by SKU
    """
    sku_id: str = Field(..., description="SKU identifier")
    description: str = Field(..., description="SKU description")
    burnaby_pending: int = Field(default=0, description="Pending quantity for Burnaby")
    kentucky_pending: int = Field(default=0, description="Pending quantity for Kentucky")
    total_pending: int = Field(default=0, description="Total pending quantity")
    supplier_orders: int = Field(default=0, description="Number of supplier orders")
    transfer_orders: int = Field(default=0, description="Number of transfer orders")
    earliest_arrival: Optional[date] = Field(None, description="Earliest expected arrival")

class BulkPendingInventoryCreate(BaseModel):
    """
    Model for bulk creating pending inventory records
    """
    orders: List[PendingInventoryCreate] = Field(..., description="List of pending orders to create")
    validate_skus: bool = Field(default=True, description="Whether to validate SKU existence")