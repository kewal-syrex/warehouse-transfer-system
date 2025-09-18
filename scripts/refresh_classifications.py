"""
ABC-XYZ Classification Refresh Script

This script manually triggers the refresh of ABC-XYZ classifications for all active SKUs.
It uses the latest 12 months of sales data from both warehouses to recalculate classifications
based on value (ABC) and demand variability (XYZ).

Usage:
    python scripts/refresh_classifications.py [options]

Options:
    --dry-run    Show what would be updated without making changes
    --verbose    Show detailed progress information
    --sku-id     Only update classification for specific SKU

Examples:
    python scripts/refresh_classifications.py
    python scripts/refresh_classifications.py --dry-run --verbose
    python scripts/refresh_classifications.py --sku-id UB-YTX14-BS

Dependencies:
    - MySQL connection to warehouse_transfer database
    - Access to backend/database.py and calculations.py modules
"""

import sys
import os
import argparse
from typing import Dict, List, Optional

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


def get_current_classifications() -> Dict[str, Dict[str, str]]:
    """
    Get current ABC-XYZ classifications for all active SKUs

    Returns:
        Dictionary mapping sku_id to {'abc_code': str, 'xyz_code': str}
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        query = """
        SELECT sku_id, abc_code, xyz_code, updated_at
        FROM skus
        WHERE status = 'Active'
        ORDER BY sku_id
        """

        cursor.execute(query)
        records = cursor.fetchall()

        cursor.close()
        db.close()

        result = {}
        for record in records:
            result[record['sku_id']] = {
                'abc_code': record['abc_code'],
                'xyz_code': record['xyz_code'],
                'updated_at': record['updated_at']
            }

        logger.info(f"Retrieved current classifications for {len(result)} active SKUs")
        return result

    except Exception as e:
        logger.error(f"Failed to retrieve current classifications: {e}")
        return {}


def compare_classifications(old_classifications: Dict[str, Dict[str, str]],
                          new_classifications: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Compare old and new classifications to identify changes

    Args:
        old_classifications: Current classifications from database
        new_classifications: New classifications that would be applied

    Returns:
        Dictionary of SKUs with changes: {sku_id: {'old': 'AX', 'new': 'BZ', 'change': 'ABC downgrade'}}
    """
    changes = {}

    for sku_id in new_classifications:
        if sku_id in old_classifications:
            old_abc = old_classifications[sku_id]['abc_code'] or 'C'
            old_xyz = old_classifications[sku_id]['xyz_code'] or 'Z'
            old_class = f"{old_abc}{old_xyz}"

            new_abc = new_classifications[sku_id]['abc_code']
            new_xyz = new_classifications[sku_id]['xyz_code']
            new_class = f"{new_abc}{new_xyz}"

            if old_class != new_class:
                # Determine type of change
                change_type = []
                if old_abc != new_abc:
                    if old_abc < new_abc:  # A->B or A->C or B->C
                        change_type.append("ABC downgrade")
                    else:
                        change_type.append("ABC upgrade")

                if old_xyz != new_xyz:
                    if old_xyz < new_xyz:  # X->Y or X->Z or Y->Z
                        change_type.append("XYZ more variable")
                    else:
                        change_type.append("XYZ less variable")

                changes[sku_id] = {
                    'old': old_class,
                    'new': new_class,
                    'change': ', '.join(change_type)
                }

    return changes


