"""
Database connection and utility functions
"""
import pymysql
import pymysql.cursors
import os
from typing import Optional
import logging

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'warehouse_transfer'),
    'charset': 'utf8mb4',
    'autocommit': True
}

logger = logging.getLogger(__name__)

def get_database_connection():
    """
    Create and return a database connection
    """
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def test_connection() -> bool:
    """
    Test if database connection is working
    """
    try:
        db = get_database_connection()
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return False

def execute_query(query: str, params: Optional[tuple] = None, fetch_one: bool = False, fetch_all: bool = True):
    """
    Execute a database query with optional parameters
    
    Args:
        query: SQL query string
        params: Query parameters tuple
        fetch_one: Return single result
        fetch_all: Return all results (default)
    
    Returns:
        Query results or None
    """
    try:
        db = get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        cursor.execute(query, params)
        
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = None
            
        db.close()
        return result
        
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise

def get_current_stock_status():
    """
    Get current stock status for all active SKUs
    """
    query = """
    SELECT 
        s.sku_id,
        s.description,
        s.supplier,
        s.abc_code,
        s.xyz_code,
        s.transfer_multiple,
        ic.burnaby_qty,
        ic.kentucky_qty,
        CASE 
            WHEN ic.kentucky_qty = 0 THEN 'OUT_OF_STOCK'
            WHEN ic.kentucky_qty < 100 THEN 'LOW_STOCK'
            ELSE 'IN_STOCK'
        END as stock_status
    FROM skus s
    LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
    WHERE s.status = 'Active'
    ORDER BY 
        CASE 
            WHEN ic.kentucky_qty = 0 THEN 1
            WHEN ic.kentucky_qty < 100 THEN 2
            ELSE 3
        END,
        s.sku_id
    """
    return execute_query(query)

def get_monthly_sales_data(sku_id: Optional[str] = None, year_month: Optional[str] = None):
    """
    Get monthly sales data with optional filters
    """
    query = """
    SELECT 
        ms.`year_month`,
        ms.sku_id,
        s.description,
        ms.burnaby_sales,
        ms.kentucky_sales,
        ms.burnaby_stockout_days,
        ms.kentucky_stockout_days,
        ms.corrected_demand_kentucky,
        (ms.burnaby_sales + ms.kentucky_sales) as total_sales
    FROM monthly_sales ms
    JOIN skus s ON ms.sku_id = s.sku_id
    WHERE 1=1
    """
    
    params = []
    if sku_id:
        query += " AND ms.sku_id = %s"
        params.append(sku_id)
    if year_month:
        query += " AND ms.`year_month` = %s"
        params.append(year_month)
        
    query += " ORDER BY ms.`year_month` DESC, ms.sku_id"
    
    return execute_query(query, tuple(params) if params else None)

def get_out_of_stock_skus():
    """
    Get all SKUs that are currently out of stock in Kentucky
    """
    query = """
    SELECT 
        s.sku_id,
        s.description,
        s.abc_code,
        s.xyz_code,
        ic.burnaby_qty,
        ms.kentucky_sales as last_month_sales,
        ms.kentucky_stockout_days,
        sd.stockout_date,
        DATEDIFF(CURDATE(), sd.stockout_date) as days_out_of_stock
    FROM skus s
    JOIN inventory_current ic ON s.sku_id = ic.sku_id
    LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id AND ms.`year_month` = '2024-03'
    LEFT JOIN stockout_dates sd ON s.sku_id = sd.sku_id 
        AND sd.warehouse = 'kentucky' 
        AND sd.is_resolved = FALSE
    WHERE ic.kentucky_qty = 0 AND s.status = 'Active'
    ORDER BY sd.stockout_date ASC
    """
    return execute_query(query)

def update_corrected_demand(sku_id: str, year_month: str, corrected_demand: float, warehouse: str = 'kentucky'):
    """
    Update the corrected demand for a specific SKU and month
    """
    field = f'corrected_demand_{warehouse}'
    query = f"""
    UPDATE monthly_sales 
    SET {field} = %s
    WHERE sku_id = %s AND `year_month` = %s
    """
    
    try:
        db = get_database_connection()
        cursor = db.cursor()
        cursor.execute(query, (corrected_demand, sku_id, year_month))
        db.close()
        return True
    except Exception as e:
        logger.error(f"Update corrected demand failed: {e}")
        return False