# Product Requirements Document (PRD)
## Warehouse Transfer Planning Tool - Simplified Version

### Version 1.0
### Date: January 2025

---

## 1. Executive Summary

### 1.1 Purpose
Build a simple, powerful web-based tool to optimize inventory transfers from Burnaby (Canada) warehouse to Kentucky (US) warehouse, replacing the current Excel-based process with an intelligent system that corrects for stockouts and provides data-driven transfer recommendations.

### 1.2 Core Problems Solved
- Monthly sales data doesn't account for stockouts (understates true demand)
- Cannot see historical CA/US sales breakdown without re-pulling reports  
- Time-consuming manual calculations for 2000+ SKUs
- No systematic approach to safety stock levels
- Human errors in transfer quantity calculations

### 1.3 Solution Approach
A straightforward web application using:
- **Python/FastAPI** backend for complex calculations
- **Simple HTML/JavaScript** frontend with DataTables for powerful features
- **MySQL** database via XAMPP
- **No build process** - just save and refresh

---

## 2. Technical Architecture

### 2.1 Stack Overview
```
Frontend (Simple HTML/JS)          Backend (Python/FastAPI)         Database (MySQL)
├── index.html                     ├── main.py                      ├── warehouse_transfer DB
├── transfer-planning.html   <-->  ├── calculations.py        <-->  ├── Tables
├── js/app.js                      ├── database.py                  └── Stored procedures
└── css/custom.css                 └── models.py
```

### 2.2 Development Environment
```bash
# Directory Structure
warehouse-transfer/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── calculations.py      # Business logic
│   ├── database.py         # Database connection
│   ├── models.py           # Data models
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── index.html          # Dashboard
│   ├── transfer-planning.html
│   ├── js/
│   │   └── app.js
│   └── css/
│       └── custom.css
└── database/
    └── schema.sql          # Database setup
```

---

## 3. Database Schema

```sql
-- Create database
CREATE DATABASE IF NOT EXISTS warehouse_transfer;
USE warehouse_transfer;

-- Main SKU table
CREATE TABLE skus (
    sku_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255),
    supplier VARCHAR(100),
    status ENUM('Active', 'Death Row', 'Discontinued', 'Seasonal', 'New') DEFAULT 'Active',
    cost_per_unit DECIMAL(10,2),
    transfer_multiple INT DEFAULT 50,
    master_carton_qty INT,
    abc_code CHAR(1), -- Calculated based on value
    xyz_code CHAR(1), -- Calculated based on variability
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status_abc (status, abc_code)
);

-- Current inventory
CREATE TABLE inventory_current (
    sku_id VARCHAR(50) PRIMARY KEY,
    burnaby_qty INT DEFAULT 0,
    kentucky_qty INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id)
);

-- Sales history (daily granularity for stockout detection)
CREATE TABLE sales_daily (
    date DATE,
    sku_id VARCHAR(50),
    burnaby_sales INT DEFAULT 0,
    kentucky_sales INT DEFAULT 0,
    burnaby_was_available BOOLEAN DEFAULT TRUE,
    kentucky_was_available BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (date, sku_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    INDEX idx_date (date)
);

-- Pending inventory (orders in transit)
CREATE TABLE pending_inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50),
    quantity INT,
    destination ENUM('burnaby', 'kentucky'),
    order_date DATE,
    expected_arrival DATE,
    order_type ENUM('supplier', 'transfer'),
    status ENUM('ordered', 'in_transit', 'received') DEFAULT 'ordered',
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    INDEX idx_sku_status (sku_id, status)
);

-- Transfer history (for tracking performance)
CREATE TABLE transfer_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transfer_date DATE,
    sku_id VARCHAR(50),
    recommended_qty INT,
    actual_qty INT,
    reason_for_change TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id)
);

-- System configuration
CREATE TABLE config (
    key_name VARCHAR(50) PRIMARY KEY,
    value VARCHAR(255),
    description TEXT
);

-- Insert default configuration
INSERT INTO config (key_name, value, description) VALUES
('transfer_lead_time_days', '21', 'Total lead time for transfers (1 week transit + 2 weeks prep)'),
('stockout_correction_min', '0.3', 'Minimum availability rate for demand correction'),
('default_coverage_months', '6', 'Default coverage target in months'),
('min_transfer_qty', '10', 'Minimum quantity to transfer'),
('transfer_multiple_chargers', '25', 'Transfer multiple for chargers'),
('transfer_multiple_standard', '50', 'Standard transfer multiple'),
('transfer_multiple_bulk', '100', 'Bulk transfer multiple');

-- View for current stockout status
CREATE VIEW stockout_status AS
SELECT 
    s.sku_id,
    s.description,
    ic.kentucky_qty,
    CASE 
        WHEN ic.kentucky_qty = 0 THEN 'OUT_OF_STOCK'
        WHEN ic.kentucky_qty < AVG(sd.kentucky_sales) * 7 THEN 'CRITICAL'
        WHEN ic.kentucky_qty < AVG(sd.kentucky_sales) * 14 THEN 'LOW'
        ELSE 'OK'
    END as stock_status,
    COUNT(CASE WHEN sd.kentucky_was_available = FALSE THEN 1 END) as stockout_days_30d
FROM skus s
JOIN inventory_current ic ON s.sku_id = ic.sku_id
LEFT JOIN sales_daily sd ON s.sku_id = sd.sku_id 
    AND sd.date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
WHERE s.status = 'Active'
GROUP BY s.sku_id;
```

---

