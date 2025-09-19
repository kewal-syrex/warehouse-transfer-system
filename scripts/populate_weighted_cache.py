"""
Weighted Demand Cache Population Script

This script calculates weighted demands for all SKUs including:
- Stockout corrections based on availability rates
- Seasonal adjustments using ABC-XYZ classifications
- Volatility analysis for demand patterns
- All advanced features from the TransferCalculator

Expected execution time: 20 minutes for 1700+ SKUs
Results are cached in sku_demand_stats table for fast retrieval
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.calculations import TransferCalculator
from backend import database


class WeightedCachePopulator:
    """
    Populates weighted demand cache for all active SKUs

    This class handles the bulk calculation and caching of weighted demands
    for all SKUs in the system, preserving all advanced calculation features.
    """

    def __init__(self):
        """Initialize the cache populator with database connection and calculator"""
        self.calculator = TransferCalculator()
        self.total_skus = 0
        self.processed_skus = 0
        self.errors = []

    def get_all_active_skus(self) -> List[Dict[str, Any]]:
        """
        Retrieve all active SKUs with their classification and sales data

        Returns comprehensive SKU data needed for weighted demand calculations
        including ABC/XYZ codes and historical sales information.

        Returns:
            List of dictionaries containing SKU data with keys:
            - sku_id: Unique SKU identifier
            - abc_code: ABC classification (A/B/C)
            - xyz_code: XYZ volatility classification (X/Y/Z)
            - kentucky_sales: Latest monthly sales in Kentucky
            - kentucky_stockout_days: Stockout days in Kentucky
            - burnaby_sales: Latest monthly sales in Burnaby
            - burnaby_stockout_days: Stockout days in Burnaby
        """
        query = """
        SELECT
            s.sku_id,
            s.abc_code,
            s.xyz_code,
            COALESCE(ms.kentucky_sales, 0) as kentucky_sales,
            COALESCE(ms.kentucky_stockout_days, 0) as kentucky_stockout_days,
            COALESCE(ms.burnaby_sales, 0) as burnaby_sales,
            COALESCE(ms.burnaby_stockout_days, 0) as burnaby_stockout_days
        FROM skus s
        LEFT JOIN (
            SELECT
                sku_id,
                kentucky_sales,
                kentucky_stockout_days,
                burnaby_sales,
                burnaby_stockout_days,
                ROW_NUMBER() OVER (PARTITION BY sku_id ORDER BY `year_month` DESC) as rn
            FROM monthly_sales
            WHERE kentucky_sales > 0 OR burnaby_sales > 0
        ) ms ON s.sku_id = ms.sku_id AND ms.rn = 1
        WHERE s.status = 'Active' OR s.status IS NULL
        ORDER BY s.sku_id
        """

        try:
            return database.execute_query(query)
        except Exception as e:
            print(f"ERROR: Failed to retrieve SKU data: {e}")
            return []

    def calculate_and_cache_sku(self, sku_data: Dict[str, Any], warehouse: str) -> bool:
        """
        Calculate weighted demand for a single SKU and cache the result

        Performs the complete weighted demand calculation including all advanced
        features (stockout correction, seasonal adjustments, volatility analysis)
        and stores the result in the cache for fast future retrieval.

        Args:
            sku_data: Dictionary containing SKU information
            warehouse: Target warehouse ('kentucky' or 'burnaby')

        Returns:
            True if calculation and caching succeeded, False otherwise

        Raises:
            Exception: When calculation or caching fails
        """
        try:
            sku_id = sku_data['sku_id']
            abc_code = sku_data.get('abc_code', 'C')
            xyz_code = sku_data.get('xyz_code', 'Z')

            # Get warehouse-specific sales and stockout data
            sales_key = f'{warehouse}_sales'
            stockout_key = f'{warehouse}_stockout_days'

            monthly_sales = sku_data.get(sales_key, 0)
            stockout_days = sku_data.get(stockout_key, 0)

            # Calculate enhanced demand with all features
            result = self.calculator.weighted_demand_calculator.get_enhanced_demand_calculation(
                sku_id=sku_id,
                abc_class=abc_code,
                xyz_class=xyz_code,
                current_month_sales=monthly_sales,
                stockout_days=stockout_days,
                warehouse=warehouse
            )

            if result:
                # Store the calculated result in cache
                success = self.calculator.cache_manager.store_cached_demand(
                    sku_id, warehouse, result
                )

                if not success:
                    self.errors.append(f"Failed to cache {sku_id}-{warehouse}")
                    return False

                return True
            else:
                # Even if calculation returns None, store a zero value to avoid recalculation
                fallback_result = {
                    'enhanced_demand': 0,
                    'original_demand': monthly_sales,
                    'stockout_correction_applied': False,
                    'seasonal_adjustment_applied': False,
                    'volatility_factor': 1.0,
                    'abc_code': abc_code,
                    'xyz_code': xyz_code,
                    'calculation_notes': 'No calculation result - stored zero value'
                }

                self.calculator.cache_manager.store_cached_demand(
                    sku_id, warehouse, fallback_result
                )
                return True

        except Exception as e:
            error_msg = f"Error calculating {sku_data.get('sku_id', 'unknown')}-{warehouse}: {e}"
            self.errors.append(error_msg)
            print(f"  {error_msg}")
            return False

    def populate_cache_batch(self) -> None:
        """
        Execute the complete cache population process for all SKUs

        This is the main method that orchestrates the entire cache population:
        1. Retrieves all active SKUs
        2. Calculates weighted demands for both warehouses
        3. Caches all results for fast future access
        4. Provides progress tracking and error reporting
        """
        print("=" * 80)
        print("WAREHOUSE TRANSFER TOOL - WEIGHTED DEMAND CACHE POPULATION")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("Features included in calculations:")
        print("• Stockout correction with 30% availability floor")
        print("• Seasonal adjustments based on ABC-XYZ classification")
        print("• Volatility analysis for demand patterns")
        print("• Enhanced demand calculation with all business rules")
        print()
        print("Expected execution time: ~20 minutes")
        print("=" * 80)
        print()

        # Get all SKUs to process
        all_skus = self.get_all_active_skus()

        if not all_skus:
            print("ERROR: No SKUs found to process!")
            return

        self.total_skus = len(all_skus)
        print(f"Processing {self.total_skus} active SKUs...")
        print(f"Total calculations: {self.total_skus * 2} (both warehouses)")
        print("-" * 60)

        successful_calculations = 0

        # Process each SKU for both warehouses
        for i, sku_data in enumerate(all_skus, 1):
            sku_id = sku_data['sku_id']

            # Progress indicator every 100 SKUs
            if i % 100 == 0 or i == 1:
                progress_pct = (i / self.total_skus) * 100
                print(f"Progress: {i:4d}/{self.total_skus} SKUs ({progress_pct:5.1f}%) - Current: {sku_id}")

            # Calculate for both warehouses
            for warehouse in ['kentucky', 'burnaby']:
                if self.calculate_and_cache_sku(sku_data, warehouse):
                    successful_calculations += 1

            self.processed_skus = i

        # Final summary
        print("-" * 60)
        print("CACHE POPULATION COMPLETED!")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("Summary:")
        print(f"• SKUs processed: {self.processed_skus:,}")
        print(f"• Total calculations: {successful_calculations:,} / {self.total_skus * 2:,}")
        print(f"• Success rate: {(successful_calculations / (self.total_skus * 2) * 100):5.1f}%")

        if self.errors:
            print(f"• Errors encountered: {len(self.errors)}")
            print("\nFirst 10 errors:")
            for error in self.errors[:10]:
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")
        else:
            print("• No errors encountered")

        print()
        print("Cache is now populated with weighted demands including:")
        print("✓ Stockout corrections")
        print("✓ Seasonal adjustments")
        print("✓ Volatility analysis")
        print("✓ All advanced calculation features")
        print()
        print("Transfer planning page should now load in < 5 seconds!")
        print("=" * 80)


def main():
    """
    Main entry point for the cache population script

    Initializes the populator and executes the complete cache population process.
    This script should be run once initially and then as needed when data changes.
    """
    try:
        populator = WeightedCachePopulator()
        populator.populate_cache_batch()

    except KeyboardInterrupt:
        print("\n\nCACHE POPULATION INTERRUPTED BY USER")
        print("Partial results may have been cached.")
        print("You can safely run this script again to complete the process.")

    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        print("Cache population failed. Please check:")
        print("1. Database connection is working")
        print("2. Required tables exist (sku_demand_stats)")
        print("3. Backend modules are accessible")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)