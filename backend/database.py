"""
Database connection and utility functions

This module provides database connectivity with both legacy PyMySQL support
and new SQLAlchemy connection pooling for improved performance.

Connection Pooling:
- Uses SQLAlchemy connection pooling to prevent connection exhaustion
- Falls back to direct PyMySQL connections if pooling fails
- Configurable pool size and overflow handling
"""
import pymysql
import pymysql.cursors
import os
from typing import Optional, Union, List, Dict, Any
import logging

# Import the new connection pool
try:
    from .database_pool import get_connection_pool, execute_pooled_query, DatabaseConnectionPool
    POOLING_AVAILABLE = True
except ImportError:
    # Fallback if SQLAlchemy is not available
    POOLING_AVAILABLE = False
    print("Warning: SQLAlchemy not available, using direct connections")

# Database configuration for legacy connections
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'warehouse_transfer'),
    'charset': 'utf8mb4',
    'autocommit': True
}

logger = logging.getLogger(__name__)

# Configuration for connection pooling
USE_CONNECTION_POOLING = os.getenv('USE_CONNECTION_POOLING', 'true').lower() == 'true'


def get_database_connection():
    """
    Create and return a database connection (legacy method)

    This is kept for backward compatibility. New code should use execute_query()
    which automatically uses connection pooling when available.
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

    Tests both connection pooling (if available) and direct connections.
    """
    try:
        if POOLING_AVAILABLE and USE_CONNECTION_POOLING:
            # Test using connection pool
            result = execute_pooled_query("SELECT 1 as test", fetch_one=True)
            return result is not None and result.get('test') == 1
        else:
            # Test using direct connection
            db = get_database_connection()
            cursor = db.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            db.close()
            return True

    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return False


def execute_query(query: str,
                 params: Optional[tuple] = None,
                 fetch_one: bool = False,
                 fetch_all: bool = True) -> Optional[Union[List[Dict], Dict, int]]:
    """
    Execute a database query with automatic connection pooling

    This function automatically uses connection pooling when available,
    falling back to direct connections if pooling is disabled or fails.

    Args:
        query: SQL query string
        params: Query parameters tuple
        fetch_one: Return single result
        fetch_all: Return all results (default)

    Returns:
        Query results or None

    Raises:
        Exception: If query execution fails
    """
    # Try using connection pooling first
    if POOLING_AVAILABLE and USE_CONNECTION_POOLING:
        try:
            return execute_pooled_query(query, params, fetch_one, fetch_all)
        except Exception as e:
            logger.warning(f"Connection pool failed, falling back to direct connection: {e}")

    # Fallback to direct connection (legacy method)
    return _execute_query_direct(query, params, fetch_one, fetch_all)


