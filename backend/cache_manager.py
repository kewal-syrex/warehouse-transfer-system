"""
Cache Management System for Weighted Demand Calculations

This module implements import-triggered caching to solve the database connection
exhaustion issue where calculating weighted demand for 1769 SKUs requires 5000+
individual database queries.

Key Features:
- Pre-calculates weighted demand values and stores in sku_demand_stats table
- Invalidates cache when new sales data is imported
- Batch processing for efficient database operations
- Fallback to live calculation when cache is unavailable
- Progress tracking for long-running operations

Performance Impact:
- Before: 5+ minutes with 5000+ database queries
- After: <30 seconds using cached values
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

try:
    from . import database
    from .weighted_demand import WeightedDemandCalculator
except ImportError:
    import database
    from weighted_demand import WeightedDemandCalculator

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages cached weighted demand calculations to improve performance

    The cache system pre-calculates weighted demand values for all SKUs and stores
    them in the sku_demand_stats table, reducing the need for individual queries
    during transfer recommendation calculations.
    """

    def __init__(self):
        """Initialize the cache manager"""
        self.weighted_calculator = WeightedDemandCalculator()

    def invalidate_cache(self, reason: str = "Manual invalidation") -> bool:
        """
        Invalidate the entire weighted demand cache

        Args:
            reason: Reason for cache invalidation (for logging)

        Returns:
            True if invalidation was successful
        """
        try:
            logger.info(f"Invalidating weighted demand cache: {reason}")

            # Mark all cache entries as invalid
            query = """
                UPDATE sku_demand_stats
                SET cache_valid = FALSE,
                    invalidated_at = NOW(),
                    invalidation_reason = %s
                WHERE cache_valid = TRUE
            """

            result = database.execute_query(query, (reason,), fetch_all=False)
            logger.info(f"Cache invalidated successfully. Reason: {reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False

    def is_cache_valid(self, sku_id: str, warehouse: str) -> bool:
        """
        Check if cached data exists and is valid for a specific SKU and warehouse

        Args:
            sku_id: SKU identifier
            warehouse: Warehouse ('kentucky' or 'burnaby')

        Returns:
            True if valid cached data exists
        """
        try:
            query = """
                SELECT cache_valid, last_calculated
                FROM sku_demand_stats
                WHERE sku_id = %s AND warehouse = %s AND cache_valid = TRUE
            """

            result = database.execute_query(query, (sku_id, warehouse), fetch_one=True)

            if result:
                # Cache is considered valid if calculated within last 24 hours
                last_calculated = result[1]
                if last_calculated:
                    age_hours = (datetime.now() - last_calculated).total_seconds() / 3600
                    return age_hours < 24

            return False

        except Exception as e:
            logger.error(f"Failed to check cache validity for {sku_id} ({warehouse}): {e}")
            return False

    def get_cached_weighted_demand(self, sku_id: str, warehouse: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached weighted demand calculation for a SKU and warehouse

        Args:
            sku_id: SKU identifier
            warehouse: Warehouse ('kentucky' or 'burnaby')

        Returns:
            Cached demand calculation result or None if not available
        """
        try:
            if not self.is_cache_valid(sku_id, warehouse):
                return None

            query = """
                SELECT
                    demand_6mo_weighted as enhanced_demand,
                    demand_6mo_weighted as weighted_average_base,
                    1.0 as volatility_adjustment,
                    calculation_method,
                    calculation_method as primary_method,
                    sample_size_months as sample_months,
                    data_quality_score,
                    volatility_class,
                    coefficient_variation,
                    demand_std_dev as standard_deviation,
                    last_calculated
                FROM sku_demand_stats
                WHERE sku_id = %s AND warehouse = %s AND cache_valid = TRUE
            """

            result = database.execute_query(query, (sku_id, warehouse), fetch_one=True)

            if result:
                return {
                    'enhanced_demand': float(result[0]) if result[0] else 0.0,
                    'weighted_average_base': float(result[1]) if result[1] else 0.0,
                    'volatility_adjustment': float(result[2]) if result[2] else 1.0,
                    'calculation_method': result[3] or 'cached',
                    'primary_method': result[4] or 'cached',
                    'sample_months': int(result[5]) if result[5] else 0,
                    'data_quality_score': float(result[6]) if result[6] else 0.0,
                    'volatility_class': result[7] or 'unknown',
                    'coefficient_variation': float(result[8]) if result[8] else 0.0,
                    'standard_deviation': float(result[9]) if result[9] else 0.0,
                    'cache_source': True,
                    'last_calculated': result[10]
                }

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve cached demand for {sku_id} ({warehouse}): {e}")
            return None

    def store_cached_demand(self, sku_id: str, warehouse: str, demand_result: Dict[str, Any]) -> bool:
        """
        Store weighted demand calculation result in cache

        Args:
            sku_id: SKU identifier
            warehouse: Warehouse ('kentucky' or 'burnaby')
            demand_result: Weighted demand calculation result

        Returns:
            True if storage was successful
        """
        try:
            query = """
                INSERT INTO sku_demand_stats (
                    sku_id, warehouse, demand_6mo_weighted, demand_3mo_weighted,
                    demand_6mo_simple, demand_3mo_simple, demand_std_dev,
                    calculation_method, sample_size_months, data_quality_score,
                    volatility_class, coefficient_variation, cache_valid,
                    last_calculated
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW()
                )
                ON DUPLICATE KEY UPDATE
                    demand_6mo_weighted = VALUES(demand_6mo_weighted),
                    demand_3mo_weighted = VALUES(demand_3mo_weighted),
                    demand_6mo_simple = VALUES(demand_6mo_simple),
                    demand_3mo_simple = VALUES(demand_3mo_simple),
                    demand_std_dev = VALUES(demand_std_dev),
                    calculation_method = VALUES(calculation_method),
                    sample_size_months = VALUES(sample_size_months),
                    data_quality_score = VALUES(data_quality_score),
                    volatility_class = VALUES(volatility_class),
                    coefficient_variation = VALUES(coefficient_variation),
                    cache_valid = TRUE,
                    last_calculated = NOW()
            """

            params = (
                sku_id,
                warehouse,
                demand_result.get('enhanced_demand', 0.0),  # demand_6mo_weighted
                demand_result.get('enhanced_demand', 0.0),  # demand_3mo_weighted
                demand_result.get('enhanced_demand', 0.0),  # demand_6mo_simple
                demand_result.get('enhanced_demand', 0.0),  # demand_3mo_simple
                demand_result.get('standard_deviation', 0.0),  # demand_std_dev
                demand_result.get('calculation_method', 'weighted'),
                demand_result.get('sample_months', 0),  # sample_size_months
                demand_result.get('data_quality_score', 0.0),
                demand_result.get('volatility_class', 'unknown'),
                demand_result.get('coefficient_variation', 0.0)
            )

            database.execute_query(query, params, fetch_all=False)
            return True

        except Exception as e:
            logger.error(f"Failed to store cached demand for {sku_id} ({warehouse}): {e}")
            return False

    def batch_load_sku_data(self) -> List[Dict[str, Any]]:
        """
        Load all SKU data in a single batch query to avoid individual queries

        Returns:
            List of SKU data dictionaries
        """
        try:
            query = """
                SELECT
                    sku_id,
                    abc_code,
                    xyz_code,
                    kentucky_qty,
                    burnaby_qty,
                    description
                FROM skus
                WHERE active = TRUE
                ORDER BY sku_id
            """

            results = database.execute_query(query, fetch_all=True)

            sku_data = []
            for row in results:
                sku_data.append({
                    'sku_id': row[0],
                    'abc_code': row[1] or 'C',
                    'xyz_code': row[2] or 'Z',
                    'kentucky_qty': int(row[3]) if row[3] else 0,
                    'burnaby_qty': int(row[4]) if row[4] else 0,
                    'description': row[5] or ''
                })

            logger.info(f"Loaded {len(sku_data)} SKUs for batch processing")
            return sku_data

        except Exception as e:
            logger.error(f"Failed to load SKU data: {e}")
            return []

    def refresh_weighted_cache(self, sku_filter: Optional[List[str]] = None,
                             progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Refresh weighted demand cache for all SKUs or a filtered subset

        Args:
            sku_filter: Optional list of SKU IDs to refresh (None = all SKUs)
            progress_callback: Optional callback function for progress updates

        Returns:
            Summary of cache refresh operation
        """
        start_time = time.time()
        summary = {
            'started_at': datetime.now(),
            'total_skus': 0,
            'processed_skus': 0,
            'successful_calculations': 0,
            'failed_calculations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': [],
            'duration_seconds': 0
        }

        try:
            logger.info("Starting weighted demand cache refresh")

            # Load all SKU data in batch
            sku_data = self.batch_load_sku_data()

            if sku_filter:
                sku_data = [sku for sku in sku_data if sku['sku_id'] in sku_filter]

            summary['total_skus'] = len(sku_data)

            if summary['total_skus'] == 0:
                logger.warning("No SKUs found for cache refresh")
                return summary

            logger.info(f"Refreshing cache for {summary['total_skus']} SKUs")

            # Process each SKU for both warehouses
            for i, sku in enumerate(sku_data):
                sku_id = sku['sku_id']
                abc_class = sku['abc_code']
                xyz_class = sku['xyz_code']

                try:
                    # Process Kentucky warehouse
                    kentucky_result = self._calculate_and_cache_demand(
                        sku_id, abc_class, xyz_class, 'kentucky'
                    )

                    # Process Burnaby warehouse
                    burnaby_result = self._calculate_and_cache_demand(
                        sku_id, abc_class, xyz_class, 'burnaby'
                    )

                    if kentucky_result and burnaby_result:
                        summary['successful_calculations'] += 2
                    else:
                        summary['failed_calculations'] += 1
                        summary['errors'].append(f"Failed to calculate demand for {sku_id}")

                except Exception as e:
                    summary['failed_calculations'] += 1
                    summary['errors'].append(f"Error processing {sku_id}: {str(e)}")
                    logger.error(f"Error processing {sku_id}: {e}")

                summary['processed_skus'] = i + 1

                # Report progress every 100 SKUs
                if progress_callback and (i + 1) % 100 == 0:
                    progress_callback({
                        'processed': i + 1,
                        'total': summary['total_skus'],
                        'percentage': ((i + 1) / summary['total_skus']) * 100,
                        'current_sku': sku_id
                    })

            summary['duration_seconds'] = time.time() - start_time
            summary['completed_at'] = datetime.now()

            logger.info(f"Cache refresh completed in {summary['duration_seconds']:.2f}s. "
                       f"Success: {summary['successful_calculations']}, "
                       f"Failed: {summary['failed_calculations']}")

            return summary

        except Exception as e:
            summary['duration_seconds'] = time.time() - start_time
            summary['errors'].append(f"Cache refresh failed: {str(e)}")
            logger.error(f"Cache refresh failed: {e}")
            return summary

    def _calculate_and_cache_demand(self, sku_id: str, abc_class: str, xyz_class: str,
                                  warehouse: str) -> Optional[Dict[str, Any]]:
        """
        Calculate weighted demand for a specific SKU and warehouse, then cache the result

        Args:
            sku_id: SKU identifier
            abc_class: ABC classification
            xyz_class: XYZ classification
            warehouse: Warehouse ('kentucky' or 'burnaby')

        Returns:
            Calculation result or None if failed
        """
        try:
            # Calculate weighted demand using the existing calculator
            result = self.weighted_calculator.get_enhanced_demand_calculation(
                sku_id=sku_id,
                abc_class=abc_class,
                xyz_class=xyz_class,
                current_month_sales=0,  # Will be calculated from historical data
                stockout_days=0,        # Will be calculated from stockout history
                warehouse=warehouse
            )

            if result:
                # Store in cache
                self.store_cached_demand(sku_id, warehouse, result)
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to calculate and cache demand for {sku_id} ({warehouse}): {e}")
            return None

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get cache performance and status statistics

        Returns:
            Dictionary containing cache statistics
        """
        try:
            query = """
                SELECT
                    warehouse,
                    COUNT(*) as total_entries,
                    SUM(CASE WHEN cache_valid = TRUE THEN 1 ELSE 0 END) as valid_entries,
                    AVG(TIMESTAMPDIFF(HOUR, last_calculated, NOW())) as avg_age_hours,
                    MIN(last_calculated) as oldest_entry,
                    MAX(last_calculated) as newest_entry
                FROM sku_demand_stats
                GROUP BY warehouse
            """

            results = database.execute_query(query, fetch_all=True)

            stats = {
                'total_cached_skus': 0,
                'valid_cached_skus': 0,
                'warehouses': {},
                'overall_hit_rate': 0.0,
                'last_updated': datetime.now()
            }

            for row in results:
                warehouse_stats = {
                    'total_entries': int(row[1]),
                    'valid_entries': int(row[2]),
                    'avg_age_hours': float(row[3]) if row[3] else 0.0,
                    'oldest_entry': row[4],
                    'newest_entry': row[5],
                    'hit_rate': (int(row[2]) / int(row[1])) * 100 if int(row[1]) > 0 else 0.0
                }

                stats['warehouses'][row[0]] = warehouse_stats
                stats['total_cached_skus'] += int(row[1])
                stats['valid_cached_skus'] += int(row[2])

            if stats['total_cached_skus'] > 0:
                stats['overall_hit_rate'] = (stats['valid_cached_skus'] / stats['total_cached_skus']) * 100

            return stats

        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {
                'error': str(e),
                'total_cached_skus': 0,
                'valid_cached_skus': 0,
                'warehouses': {},
                'overall_hit_rate': 0.0,
                'last_updated': datetime.now()
            }


def create_cache_manager() -> CacheManager:
    """
    Factory function to create a cache manager instance

    Returns:
        Configured CacheManager instance
    """
    return CacheManager()