## 4. Backend Implementation (Python/FastAPI)

### 4.1 Setup and Dependencies

```python
# requirements.txt
fastapi==0.104.1
uvicorn==0.24.0
pandas==2.1.3
numpy==1.24.3
sqlalchemy==2.0.23
pymysql==1.1.0
python-multipart==0.0.6
openpyxl==3.1.2
scipy==1.11.4
python-dateutil==2.8.2
```

### 4.2 Main Application (main.py)

```python
# backend/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Optional, List
from database import engine, get_db_connection
from calculations import TransferCalculator, DemandCorrector, ABCXYZClassifier
from models import TransferRecommendation, SKU, InventorySnapshot

app = FastAPI(title="Warehouse Transfer Planning Tool")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize calculators
transfer_calc = TransferCalculator()
demand_corrector = DemandCorrector()
classifier = ABCXYZClassifier()

@app.get("/")
def read_root():
    return {"message": "Warehouse Transfer Planning API", "version": "1.0"}

@app.get("/api/dashboard-metrics")
def get_dashboard_metrics():
    """Get key metrics for dashboard"""
    with get_db_connection() as conn:
        # Critical SKUs (out of stock or <7 days coverage)
        critical_query = """
            SELECT COUNT(*) as count
            FROM stockout_status 
            WHERE stock_status IN ('OUT_OF_STOCK', 'CRITICAL')
        """
        critical_count = pd.read_sql(critical_query, conn).iloc[0]['count']
        
        # Low stock (7-14 days)
        low_query = """
            SELECT COUNT(*) as count
            FROM stockout_status 
            WHERE stock_status = 'LOW'
        """
        low_count = pd.read_sql(low_query, conn).iloc[0]['count']
        
        # Calculate total transfer value needed
        transfer_query = """
            SELECT 
                s.sku_id,
                s.cost_per_unit,
                ic.kentucky_qty,
                AVG(sd.kentucky_sales) as avg_daily_sales
            FROM skus s
            JOIN inventory_current ic ON s.sku_id = ic.sku_id
            LEFT JOIN sales_daily sd ON s.sku_id = sd.sku_id
                AND sd.date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            WHERE s.status = 'Active'
            GROUP BY s.sku_id
        """
        df = pd.read_sql(transfer_query, conn)
        
        # Calculate recommended transfers
        total_units = 0
        total_value = 0
        
        for _, row in df.iterrows():
            if pd.notna(row['avg_daily_sales']) and row['avg_daily_sales'] > 0:
                # Simple 6-month coverage calculation for dashboard
                target_qty = row['avg_daily_sales'] * 180
                transfer_qty = max(0, target_qty - row['kentucky_qty'])
                if transfer_qty > 10:  # Minimum transfer
                    total_units += transfer_qty
                    total_value += transfer_qty * row['cost_per_unit']
        
        return {
            "critical_count": int(critical_count),
            "low_stock_count": int(low_count),
            "transfer_units": int(total_units),
            "transfer_value": round(total_value, 2),
            "last_updated": datetime.now().isoformat()
        }

@app.get("/api/transfer-recommendations")
def get_transfer_recommendations(
    status: Optional[str] = "Active",
    abc_code: Optional[str] = None,
    min_coverage_days: Optional[int] = None,
    max_coverage_days: Optional[int] = None
):
    """Get transfer recommendations with stockout-corrected demand"""
    
    with get_db_connection() as conn:
        # Build query
        query = """
            SELECT 
                s.sku_id,
                s.description,
                s.status,
                s.cost_per_unit,
                s.transfer_multiple,
                COALESCE(s.abc_code, 'C') as abc_code,
                COALESCE(s.xyz_code, 'Z') as xyz_code,
                ic.burnaby_qty,
                ic.kentucky_qty,
                COALESCE(pi.pending_qty, 0) as pending_qty,
                COALESCE(sales.total_sales_30d, 0) as kentucky_sales_30d,
                COALESCE(sales.days_available_30d, 30) as days_available_30d,
                COALESCE(sales.avg_daily_sales, 0) as avg_daily_sales
            FROM skus s
            JOIN inventory_current ic ON s.sku_id = ic.sku_id
            LEFT JOIN (
                SELECT 
                    sku_id,
                    SUM(quantity) as pending_qty
                FROM pending_inventory
                WHERE destination = 'kentucky' 
                    AND status IN ('ordered', 'in_transit')
                    AND expected_arrival <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                GROUP BY sku_id
            ) pi ON s.sku_id = pi.sku_id
            LEFT JOIN (
                SELECT 
                    sku_id,
                    SUM(kentucky_sales) as total_sales_30d,
                    SUM(CASE WHEN kentucky_was_available THEN 1 ELSE 0 END) as days_available_30d,
                    AVG(kentucky_sales) as avg_daily_sales
                FROM sales_daily
                WHERE date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY sku_id
            ) sales ON s.sku_id = sales.sku_id
            WHERE 1=1
        """
        
        # Add filters
        if status:
            query += f" AND s.status = '{status}'"
        if abc_code:
            query += f" AND s.abc_code = '{abc_code}'"
            
        df = pd.read_sql(query, conn)
        
        # Calculate recommendations for each SKU
        recommendations = []
        
        for _, row in df.iterrows():
            # Correct demand for stockouts
            availability_rate = row['days_available_30d'] / 30
            if availability_rate < 1.0 and row['kentucky_sales_30d'] > 0:
                correction_factor = max(availability_rate, 0.3)  # Min 30% as per knowledge base
                corrected_monthly_demand = row['kentucky_sales_30d'] / correction_factor
            else:
                corrected_monthly_demand = row['kentucky_sales_30d']
            
            # Calculate coverage
            if corrected_monthly_demand > 0:
                current_coverage_days = (row['kentucky_qty'] / (corrected_monthly_demand / 30))
                after_pending_coverage = ((row['kentucky_qty'] + row['pending_qty']) / 
                                         (corrected_monthly_demand / 30))
            else:
                current_coverage_days = 999
                after_pending_coverage = 999
            
            # Apply coverage filters if specified
            if min_coverage_days and current_coverage_days < min_coverage_days:
                continue
            if max_coverage_days and current_coverage_days > max_coverage_days:
                continue
            
            # Calculate transfer quantity
            transfer_qty = transfer_calc.calculate_transfer_quantity(
                row.to_dict(),
                corrected_monthly_demand
            )
            
            recommendations.append({
                "sku_id": row['sku_id'],
                "description": row['description'],
                "status": row['status'],
                "abc_xyz": f"{row['abc_code']}{row['xyz_code']}",
                "burnaby_qty": int(row['burnaby_qty']),
                "kentucky_qty": int(row['kentucky_qty']),
                "pending_qty": int(row['pending_qty']),
                "kentucky_sales_30d": int(row['kentucky_sales_30d']),
                "corrected_demand": int(corrected_monthly_demand),
                "availability_rate": round(availability_rate * 100, 1),
                "current_coverage_days": round(current_coverage_days, 1),
                "after_pending_coverage": round(after_pending_coverage, 1),
                "recommended_qty": transfer_qty['recommended'],
                "transfer_qty": transfer_qty['final'],
                "transfer_value": round(transfer_qty['final'] * row['cost_per_unit'], 2),
                "stockout_adjusted": availability_rate < 1.0
            })
        
        # Sort by coverage days (most urgent first)
        recommendations.sort(key=lambda x: x['current_coverage_days'])
        
        return recommendations

@app.post("/api/update-transfer-qty")
async def update_transfer_qty(sku_id: str, new_qty: int):
    """Update transfer quantity for a SKU"""
    # In a real app, you'd save this to a draft transfer order
    # For now, just validate and return success
    if new_qty < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
    
    # Round to transfer multiple
    with get_db_connection() as conn:
        sku_query = f"SELECT transfer_multiple FROM skus WHERE sku_id = '{sku_id}'"
        result = pd.read_sql(sku_query, conn)
        if not result.empty:
            multiple = result.iloc[0]['transfer_multiple'] or 50
            rounded_qty = round(new_qty / multiple) * multiple
            return {"sku_id": sku_id, "original_qty": new_qty, "rounded_qty": rounded_qty}
    
    return {"sku_id": sku_id, "qty": new_qty}

@app.post("/api/generate-transfer-order")
async def generate_transfer_order(items: List[dict]):
    """Generate Excel file for transfer order"""
    
    # Create DataFrame from items
    df = pd.DataFrame(items)
    
    # Filter only items with transfer_qty > 0
    df = df[df['transfer_qty'] > 0].copy()
    
    if df.empty:
        raise HTTPException(status_code=400, detail="No items to transfer")
    
    # Create Excel file
    filename = f"transfer_order_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = f"exports/{filename}"
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Main transfer sheet
        transfer_df = df[['sku_id', 'description', 'transfer_qty', 'transfer_value']]
        transfer_df.to_excel(writer, sheet_name='Transfer Order', index=False)
        
        # Summary sheet
        summary_data = {
            'Metric': ['Total SKUs', 'Total Units', 'Total Value', 'Date Generated'],
            'Value': [
                len(df),
                df['transfer_qty'].sum(),
                f"${df['transfer_value'].sum():,.2f}",
                datetime.now().strftime('%Y-%m-%d %H:%M')
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    return FileResponse(filepath, filename=filename)

@app.post("/api/import-excel")
async def import_excel(file: UploadFile = File(...)):
    """Import data from Excel file"""
    
    # Read Excel file
    contents = await file.read()
    df = pd.read_excel(contents)
    
    # Validate required columns
    required_columns = ['sku_id', 'burnaby_qty', 'kentucky_qty']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing_columns}"
        )
    
    # Import to database
    with get_db_connection() as conn:
        # Update inventory_current table
        for _, row in df.iterrows():
            update_query = """
                INSERT INTO inventory_current (sku_id, burnaby_qty, kentucky_qty)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    burnaby_qty = VALUES(burnaby_qty),
                    kentucky_qty = VALUES(kentucky_qty),
                    last_updated = NOW()
            """
            conn.execute(update_query, (
                row['sku_id'],
                row['burnaby_qty'],
                row['kentucky_qty']
            ))
        conn.commit()
    
    return {"message": f"Successfully imported {len(df)} records"}

@app.get("/api/sku/{sku_id}")
def get_sku_detail(sku_id: str):
    """Get detailed information for a specific SKU"""
    
    with get_db_connection() as conn:
        # Get SKU info
        sku_query = """
            SELECT s.*, ic.burnaby_qty, ic.kentucky_qty
            FROM skus s
            JOIN inventory_current ic ON s.sku_id = ic.sku_id
            WHERE s.sku_id = %s
        """
        sku_df = pd.read_sql(sku_query, conn, params=[sku_id])
        
        if sku_df.empty:
            raise HTTPException(status_code=404, detail="SKU not found")
        
        sku_info = sku_df.iloc[0].to_dict()
        
        # Get sales history
        sales_query = """
            SELECT 
                date,
                kentucky_sales,
                kentucky_was_available
            FROM sales_daily
            WHERE sku_id = %s
                AND date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
            ORDER BY date
        """
        sales_df = pd.read_sql(sales_query, conn, params=[sku_id])
        
        # Calculate statistics
        stockout_days = len(sales_df[sales_df['kentucky_was_available'] == False])
        avg_sales = sales_df['kentucky_sales'].mean()
        std_sales = sales_df['kentucky_sales'].std()
        
        return {
            "sku_info": sku_info,
            "statistics": {
                "avg_daily_sales": round(avg_sales, 2),
                "std_deviation": round(std_sales, 2),
                "stockout_days_90d": stockout_days,
                "cv": round(std_sales / avg_sales, 2) if avg_sales > 0 else 0
            },
            "sales_history": sales_df.to_dict('records')
        }
```

