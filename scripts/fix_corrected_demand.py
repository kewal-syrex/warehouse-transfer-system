"""
Fix Corrected Demand Values Script

This script recalculates and updates the corrected_demand_burnaby and corrected_demand_kentucky
values for all SKUs in the monthly_sales table using the existing ENHANCED calculation methods.

Currently, these values are 0.00 even when there are actual sales, which breaks the entire
transfer calculation system. The enhanced calculation includes:

- Stockout correction with 30% floor and 50% cap
- Year-over-year seasonal comparisons
- Category average fallbacks for new products
- Viral growth detection and adjustment
- Seasonal pattern recognition and multipliers

The script uses the existing StockoutCorrector.correct_monthly_demand_enhanced() method
which includes all the sophisticated logic from the forecasting courses.

Usage:
    python scripts/fix_corrected_demand.py

Dependencies:
    - MySQL connection to warehouse_transfer database
    - Access to backend/database.py and calculations.py modules
"""

import sys
import os

# Add backend directory to path so we can import database module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    import database
    import calculations
    import pymysql
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this from the project root and database.py/calculations.py are available")
    sys.exit(1)

import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def calculate_enhanced_corrected_demand(sku_id: str, monthly_sales: int, stockout_days: int, year_month: str) -> float:
    """
    Calculate enhanced corrected demand using the existing sophisticated calculation system

    This uses the StockoutCorrector.correct_monthly_demand_enhanced() method which includes:
    - Basic stockout correction with 30% floor and 50% cap
    - Year-over-year seasonal comparisons
    - Category average fallbacks for new products
    - Enhanced logic for zero sales with significant stockouts

    Args:
        sku_id: SKU identifier for historical lookup
        monthly_sales: Actual units sold in the month
        stockout_days: Number of days out of stock in the month
        year_month: Period for analysis (YYYY-MM format)

    Returns:
        Enhanced corrected demand with all sophisticated adjustments
    """
    try:
        corrector = calculations.StockoutCorrector()

        # Use the existing enhanced method that includes all the sophisticated logic
        corrected_demand = corrector.correct_monthly_demand_enhanced(
            sku_id=sku_id,
            monthly_sales=monthly_sales,
            stockout_days=stockout_days,
            year_month=year_month
        )

        logger.debug(f"Enhanced correction for {sku_id} {year_month}: {monthly_sales} -> {corrected_demand}")
        return corrected_demand

    except Exception as e:
        logger.error(f"Enhanced correction failed for {sku_id} {year_month}: {e}")

        # Fallback to basic correction if enhanced fails
        if monthly_sales == 0:
            return 0.0
        if stockout_days == 0:
            return float(monthly_sales)

        # Basic stockout correction as fallback
        availability_rate = max((30 - stockout_days) / 30, 0.3)
        corrected = monthly_sales / availability_rate
        return round(min(corrected, monthly_sales * 1.5), 2)