def _execute_query_direct(query: str,
                         params: Optional[tuple] = None,
                         fetch_one: bool = False,
                         fetch_all: bool = True) -> Optional[Union[List[Dict], Dict, int]]:
    """
    Execute a database query using direct PyMySQL connection (legacy method)

    This is the original implementation kept for fallback purposes.
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
        logger.error("Query execution failed: " + str(e))
        raise


def get_connection_pool_status() -> Dict[str, Any]:
    """
    Get connection pool status and statistics

    Returns:
        Dictionary containing pool status, or error info if pooling unavailable
    """
    if not POOLING_AVAILABLE:
        return {
            'pooling_available': False,
            'error': 'SQLAlchemy not installed'
        }

    if not USE_CONNECTION_POOLING:
        return {
            'pooling_available': True,
            'pooling_enabled': False,
            'reason': 'Disabled via configuration'
        }

    try:
        pool = get_connection_pool()
        status = pool.get_pool_status()
        status['pooling_available'] = True
        status['pooling_enabled'] = True
        return status
    except Exception as e:
        return {
            'pooling_available': True,
            'pooling_enabled': True,
            'error': str(e)
        }

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


def aggregate_stockout_days_for_month(sku_id: str, year_month: str, warehouse: str) -> int:
    """
    Calculate the number of stockout days for a specific SKU, month, and warehouse

    This function aggregates stockout periods from the stockout_dates table
    and calculates how many days within the specified month the SKU was out of stock.

    Business Logic:
    - Handles partial stockout periods that span month boundaries
    - Counts only days within the target month
    - Handles overlapping stockout periods by using date ranges
    - Returns 0 if no stockouts occurred in the specified month

    Args:
        sku_id: The SKU identifier
        year_month: Target month in YYYY-MM format (e.g., '2025-08')
        warehouse: Warehouse name ('kentucky' or 'burnaby')

    Returns:
        int: Number of days out of stock within the specified month (0-31)

    Example:
        # SKU was out from Aug 21 to Sep 2
        days = aggregate_stockout_days_for_month('UB-YTX14AH-BS', '2025-08', 'burnaby')
        # Returns 11 (Aug 21-31 = 11 days)

        days = aggregate_stockout_days_for_month('UB-YTX14AH-BS', '2025-09', 'burnaby')
        # Returns 2 (Sep 1-2 = 2 days)
    """
    try:
        # Parse year and month
        year, month = year_month.split('-')
        year, month = int(year), int(month)

        # Calculate month start and end dates
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        month_start = f"{year:04d}-{month:02d}-01"
        month_end = f"{next_year:04d}-{next_month:02d}-01"

        # Query stockout periods that overlap with the target month
        query = """
        SELECT
            stockout_date,
            COALESCE(resolved_date, CURDATE()) as end_date,
            is_resolved
        FROM stockout_dates
        WHERE sku_id = %s
            AND warehouse = %s
            AND stockout_date < %s
            AND COALESCE(resolved_date, CURDATE()) >= %s
        ORDER BY stockout_date
        """

        db = get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        cursor.execute(query, (sku_id, warehouse, month_end, month_start))
        stockout_periods = cursor.fetchall()
        cursor.close()
        db.close()

        if not stockout_periods:
            return 0

        # Calculate total days within the month
        total_days = 0

        for period in stockout_periods:
            period_start = period['stockout_date']
            period_end = period['end_date']

            # Convert to string format for comparison
            period_start_str = period_start.strftime('%Y-%m-%d')
            period_end_str = period_end.strftime('%Y-%m-%d')

            # Find the overlap between stockout period and target month
            overlap_start = max(period_start_str, month_start)
            overlap_end = min(period_end_str, month_end)

            # Calculate days in overlap (if any)
            if overlap_start < overlap_end:
                from datetime import datetime
                start_date = datetime.strptime(overlap_start, '%Y-%m-%d')
                end_date = datetime.strptime(overlap_end, '%Y-%m-%d')
                days_in_period = (end_date - start_date).days
                total_days += days_in_period

        # Cap at maximum days in month (safety check)
        import calendar
        max_days = calendar.monthrange(year, month)[1]
        return min(total_days, max_days)

    except Exception as e:
        logger.error(f"Stockout aggregation failed for {sku_id} {year_month} {warehouse}: {e}")
        return 0


def sync_all_stockout_days() -> Dict[str, Any]:
    """
    Synchronize all stockout days from stockout_dates table to monthly_sales table

    This function processes all stockout periods and updates the monthly_sales table
    with the correct stockout day counts for both warehouses. It handles:
    - All SKUs that have stockout records
    - All months that are affected by stockout periods
    - Both Burnaby and Kentucky warehouses
    - Proper aggregation of overlapping periods

    Returns:
        Dict containing:
        - success: boolean indicating if operation completed
        - processed_records: number of monthly_sales records updated
        - processed_skus: number of unique SKUs processed
        - errors: list of any errors encountered
        - duration_seconds: time taken to complete

    Example:
        result = sync_all_stockout_days()
        # {
        #     "success": True,
        #     "processed_records": 1234,
        #     "processed_skus": 567,
        #     "errors": [],
        #     "duration_seconds": 5.23
        # }
    """
    import time
    from datetime import datetime, timedelta

    start_time = time.time()
    processed_records = 0
    processed_skus = set()
    errors = []

    try:
        logger.info("Starting stockout days synchronization")

        # Get all unique SKU-warehouse combinations that have stockout data
        db = get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        # Find all month-year combinations that need updating
        query = """
        SELECT DISTINCT
            sd.sku_id,
            sd.warehouse,
            DATE_FORMAT(sd.stockout_date, '%Y-%m') as start_month,
            DATE_FORMAT(COALESCE(sd.resolved_date, CURDATE()), '%Y-%m') as end_month
        FROM stockout_dates sd
        JOIN skus s ON sd.sku_id = s.sku_id
        WHERE s.status = 'Active'
        ORDER BY sd.sku_id, sd.warehouse, start_month
        """

        cursor.execute(query)
        stockout_records = cursor.fetchall()

        if not stockout_records:
            cursor.close()
            db.close()
            return {
                "success": True,
                "processed_records": 0,
                "processed_skus": 0,
                "errors": ["No stockout records found"],
                "duration_seconds": time.time() - start_time
            }

        # Process each stockout record and generate all affected months
        months_to_update = set()

        for record in stockout_records:
            sku_id = record['sku_id']
            warehouse = record['warehouse']
            start_month = record['start_month']
            end_month = record['end_month']

            processed_skus.add(sku_id)

            # Generate all months between start and end
            current_date = datetime.strptime(start_month + '-01', '%Y-%m-%d')
            end_date = datetime.strptime(end_month + '-01', '%Y-%m-%d')

            while current_date <= end_date:
                year_month = current_date.strftime('%Y-%m')
                months_to_update.add((sku_id, warehouse, year_month))

                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)

        logger.info(f"Found {len(months_to_update)} month-warehouse combinations to update")

        # Update each month's stockout days
        for sku_id, warehouse, year_month in months_to_update:
            try:
                # Calculate stockout days for this month
                stockout_days = aggregate_stockout_days_for_month(sku_id, year_month, warehouse)

                # Determine which field to update
                field = f"{warehouse}_stockout_days"

                # Update or insert monthly_sales record
                update_query = f"""
                INSERT INTO monthly_sales (sku_id, `year_month`, {field})
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE {field} = VALUES({field})
                """

                cursor.execute(update_query, (sku_id, year_month, stockout_days))
                processed_records += 1

                if processed_records % 100 == 0:
                    logger.info(f"Processed {processed_records} records...")

            except Exception as e:
                error_msg = f"Failed to update {sku_id} {year_month} {warehouse}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        cursor.close()
        db.close()

        duration = time.time() - start_time
        logger.info(f"Stockout synchronization completed: {processed_records} records, {len(processed_skus)} SKUs in {duration:.2f}s")

        return {
            "success": True,
            "processed_records": processed_records,
            "processed_skus": len(processed_skus),
            "errors": errors,
            "duration_seconds": round(duration, 2)
        }

    except Exception as e:
        error_msg = f"Stockout synchronization failed: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "processed_records": processed_records,
            "processed_skus": len(processed_skus),
            "errors": errors + [error_msg],
            "duration_seconds": time.time() - start_time
        }