### 4.3 Business Logic (calculations.py)

```python
# backend/calculations.py
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Any

class DemandCorrector:
    """Correct demand for stockout periods based on knowledge base"""
    
    def correct_demand(self, actual_sales: float, availability_rate: float) -> float:
        """
        Correct demand based on availability
        From knowledge base: use minimum 30% availability to avoid overcorrection
        """
        if availability_rate >= 1.0:
            return actual_sales
        
        # Apply correction with safety factor
        correction_factor = max(availability_rate, 0.3)
        corrected = actual_sales / correction_factor
        
        # Cap at 50% increase for very low availability
        if availability_rate < 0.3:
            corrected = min(corrected, actual_sales * 1.5)
        
        return corrected

class ABCXYZClassifier:
    """Classify SKUs based on value (ABC) and variability (XYZ)"""
    
    def classify_abc(self, skus_df: pd.DataFrame) -> pd.Series:
        """
        ABC classification based on sales value
        A: 80% of value
        B: 15% of value  
        C: 5% of value
        """
        # Calculate value for each SKU
        skus_df['value'] = skus_df['sales_qty'] * skus_df['cost_per_unit']
        
        # Sort by value and calculate cumulative percentage
        skus_df = skus_df.sort_values('value', ascending=False)
        skus_df['cumulative_value'] = skus_df['value'].cumsum()
        skus_df['cumulative_pct'] = skus_df['cumulative_value'] / skus_df['value'].sum()
        
        # Classify
        conditions = [
            skus_df['cumulative_pct'] <= 0.80,
            skus_df['cumulative_pct'] <= 0.95
        ]
        choices = ['A', 'B']
        
        return np.select(conditions, choices, default='C')
    
    def classify_xyz(self, sales_history: list) -> str:
        """
        XYZ classification based on demand variability
        X: CV < 0.25 (stable)
        Y: CV < 0.50 (variable)
        Z: CV >= 0.50 (irregular)
        """
        if len(sales_history) < 4:
            return 'Z'
        
        mean = np.mean(sales_history)
        if mean == 0:
            return 'Z'
        
        std_dev = np.std(sales_history)
        cv = std_dev / mean
        
        if cv < 0.25:
            return 'X'
        elif cv < 0.50:
            return 'Y'
        else:
            return 'Z'

class TransferCalculator:
    """Calculate optimal transfer quantities"""
    
    def __init__(self):
        # Coverage targets by ABC-XYZ (from knowledge base)
        self.coverage_months = {
            'AX': 4, 'AY': 5, 'AZ': 6,
            'BX': 3, 'BY': 4, 'BZ': 5,
            'CX': 2, 'CY': 2, 'CZ': 1
        }
        
        # Service level Z-scores
        self.z_scores = {
            'AX': 2.33,  # 99% service
            'AY': 1.96,  # 97.5% service
            'AZ': 1.65,  # 95% service
            'BX': 1.65,  # 95% service
            'BY': 1.44,  # 92.5% service
            'BZ': 1.28,  # 90% service
            'CX': 1.04,  # 85% service
            'CY': 0.84,  # 80% service
            'CZ': 0.67   # 75% service
        }
    
    def calculate_transfer_quantity(self, sku_data: Dict[str, Any], 
                                   corrected_monthly_demand: float) -> Dict[str, int]:
        """
        Calculate recommended transfer quantity
        
        Returns:
            dict with 'recommended' and 'final' quantities
        """
        # Get classification
        classification = f"{sku_data['abc_code']}{sku_data['xyz_code']}"
        
        # Get target coverage
        coverage_months = self.coverage_months.get(classification, 6)
        
        # Calculate target inventory
        target_inventory = corrected_monthly_demand * coverage_months
        
        # Current position (inventory + pending within 30 days)
        current_position = sku_data['kentucky_qty'] + sku_data['pending_qty']
        
        # Base transfer need
        transfer_need = target_inventory - current_position
        
        # Apply minimum transfer quantity
        if transfer_need < 10:
            transfer_need = 0
        
        # Round to transfer multiple
        if transfer_need > 0:
            multiple = self.get_transfer_multiple(sku_data)
            transfer_need = np.ceil(transfer_need / multiple) * multiple
        
        # Check Burnaby availability (keep minimum 1 month in Burnaby)
        burnaby_min = corrected_monthly_demand * 1  # Keep 1 month in Burnaby
        available_to_transfer = max(0, sku_data['burnaby_qty'] - burnaby_min)
        
        # Final quantity is minimum of need and available
        final_qty = min(transfer_need, available_to_transfer)
        
        return {
            'recommended': int(transfer_need),
            'final': int(final_qty)
        }
    
    def get_transfer_multiple(self, sku_data: Dict[str, Any]) -> int:
        """Get appropriate transfer multiple based on SKU type"""
        
        description = sku_data.get('description', '').lower()
        
        # Special rules
        if 'charger' in description or 'cable' in description:
            return 25
        elif sku_data['abc_code'] == 'A':
            return 100  # Bulk for high-value items
        elif sku_data['abc_code'] == 'C':
            return 50
        else:
            return sku_data.get('transfer_multiple', 50)
    
    def calculate_safety_stock(self, sku_data: Dict[str, Any], 
                               demand_std_dev: float) -> float:
        """
        Calculate safety stock using statistical formula
        Based on knowledge base formulas
        """
        classification = f"{sku_data['abc_code']}{sku_data['xyz_code']}"
        z_score = self.z_scores.get(classification, 1.65)
        
        # Lead time = 21 days (3 weeks)
        lead_time = 21
        
        # Safety stock formula from knowledge base
        safety_stock = z_score * demand_std_dev * np.sqrt(lead_time)
        
        return safety_stock
```