def get_all_sales_records():
    """
    Get all monthly sales records that need corrected demand calculation

    Returns:
        List of sales records with sku_id, year_month, and sales data
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        query = """
        SELECT
            `year_month`,
            sku_id,
            burnaby_sales,
            kentucky_sales,
            burnaby_stockout_days,
            kentucky_stockout_days,
            corrected_demand_burnaby,
            corrected_demand_kentucky
        FROM monthly_sales
        WHERE (burnaby_sales > 0 OR kentucky_sales > 0)
        ORDER BY sku_id, `year_month`
        """

        cursor.execute(query)
        records = cursor.fetchall()

        cursor.close()
        db.close()

        logger.info(f"Retrieved {len(records)} sales records for processing")
        return records

    except Exception as e:
        logger.error(f"Failed to retrieve sales records: {e}")
        return []


def update_corrected_demand_both_warehouses(sku_id: str, year_month: str,
                                          corrected_burnaby: float, corrected_kentucky: float):
    """
    Update the corrected demand values for both warehouses using the existing database function

    Args:
        sku_id: SKU identifier
        year_month: Year-month period (e.g., '2025-08')
        corrected_burnaby: Enhanced corrected demand for Burnaby
        corrected_kentucky: Enhanced corrected demand for Kentucky
    """
    try:
        # Use the existing database function for Kentucky
        success_ky = database.update_corrected_demand(sku_id, year_month, corrected_kentucky, 'kentucky')

        # Use the existing database function for Burnaby
        success_by = database.update_corrected_demand(sku_id, year_month, corrected_burnaby, 'burnaby')

        if success_ky and success_by:
            logger.debug(f"Updated {sku_id} {year_month}: BY={corrected_burnaby}, KY={corrected_kentucky}")
            return True
        else:
            logger.error(f"Partial update failure for {sku_id} {year_month}")
            return False

    except Exception as e:
        logger.error(f"Failed to update corrected demand for {sku_id} {year_month}: {e}")
        return False


def fix_all_corrected_demands():
    """
    Main function to fix all corrected demand values in the database
    """
    logger.info("Starting corrected demand fix process...")

    # Get all sales records
    records = get_all_sales_records()

    if not records:
        logger.error("No sales records found. Exiting.")
        return False

    updated_count = 0
    skipped_count = 0

    for record in records:
        year_month = record['year_month']
        sku_id = record['sku_id']
        burnaby_sales = record['burnaby_sales'] or 0
        kentucky_sales = record['kentucky_sales'] or 0
        burnaby_stockout_days = record['burnaby_stockout_days'] or 0
        kentucky_stockout_days = record['kentucky_stockout_days'] or 0

        # Calculate enhanced corrected demands for both warehouses using existing sophisticated methods
        corrected_burnaby = calculate_enhanced_corrected_demand(
            sku_id, burnaby_sales, burnaby_stockout_days, year_month)
        corrected_kentucky = calculate_enhanced_corrected_demand(
            sku_id, kentucky_sales, kentucky_stockout_days, year_month)

        # Check if update is needed
        current_burnaby = float(record['corrected_demand_burnaby'] or 0)
        current_kentucky = float(record['corrected_demand_kentucky'] or 0)

        if (abs(current_burnaby - corrected_burnaby) > 0.01 or
            abs(current_kentucky - corrected_kentucky) > 0.01):

            # Update the database using existing functions
            if update_corrected_demand_both_warehouses(sku_id, year_month, corrected_burnaby, corrected_kentucky):
                updated_count += 1
            else:
                logger.error(f"Failed to update {sku_id} {year_month}")

            if updated_count <= 10:  # Log first 10 updates for verification
                logger.info(f"Updated {sku_id} {year_month}: "
                          f"BY: {current_burnaby} -> {corrected_burnaby}, "
                          f"KY: {current_kentucky} -> {corrected_kentucky}")
        else:
            skipped_count += 1

    logger.info(f"Corrected demand fix completed:")
    logger.info(f"  - Updated: {updated_count} records")
    logger.info(f"  - Skipped (no change needed): {skipped_count} records")
    logger.info(f"  - Total processed: {len(records)} records")

    return True


def verify_specific_sku(sku_id: str):
    """
    Verify the corrected demand fix for a specific SKU

    Args:
        sku_id: SKU to verify (e.g., 'UB-YTX14-BS')
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        query = """
        SELECT
            `year_month`,
            burnaby_sales,
            kentucky_sales,
            burnaby_stockout_days,
            kentucky_stockout_days,
            corrected_demand_burnaby,
            corrected_demand_kentucky
        FROM monthly_sales
        WHERE sku_id = %s
        ORDER BY `year_month` DESC
        """

        cursor.execute(query, (sku_id,))
        records = cursor.fetchall()

        cursor.close()
        db.close()

        if records:
            logger.info(f"\nVerification for SKU {sku_id}:")
            logger.info("Month    | BY Sales | KY Sales | BY Corrected | KY Corrected | BY Stockout | KY Stockout")
            logger.info("-" * 95)

            total_ky_corrected = 0
            total_by_corrected = 0
            count = 0

            for record in records:
                logger.info(f"{record['year_month']} | "
                          f"{record['burnaby_sales']:8} | "
                          f"{record['kentucky_sales']:8} | "
                          f"{record['corrected_demand_burnaby']:11.2f} | "
                          f"{record['corrected_demand_kentucky']:12.2f} | "
                          f"{record['burnaby_stockout_days']:11} | "
                          f"{record['kentucky_stockout_days']:11}")

                total_ky_corrected += record['corrected_demand_kentucky'] or 0
                total_by_corrected += record['corrected_demand_burnaby'] or 0
                count += 1

            if count > 0:
                avg_ky = total_ky_corrected / count
                avg_by = total_by_corrected / count
                logger.info(f"\nAverages: BY={avg_by:.1f}/month, KY={avg_ky:.1f}/month")

                # Calculate expected coverage
                from inventory_current_query import get_current_inventory
                try:
                    inventory = get_current_inventory(sku_id)
                    if inventory:
                        ky_coverage = inventory['kentucky_qty'] / max(avg_ky, 1)
                        logger.info(f"Kentucky Coverage: {inventory['kentucky_qty']} units / {avg_ky:.1f} demand = {ky_coverage:.1f} months")
                except:
                    pass
        else:
            logger.warning(f"No sales records found for SKU {sku_id}")

    except Exception as e:
        logger.error(f"Failed to verify SKU {sku_id}: {e}")


def get_current_inventory(sku_id: str):
    """
    Helper function to get current inventory for a SKU
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        query = """
        SELECT burnaby_qty, kentucky_qty
        FROM inventory_current
        WHERE sku_id = %s
        """

        cursor.execute(query, (sku_id,))
        result = cursor.fetchone()

        cursor.close()
        db.close()

        return result

    except Exception as e:
        logger.error(f"Failed to get inventory for {sku_id}: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("Warehouse Transfer Tool - Corrected Demand Fix Script")
    print("=" * 60)

    # Test database connection first
    try:
        db = database.get_database_connection()
        db.close()
        logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        sys.exit(1)

    # Ask for confirmation
    print("\nThis script will:")
    print("1. Recalculate corrected demand using ENHANCED methods (seasonal, viral, stockout)")
    print("2. Apply sophisticated adjustments for both Burnaby and Kentucky warehouses")
    print("3. Update the monthly_sales table with corrected values")
    print("4. Fix the transfer calculation issues that show 'No transfer needed'")
    print("5. Use existing StockoutCorrector.correct_monthly_demand_enhanced() methods")

    confirm = input("\nProceed with the fix? (y/N): ").strip().lower()

    if confirm == 'y':
        # Run the fix
        success = fix_all_corrected_demands()

        if success:
            print("\n" + "=" * 60)
            print("VERIFICATION - Testing specific SKU")
            print("=" * 60)

            # Verify with the problematic SKU
            verify_specific_sku('UB-YTX14-BS')

            print("\nFix completed successfully!")
            print("You can now test the transfer planning tool to see the corrected calculations.")
        else:
            print("Fix failed. Check the logs for details.")
    else:
        print("Fix cancelled by user.")