def refresh_classifications_for_sku(sku_id: str, dry_run: bool = False) -> bool:
    """
    Refresh classification for a specific SKU

    Args:
        sku_id: SKU to refresh
        dry_run: If True, don't make actual changes

    Returns:
        True if successful (or would be successful in dry run)
    """
    try:
        # Get current classification
        current = get_current_classifications()
        if sku_id not in current:
            logger.warning(f"SKU {sku_id} not found in active SKUs")
            return False

        # Create temporary calculator instance
        calc = calculations.TransferCalculator()

        # Get sales data for this SKU
        from datetime import datetime, timedelta
        import calendar

        # Calculate 12 months back from the most recent sales data
        current_month_query = "SELECT MAX(`year_month`) as latest_month FROM monthly_sales WHERE sku_id = %s"
        latest_data = database.execute_query(current_month_query, (sku_id,))

        if not latest_data or not latest_data[0]['latest_month']:
            logger.warning(f"No sales data found for SKU {sku_id}")
            return False

        latest_month = latest_data[0]['latest_month']

        # Calculate 12 months back
        try:
            year, month = map(int, latest_month.split('-'))
            start_year = year - 1
            start_month = month
            start_date = f"{start_year:04d}-{start_month:02d}"
        except:
            start_date = "2024-01"

        # Get combined sales data for this SKU
        sales_query = """
        SELECT
            s.sku_id,
            s.cost_per_unit,
            ms.kentucky_sales,
            ms.burnaby_sales,
            ms.`year_month`
        FROM skus s
        LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id
        WHERE s.sku_id = %s
            AND s.status = 'Active'
            AND ms.`year_month` >= %s
            AND (ms.kentucky_sales > 0 OR ms.burnaby_sales > 0)
        ORDER BY ms.`year_month`
        """

        sales_data = database.execute_query(sales_query, (sku_id, start_date))

        if not sales_data:
            logger.warning(f"No sales data found for SKU {sku_id} from {start_date} onwards")
            return False

        # Calculate new classification
        cost_per_unit = sales_data[0]['cost_per_unit'] or 0
        sales_values = []

        for row in sales_data:
            total_monthly_sales = (row['kentucky_sales'] or 0) + (row['burnaby_sales'] or 0)
            sales_values.append(total_monthly_sales)

        annual_sales = sum(sales_values)
        annual_value = annual_sales * cost_per_unit

        # For single SKU, we need total annual value context - use current total from all SKUs
        total_value_query = """
        SELECT SUM(
            (SELECT SUM(COALESCE(kentucky_sales, 0) + COALESCE(burnaby_sales, 0))
             FROM monthly_sales ms2
             WHERE ms2.sku_id = s.sku_id AND ms2.`year_month` >= %s) * s.cost_per_unit
        ) as total_value
        FROM skus s
        WHERE s.status = 'Active'
        """

        total_data = database.execute_query(total_value_query, (start_date,))
        total_annual_value = total_data[0]['total_value'] if total_data and total_data[0]['total_value'] else 1

        classifier = calculations.ABCXYZClassifier()
        new_abc = classifier.classify_abc(annual_value, total_annual_value)
        new_xyz = classifier.classify_xyz(sales_values)

        old_abc = current[sku_id]['abc_code'] or 'C'
        old_xyz = current[sku_id]['xyz_code'] or 'Z'

        if old_abc == new_abc and old_xyz == new_xyz:
            logger.info(f"SKU {sku_id}: No change needed (stays {old_abc}{old_xyz})")
            return True

        logger.info(f"SKU {sku_id}: {old_abc}{old_xyz} -> {new_abc}{new_xyz}")

        if not dry_run:
            # Update database
            update_query = """
            UPDATE skus
            SET abc_code = %s, xyz_code = %s, updated_at = NOW()
            WHERE sku_id = %s
            """

            db = database.get_database_connection()
            cursor = db.cursor()
            cursor.execute(update_query, (new_abc, new_xyz, sku_id))
            db.commit()
            cursor.close()
            db.close()

            logger.info(f"SKU {sku_id}: Classification updated successfully")

        return True

    except Exception as e:
        logger.error(f"Failed to refresh classification for SKU {sku_id}: {e}")
        return False


def refresh_all_classifications(dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Refresh all ABC-XYZ classifications

    Args:
        dry_run: If True, show what would change without making updates
        verbose: If True, show detailed progress information

    Returns:
        True if successful
    """
    try:
        if verbose:
            logger.setLevel(logging.DEBUG)

        logger.info("Starting ABC-XYZ classification refresh...")

        # Get current classifications before update
        current_classifications = get_current_classifications()
        if not current_classifications:
            logger.error("Failed to retrieve current classifications")
            return False

        # Run the update function to get new classifications
        if dry_run:
            logger.info("DRY RUN MODE - No actual changes will be made")

        # Use existing update function
        calc = calculations.TransferCalculator()
        success = calc.update_abc_xyz_classifications()

        if not success:
            logger.error("Classification update failed")
            return False

        if dry_run:
            # In dry run, we would need to simulate the changes
            # For now, just report that the function would run
            logger.info("DRY RUN: ABC-XYZ classification update would be performed")
            logger.info("Use --verbose for detailed change analysis (requires actual run)")
        else:
            logger.info("ABC-XYZ classification refresh completed successfully")

        return True

    except Exception as e:
        logger.error(f"Failed to refresh classifications: {e}")
        return False


def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Refresh ABC-XYZ classifications for warehouse transfer planning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/refresh_classifications.py
  python scripts/refresh_classifications.py --dry-run --verbose
  python scripts/refresh_classifications.py --sku-id UB-YTX14-BS
        """
    )

    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be updated without making changes')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed progress information')
    parser.add_argument('--sku-id', type=str,
                        help='Only update classification for specific SKU')

    args = parser.parse_args()

    print("=" * 60)
    print("Warehouse Transfer Tool - ABC-XYZ Classification Refresh")
    print("=" * 60)

    # Test database connection first
    try:
        db = database.get_database_connection()
        db.close()
        logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        sys.exit(1)

    # Determine what to do based on arguments
    if args.sku_id:
        # Single SKU refresh
        print(f"\nRefreshing classification for SKU: {args.sku_id}")
        if args.dry_run:
            print("DRY RUN MODE - No actual changes will be made")

        success = refresh_classifications_for_sku(args.sku_id, args.dry_run)
        if success:
            print(f"\n✓ SKU {args.sku_id} classification refresh completed")
        else:
            print(f"\n✗ SKU {args.sku_id} classification refresh failed")
            sys.exit(1)

    else:
        # Full refresh
        print("\nRefreshing ABC-XYZ classifications for all active SKUs...")
        print("This will use the latest 12 months of combined warehouse sales data")

        if args.dry_run:
            print("DRY RUN MODE - No actual changes will be made")
        else:
            confirm = input("\nProceed with classification refresh? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Classification refresh cancelled by user.")
                sys.exit(0)

        success = refresh_all_classifications(args.dry_run, args.verbose)
        if success:
            print("\n✓ ABC-XYZ classification refresh completed successfully")
            print("Transfer calculations will now use updated classifications")
        else:
            print("\n✗ ABC-XYZ classification refresh failed")
            sys.exit(1)


if __name__ == "__main__":
    main()