### 4.4 Database Connection (database.py)

```python
# backend/database.py
from sqlalchemy import create_engine
import pymysql
from contextlib import contextmanager

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # XAMPP default
    'database': 'warehouse_transfer',
    'charset': 'utf8mb4'
}

# Create SQLAlchemy engine
engine = create_engine(
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
)

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()

def test_connection():
    """Test database connection"""
    try:
        with get_db_connection() as conn:
            result = conn.execute("SELECT 1")
            print("Database connection successful!")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
```

---

## 5. Frontend Implementation (Simple HTML/JS)

### 5.1 Main Dashboard (index.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Warehouse Transfer Planning</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <!-- Custom CSS -->
    <style>
        .metric-card {
            border-left: 4px solid;
            transition: transform 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-5px);
        }
        .metric-card.critical { border-left-color: #dc3545; }
        .metric-card.warning { border-left-color: #ffc107; }
        .metric-card.info { border-left-color: #0dcaf0; }
        .metric-card.success { border-left-color: #198754; }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-warehouse"></i> Transfer Planning Tool
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="index.html">Dashboard</a>
                <a class="nav-link" href="transfer-planning.html">Transfer Planning</a>
                <a class="nav-link" href="import.html">Import Data</a>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="container-fluid mt-4">
        <!-- Metrics Row -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card metric-card critical">
                    <div class="card-body">
                        <h6 class="text-muted">Critical SKUs</h6>
                        <h2 id="critical-count">
                            <span class="spinner-border spinner-border-sm"></span>
                        </h2>
                        <small>Out of stock or <7 days</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card warning">
                    <div class="card-body">
                        <h6 class="text-muted">Low Stock</h6>
                        <h2 id="low-stock-count">
                            <span class="spinner-border spinner-border-sm"></span>
                        </h2>
                        <small>7-14 days coverage</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card info">
                    <div class="card-body">
                        <h6 class="text-muted">Transfer Units</h6>
                        <h2 id="transfer-units">
                            <span class="spinner-border spinner-border-sm"></span>
                        </h2>
                        <small>Recommended to transfer</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card success">
                    <div class="card-body">
                        <h6 class="text-muted">Transfer Value</h6>
                        <h2 id="transfer-value">
                            <span class="spinner-border spinner-border-sm"></span>
                        </h2>
                        <small>Total value to transfer</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Quick Actions</h5>
                        <a href="transfer-planning.html" class="btn btn-primary">
                            <i class="fas fa-exchange-alt"></i> Plan Transfer
                        </a>
                        <button class="btn btn-success" onclick="refreshData()">
                            <i class="fas fa-sync"></i> Refresh Data
                        </button>
                        <a href="import.html" class="btn btn-info">
                            <i class="fas fa-upload"></i> Import Excel
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Alerts Section -->
        <div class="row">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Recent Alerts</h5>
                    </div>
                    <div class="card-body" id="alerts-container">
                        <div class="text-center">
                            <span class="spinner-border spinner-border-sm"></span>
                            Loading alerts...
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        // API base URL
        const API_URL = 'http://localhost:8000';

        // Load dashboard metrics on page load
        $(document).ready(function() {
            loadDashboardMetrics();
            loadAlerts();
            
            // Auto-refresh every 5 minutes
            setInterval(function() {
                loadDashboardMetrics();
                loadAlerts();
            }, 300000);
        });

        function loadDashboardMetrics() {
            $.ajax({
                url: `${API_URL}/api/dashboard-metrics`,
                method: 'GET',
                success: function(data) {
                    $('#critical-count').text(data.critical_count);
                    $('#low-stock-count').text(data.low_stock_count);
                    $('#transfer-units').text(data.transfer_units.toLocaleString());
                    $('#transfer-value').text('$' + data.transfer_value.toLocaleString());
                },
                error: function(xhr, status, error) {
                    console.error('Error loading metrics:', error);
                    $('.metric-card h2').html('<i class="fas fa-exclamation-triangle text-danger"></i>');
                }
            });
        }

        function loadAlerts() {
            // In a real app, this would fetch from an alerts endpoint
            // For now, we'll generate sample alerts based on metrics
            $.ajax({
                url: `${API_URL}/api/transfer-recommendations`,
                method: 'GET',
                data: { max_coverage_days: 7 },
                success: function(data) {
                    let alertsHtml = '';
                    
                    if (data.length === 0) {
                        alertsHtml = '<div class="alert alert-success">No critical alerts at this time.</div>';
                    } else {
                        data.slice(0, 5).forEach(function(item) {
                            const alertClass = item.current_coverage_days < 3 ? 'danger' : 'warning';
                            const icon = item.current_coverage_days < 3 ? 'exclamation-circle' : 'exclamation-triangle';
                            
                            alertsHtml += `
                                <div class="alert alert-${alertClass} d-flex justify-content-between align-items-center">
                                    <div>
                                        <i class="fas fa-${icon}"></i>
                                        <strong>${item.sku_id}</strong> - ${item.description}
                                        <br>
                                        <small>Coverage: ${item.current_coverage_days} days | 
                                        Recommended Transfer: ${item.recommended_qty} units</small>
                                    </div>
                                    <a href="transfer-planning.html?sku=${item.sku_id}" 
                                       class="btn btn-sm btn-${alertClass}">
                                        View Details
                                    </a>
                                </div>
                            `;
                        });
                    }
                    
                    $('#alerts-container').html(alertsHtml);
                },
                error: function(xhr, status, error) {
                    $('#alerts-container').html(
                        '<div class="alert alert-danger">Error loading alerts. Please refresh.</div>'
                    );
                }
            });
        }

        function refreshData() {
            loadDashboardMetrics();
            loadAlerts();
            
            // Show toast notification
            const toast = `
                <div class="position-fixed bottom-0 end-0 p-3" style="z-index: 11">
                    <div class="toast show" role="alert">
                        <div class="toast-header">
                            <strong class="me-auto">Success</strong>
                            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                        </div>
                        <div class="toast-body">
                            Data refreshed successfully!
                        </div>
                    </div>
                </div>
            `;
            $('body').append(toast);
            setTimeout(() => $('.toast').remove(), 3000);
        }
    </script>
</body>
</html>
```

### 5.2 Transfer Planning Page (transfer-planning.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transfer Planning - Warehouse Transfer Tool</title>
    
    <!-- CSS Libraries -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/buttons/2.4.1/css/buttons.bootstrap5.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    
    <style>
        .table-danger { background-color: #f8d7da !important; }
        .table-warning { background-color: #fff3cd !important; }
        .badge-stockout { background-color: #ff6b6b; }
        .transfer-input { width: 100px; }
        .dataTables_wrapper .dt-buttons {
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="index.html">
                <i class="fas fa-warehouse"></i> Transfer Planning Tool
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="index.html">Dashboard</a>
                <a class="nav-link active" href="transfer-planning.html">Transfer Planning</a>
                <a class="nav-link" href="import.html">Import Data</a>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="container-fluid mt-3">
        <!-- Filters -->
        <div class="card mb-3">
            <div class="card-body">
                <div class="row">
                    <div class="col-md-3">
                        <label class="form-label">Status</label>
                        <select id="filter-status" class="form-select">
                            <option value="">All</option>
                            <option value="Active" selected>Active</option>
                            <option value="Death Row">Death Row</option>
                            <option value="Discontinued">Discontinued</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">ABC Classification</label>
                        <select id="filter-abc" class="form-select">
                            <option value="">All</option>
                            <option value="A">A - High Value</option>
                            <option value="B">B - Medium Value</option>
                            <option value="C">C - Low Value</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">Coverage Days</label>
                        <select id="filter-coverage" class="form-select">
                            <option value="">All</option>
                            <option value="critical">Critical (<7 days)</option>
                            <option value="low">Low (7-14 days)</option>
                            <option value="ok">OK (14-30 days)</option>
                            <option value="excess">Excess (>30 days)</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">&nbsp;</label>
                        <button class="btn btn-primary w-100" onclick="applyFilters()">
                            <i class="fas fa-filter"></i> Apply Filters
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Transfer Table -->
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">Transfer Recommendations</h5>
                <div>
                    <span class="badge bg-info me-2">
                        Selected: <span id="selected-count">0</span> items
                    </span>
                    <span class="badge bg-success">
                        Value: $<span id="selected-value">0</span>
                    </span>
                </div>
            </div>
            <div class="card-body">
                <table id="transfer-table" class="table table-striped table-hover">
                    <thead>
                        <tr>
                            <th><input type="checkbox" id="select-all"></th>
                            <th>SKU</th>
                            <th>Description</th>
                            <th>Status</th>
                            <th>ABC-XYZ</th>
                            <th>KY Stock</th>
                            <th>Pending</th>
                            <th>Sales (30d)</th>
                            <th>Corrected</th>
                            <th>Coverage</th>
                            <th>Recommended</th>
                            <th>Transfer Qty</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="transfer-tbody">
                        <!-- Populated by JavaScript -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- SKU Detail Modal -->
    <div class="modal fade" id="skuModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">SKU Details</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="modal-content">
                    <!-- Populated dynamically -->
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" onclick="saveModalChanges()">Save Changes</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/2.4.1/js/dataTables.buttons.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/2.4.1/js/buttons.bootstrap5.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/2.4.1/js/buttons.html5.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <script>
        const API_URL = 'http://localhost:8000';
        let dataTable;
        let recommendationsData = [];

        $(document).ready(function() {
            loadRecommendations();
            
            // Select all checkbox
            $('#select-all').on('change', function() {
                $('.item-checkbox').prop('checked', this.checked);
                updateSelection();
            });
        });

        function loadRecommendations() {
            const params = {
                status: $('#filter-status').val(),
                abc_code: $('#filter-abc').val()
            };

            $.ajax({
                url: `${API_URL}/api/transfer-recommendations`,
                method: 'GET',
                data: params,
                success: function(data) {
                    recommendationsData = data;
                    renderTable(data);
                },
                error: function(xhr, status, error) {
                    console.error('Error loading recommendations:', error);
                    alert('Error loading recommendations. Please try again.');
                }
            });
        }

        function renderTable(data) {
            // Destroy existing DataTable if it exists
            if (dataTable) {
                dataTable.destroy();
            }

            // Build table HTML
            let tableHtml = '';
            data.forEach(function(item) {
                // Determine row class based on coverage
                let rowClass = '';
                if (item.current_coverage_days < 7) {
                    rowClass = 'table-danger';
                } else if (item.current_coverage_days < 14) {
                    rowClass = 'table-warning';
                }

                // Stockout indicator
                let stockoutBadge = '';
                if (item.stockout_adjusted) {
                    stockoutBadge = '<span class="badge badge-stockout" title="Demand adjusted for stockout">SO</span>';
                }

                tableHtml += `
                    <tr class="${rowClass}">
                        <td>
                            <input type="checkbox" class="item-checkbox" 
                                data-sku="${item.sku_id}" 
                                data-value="${item.transfer_value}">
                        </td>
                        <td>${item.sku_id}</td>
                        <td>${item.description}</td>
                        <td>
                            <span class="badge bg-${getStatusColor(item.status)}">
                                ${item.status}
                            </span>
                        </td>
                        <td>${item.abc_xyz}</td>
                        <td>${item.kentucky_qty}</td>
                        <td>${item.pending_qty}</td>
                        <td>${item.kentucky_sales_30d}</td>
                        <td>
                            ${item.corrected_demand} ${stockoutBadge}
                        </td>
                        <td>${item.current_coverage_days.toFixed(1)}d</td>
                        <td>${item.recommended_qty}</td>
                        <td>
                            <input type="number" 
                                class="form-control form-control-sm transfer-input" 
                                value="${item.transfer_qty}"
                                data-sku="${item.sku_id}"
                                step="25"
                                min="0">
                        </td>
                        <td>
                            <button class="btn btn-sm btn-info" 
                                onclick="showSKUDetail('${item.sku_id}')">
                                <i class="fas fa-info-circle"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });

            $('#transfer-tbody').html(tableHtml);

            // Initialize DataTable
            dataTable = $('#transfer-table').DataTable({
                pageLength: 50,
                order: [[9, 'asc']], // Sort by coverage days
                dom: 'Bfrtip',
                buttons: [
                    {
                        extend: 'excel',
                        text: '<i class="fas fa-file-excel"></i> Export Excel',
                        className: 'btn btn-success btn-sm',
                        exportOptions: {
                            columns: ':not(:first-child):not(:last-child)'
                        }
                    },
                    {
                        text: '<i class="fas fa-truck"></i> Generate Transfer Order',
                        className: 'btn btn-primary btn-sm',
                        action: function() {
                            generateTransferOrder();
                        }
                    }
                ],
                columnDefs: [
                    { orderable: false, targets: [0, 11, 12] }
                ]
            });

            // Bind events
            $('.item-checkbox').on('change', updateSelection);
            $('.transfer-input').on('change', function() {
                updateTransferQty($(this).data('sku'), $(this).val());
            });
        }

        function getStatusColor(status) {
            const colors = {
                'Active': 'success',
                'Death Row': 'warning',
                'Discontinued': 'secondary'
            };
            return colors[status] || 'secondary';
        }

        function updateSelection() {
            let count = 0;
            let totalValue = 0;

            $('.item-checkbox:checked').each(function() {
                count++;
                totalValue += parseFloat($(this).data('value')) || 0;
            });

            $('#selected-count').text(count);
            $('#selected-value').text(totalValue.toFixed(2));
        }

        function updateTransferQty(sku, qty) {
            $.ajax({
                url: `${API_URL}/api/update-transfer-qty`,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ sku_id: sku, new_qty: parseInt(qty) }),
                success: function(response) {
                    // Update the input with rounded value if different
                    if (response.rounded_qty && response.rounded_qty !== parseInt(qty)) {
                        $(`.transfer-input[data-sku="${sku}"]`).val(response.rounded_qty);
                    }
                }
            });
        }

        function showSKUDetail(sku_id) {
            $.ajax({
                url: `${API_URL}/api/sku/${sku_id}`,
                method: 'GET',
                success: function(data) {
                    let html = `
                        <div class="row">
                            <div class="col-md-6">
                                <h6>Inventory Status</h6>
                                <table class="table table-sm">
                                    <tr><td>Burnaby:</td><td>${data.sku_info.burnaby_qty}</td></tr>
                                    <tr><td>Kentucky:</td><td>${data.sku_info.kentucky_qty}</td></tr>
                                    <tr><td>Cost:</td><td>$${data.sku_info.cost_per_unit}</td></tr>
                                </table>
                                
                                <h6 class="mt-3">Statistics</h6>
                                <table class="table table-sm">
                                    <tr><td>Avg Daily Sales:</td><td>${data.statistics.avg_daily_sales}</td></tr>
                                    <tr><td>Std Deviation:</td><td>${data.statistics.std_deviation}</td></tr>
                                    <tr><td>CV:</td><td>${data.statistics.cv}</td></tr>
                                    <tr><td>Stockout Days (90d):</td><td>${data.statistics.stockout_days_90d}</td></tr>
                                </table>
                            </div>
                            <div class="col-md-6">
                                <h6>Sales History</h6>
                                <canvas id="sales-chart" height="200"></canvas>
                            </div>
                        </div>
                    `;
                    
                    $('#modal-content').html(html);
                    $('#skuModal').modal('show');
                    
                    // Draw chart
                    setTimeout(() => drawSalesChart(data.sales_history), 100);
                }
            });
        }

        function drawSalesChart(salesHistory) {
            const ctx = document.getElementById('sales-chart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: salesHistory.map(s => s.date),
                    datasets: [{
                        label: 'Daily Sales',
                        data: salesHistory.map(s => s.kentucky_sales),
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }

        function generateTransferOrder() {
            // Collect items with transfer_qty > 0
            let items = [];
            recommendationsData.forEach(function(item) {
                const input = $(`.transfer-input[data-sku="${item.sku_id}"]`);
                const qty = parseInt(input.val()) || 0;
                if (qty > 0) {
                    items.push({
                        ...item,
                        transfer_qty: qty
                    });
                }
            });

            if (items.length === 0) {
                alert('No items selected for transfer');
                return;
            }

            // Send to backend
            $.ajax({
                url: `${API_URL}/api/generate-transfer-order`,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(items),
                xhrFields: {
                    responseType: 'blob'
                },
                success: function(blob) {
                    // Create download link
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `transfer_order_${new Date().toISOString().split('T')[0]}.xlsx`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    
                    alert('Transfer order generated successfully!');
                },
                error: function() {
                    alert('Error generating transfer order');
                }
            });
        }

        function applyFilters() {
            loadRecommendations();
        }
    </script>
</body>
</html>
```

---

## 6. Setup Instructions

### 6.1 Backend Setup

```bash
# 1. Install Python (3.9 or higher)
# Download from python.org

# 2. Create project directory
mkdir warehouse-transfer
cd warehouse-transfer

# 3. Create virtual environment
python -m venv venv

# 4. Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Create exports directory
mkdir exports

# 7. Run the application
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 6.2 Database Setup

```sql
-- 1. Open phpMyAdmin (http://localhost/phpmyadmin)
-- 2. Run the schema.sql file
-- 3. Import sample data (optional)

-- Sample data for testing
INSERT INTO skus (sku_id, description, supplier, status, cost_per_unit, transfer_multiple) VALUES
('TEST-001', 'Test Product 1', 'Supplier A', 'Active', 10.00, 50),
('TEST-002', 'Test Product 2', 'Supplier B', 'Active', 20.00, 25);

INSERT INTO inventory_current (sku_id, burnaby_qty, kentucky_qty) VALUES
('TEST-001', 500, 20),
('TEST-002', 300, 0);

-- Add sample sales data
INSERT INTO sales_daily (date, sku_id, kentucky_sales, kentucky_was_available)
VALUES 
(CURDATE() - INTERVAL 1 DAY, 'TEST-001', 10, TRUE),
(CURDATE() - INTERVAL 2 DAY, 'TEST-001', 15, TRUE),
(CURDATE() - INTERVAL 3 DAY, 'TEST-001', 0, FALSE);
```

### 6.3 Frontend Setup

```bash
# No build process needed!
# 1. Save HTML files in frontend directory
# 2. Open index.html in browser
# 3. Make sure backend is running on port 8000
```

---

## 7. Usage Guide

### 7.1 Daily Workflow

1. **Morning Check (5 minutes)**
   - Open Dashboard
   - Review critical alerts
   - Check metrics

2. **Transfer Planning (10 minutes)**
   - Go to Transfer Planning page
   - Review recommendations (sorted by urgency)
   - Adjust quantities as needed
   - Generate transfer order

3. **Data Updates**
   - Import new inventory snapshot (weekly/monthly)
   - System auto-calculates everything

### 7.2 Key Features

**Stockout Correction**
- Automatically detects when SKUs were out of stock
- Adjusts demand upward to reflect true demand
- Shows "SO" badge when correction applied

**Smart Rounding**
- Automatically rounds to transfer multiples
- Different rules for chargers (25), standard (50), bulk (100)

**Coverage Analysis**
- Color coding: Red (<7 days), Yellow (7-14 days), Normal (14+ days)
- Considers pending inventory arrivals

**Export Options**
- Excel export with all data
- Transfer order generation
- Filters persist during export

---

## 8. Testing Checklist

- [ ] Import Excel file with inventory data
- [ ] View dashboard metrics
- [ ] Filter transfer recommendations
- [ ] Adjust transfer quantities
- [ ] Generate transfer order
- [ ] View SKU details
- [ ] Export to Excel
- [ ] Test with 2000+ SKUs
- [ ] Verify stockout corrections
- [ ] Test rounding logic

---

## 9. Future Enhancements

1. **Phase 2 (Optional)**
   - Connect directly to OMS API
   - Automated daily sync
   - Email alerts for critical items

2. **Phase 3 (Optional)**
   - Historical performance tracking
   - Machine learning for demand forecasting
   - Multi-warehouse support

---

## 10. Support & Maintenance

### Common Issues & Solutions

**CORS Error**: Make sure FastAPI CORS middleware is configured
**Database Connection Failed**: Check XAMPP MySQL is running
**No Data Showing**: Verify data exists in database tables

### Performance Tips
- Index database columns used in WHERE clauses
- Use pagination for large datasets
- Cache calculated values when possible

---

This simplified PRD provides everything needed to build a working system quickly. The focus is on practical implementation with no unnecessary complexity. Start with the backend API, then the database, and finally the simple frontend. You should have a working system within 1-2 weeks.