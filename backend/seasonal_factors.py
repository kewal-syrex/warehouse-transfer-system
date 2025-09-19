"""
Seasonal Factor Calculator Module

Provides data-driven seasonal factor calculation and application for warehouse
transfer planning. Replaces fixed multipliers with historical sales analysis.

Key Features:
- Historical seasonal factor calculation from sales data
- Confidence-based factor application
- Category-level fallback for new SKUs
- Statistical validation of seasonal patterns
- Integration with weighted demand calculations

This module implements the core business logic for applying data-driven
seasonality to demand forecasts, following inventory management best practices.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

try:
    from . import database
    from .seasonal_analysis import SeasonalAnalyzer
except ImportError:
    import database
    from seasonal_analysis import SeasonalAnalyzer

logger = logging.getLogger(__name__)


class SeasonalFactorCalculator:
    """
    Calculates and applies data-driven seasonal factors to demand forecasts

    This class provides the core functionality for seasonal adjustment in the
    warehouse transfer planning system. It replaces arbitrary fixed multipliers
    with factors calculated from historical sales patterns.

    Attributes:
        min_confidence_threshold: Minimum confidence required to apply factors
        pattern_strength_threshold: Minimum pattern strength for reliable factors
        enable_category_fallback: Whether to use category averages for new SKUs
        cache_duration_hours: How long to cache seasonal factors
    """

    def __init__(self, min_confidence_threshold: float = 0.6,
                 pattern_strength_threshold: float = 0.3,
                 enable_category_fallback: bool = True,
                 cache_duration_hours: int = 24):
        """
        Initialize the Seasonal Factor Calculator

        Args:
            min_confidence_threshold: Minimum confidence to apply seasonal factors
            pattern_strength_threshold: Minimum pattern strength for reliability
            enable_category_fallback: Use category patterns for new SKUs
            cache_duration_hours: Cache duration for seasonal factors
        """
        self.min_confidence_threshold = min_confidence_threshold
        self.pattern_strength_threshold = pattern_strength_threshold
        self.enable_category_fallback = enable_category_fallback
        self.cache_duration_hours = cache_duration_hours

        # Load configuration from database
        self.config = self._load_seasonal_config()

        logger.info(f"SeasonalFactorCalculator initialized with confidence_threshold={min_confidence_threshold}, "
                   f"pattern_strength_threshold={pattern_strength_threshold}")

    def _load_seasonal_config(self) -> Dict:
        """
        Load seasonal configuration from database

        Returns:
            Dictionary containing seasonal configuration settings
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor(database.pymysql.cursors.DictCursor)

            query = """
            SELECT config_key, config_value, data_type
            FROM demand_calculation_config
            WHERE config_key LIKE 'seasonal_%'
            """

            cursor.execute(query)
            config_rows = cursor.fetchall()
            cursor.close()
            db.close()

            config = {}
            for row in config_rows:
                key = row['config_key']
                value = row['config_value']
                data_type = row['data_type']

                # Convert to appropriate type
                if data_type == 'boolean':
                    config[key] = value.lower() == 'true'
                elif data_type == 'integer':
                    config[key] = int(value)
                elif data_type == 'decimal':
                    config[key] = float(value)
                else:
                    config[key] = value

            # Set defaults if not found in database
            defaults = {
                'seasonal_adjustment_enabled': True,
                'seasonal_min_confidence': self.min_confidence_threshold,
                'seasonal_pattern_strength_threshold': self.pattern_strength_threshold,
                'seasonal_fallback_to_category': self.enable_category_fallback,
                'seasonal_analysis_years': 3
            }

            for key, default_value in defaults.items():
                if key not in config:
                    config[key] = default_value

            return config

        except Exception as e:
            logger.error(f"Failed to load seasonal configuration: {e}")
            return {
                'seasonal_adjustment_enabled': True,
                'seasonal_min_confidence': self.min_confidence_threshold,
                'seasonal_pattern_strength_threshold': self.pattern_strength_threshold,
                'seasonal_fallback_to_category': self.enable_category_fallback,
                'seasonal_analysis_years': 3
            }

    def get_seasonal_factor(self, sku_id: str, target_month: int = None,
                          warehouse: str = 'kentucky') -> Dict:
        """
        Get seasonal factor for a specific SKU and month

        Args:
            sku_id: SKU identifier
            target_month: Month to get factor for (1-12), defaults to current month
            warehouse: Warehouse to get factor for

        Returns:
            Dictionary containing seasonal factor and metadata
        """
        try:
            if target_month is None:
                target_month = datetime.now().month

            # Validate inputs
            if not (1 <= target_month <= 12):
                raise ValueError(f"Invalid month: {target_month}")

            if warehouse.lower() not in ['kentucky', 'burnaby']:
                logger.warning(f"Invalid warehouse '{warehouse}', defaulting to kentucky")
                warehouse = 'kentucky'

            # Check if seasonal adjustment is enabled
            if not self.config.get('seasonal_adjustment_enabled', True):
                return self._get_neutral_factor('disabled')

            # Try to get cached seasonal factor
            factor_data = self._get_cached_seasonal_factor(sku_id, target_month, warehouse)

            if factor_data:
                # Check if factor meets confidence requirements
                if self._is_factor_reliable(factor_data):
                    return factor_data
                else:
                    logger.debug(f"Cached factor for {sku_id} below confidence threshold")

            # If no reliable cached factor, try category fallback
            if self.config.get('seasonal_fallback_to_category', True):
                category_factor = self._get_category_seasonal_factor(sku_id, target_month, warehouse)
                if category_factor and self._is_factor_reliable(category_factor):
                    category_factor['source'] = 'category_fallback'
                    return category_factor

            # If all else fails, return neutral factor
            return self._get_neutral_factor('insufficient_data')

        except Exception as e:
            logger.error(f"Failed to get seasonal factor for {sku_id}: {e}")
            return self._get_neutral_factor('error')

    def _get_cached_seasonal_factor(self, sku_id: str, month: int,
                                  warehouse: str) -> Optional[Dict]:
        """
        Retrieve cached seasonal factor from database

        Args:
            sku_id: SKU identifier
            month: Month number (1-12)
            warehouse: Warehouse name

        Returns:
            Seasonal factor data if found and valid, None otherwise
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor(database.pymysql.cursors.DictCursor)

            query = """
            SELECT
                sf.seasonal_factor,
                sf.confidence_level,
                sf.data_points_used,
                sf.last_calculated,
                sps.pattern_type,
                sps.pattern_strength,
                sps.overall_confidence,
                sps.statistical_significance
            FROM seasonal_factors sf
            JOIN seasonal_patterns_summary sps ON sf.sku_id = sps.sku_id AND sf.warehouse = sps.warehouse
            WHERE sf.sku_id = %s
                AND sf.warehouse = %s
                AND sf.month_number = %s
                AND sf.last_calculated >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            """

            cursor.execute(query, (sku_id, warehouse, month, self.cache_duration_hours))
            result = cursor.fetchone()
            cursor.close()
            db.close()

            if not result:
                return None

            return {
                'seasonal_factor': float(result['seasonal_factor']),
                'confidence_level': float(result['confidence_level']),
                'data_points_used': result['data_points_used'],
                'pattern_type': result['pattern_type'],
                'pattern_strength': float(result['pattern_strength']),
                'overall_confidence': float(result['overall_confidence']),
                'statistical_significance': bool(result['statistical_significance']),
                'last_calculated': result['last_calculated'],
                'source': 'cached',
                'sku_id': sku_id,
                'warehouse': warehouse,
                'month': month
            }

        except Exception as e:
            logger.error(f"Failed to retrieve cached seasonal factor: {e}")
            return None

    def _get_category_seasonal_factor(self, sku_id: str, month: int,
                                    warehouse: str) -> Optional[Dict]:
        """
        Get category-level seasonal factor as fallback

        Args:
            sku_id: SKU identifier
            month: Month number
            warehouse: Warehouse name

        Returns:
            Category-level seasonal factor if available
        """
        try:
            # Get SKU category
            db = database.get_database_connection()
            cursor = db.cursor(database.pymysql.cursors.DictCursor)

            # Get SKU category
            cursor.execute("SELECT category FROM skus WHERE sku_id = %s", (sku_id,))
            sku_result = cursor.fetchone()

            if not sku_result or not sku_result['category']:
                cursor.close()
                db.close()
                return None

            category = sku_result['category']

            # Get average seasonal factor for category
            query = """
            SELECT
                AVG(sf.seasonal_factor) as avg_seasonal_factor,
                AVG(sf.confidence_level) as avg_confidence,
                COUNT(*) as sku_count,
                AVG(sps.pattern_strength) as avg_pattern_strength
            FROM seasonal_factors sf
            JOIN seasonal_patterns_summary sps ON sf.sku_id = sps.sku_id AND sf.warehouse = sps.warehouse
            JOIN skus s ON sf.sku_id = s.sku_id
            WHERE s.category = %s
                AND sf.warehouse = %s
                AND sf.month_number = %s
                AND sf.confidence_level >= %s
                AND sps.pattern_strength >= %s
                AND sf.last_calculated >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            """

            cursor.execute(query, (
                category, warehouse, month,
                self.config.get('seasonal_min_confidence', 0.6),
                self.config.get('seasonal_pattern_strength_threshold', 0.3),
                self.cache_duration_hours
            ))

            result = cursor.fetchone()
            cursor.close()
            db.close()

            if not result or result['sku_count'] < 3:  # Need at least 3 SKUs for reliable average
                return None

            return {
                'seasonal_factor': float(result['avg_seasonal_factor']),
                'confidence_level': float(result['avg_confidence']),
                'data_points_used': result['sku_count'],
                'pattern_type': 'category_average',
                'pattern_strength': float(result['avg_pattern_strength']),
                'overall_confidence': float(result['avg_confidence']),
                'statistical_significance': True,  # Assume significant for category averages
                'source': 'category',
                'category': category,
                'sku_id': sku_id,
                'warehouse': warehouse,
                'month': month
            }

        except Exception as e:
            logger.error(f"Failed to get category seasonal factor: {e}")
            return None

    def _is_factor_reliable(self, factor_data: Dict) -> bool:
        """
        Check if seasonal factor meets reliability thresholds

        Args:
            factor_data: Seasonal factor data dictionary

        Returns:
            True if factor is reliable enough to use
        """
        min_confidence = self.config.get('seasonal_min_confidence', 0.6)
        min_pattern_strength = self.config.get('seasonal_pattern_strength_threshold', 0.3)

        confidence_ok = factor_data.get('confidence_level', 0) >= min_confidence
        pattern_ok = factor_data.get('pattern_strength', 0) >= min_pattern_strength
        has_data = factor_data.get('data_points_used', 0) >= 2

        return confidence_ok and pattern_ok and has_data

    def _get_neutral_factor(self, reason: str) -> Dict:
        """
        Return neutral seasonal factor (1.0) with metadata

        Args:
            reason: Reason for using neutral factor

        Returns:
            Neutral factor data
        """
        return {
            'seasonal_factor': 1.0,
            'confidence_level': 0.0,
            'data_points_used': 0,
            'pattern_type': 'none',
            'pattern_strength': 0.0,
            'overall_confidence': 0.0,
            'statistical_significance': False,
            'source': 'neutral',
            'reason': reason,
            'month': datetime.now().month
        }

    def apply_seasonal_adjustment(self, base_demand: float, sku_id: str,
                                target_month: int = None, warehouse: str = 'kentucky') -> Dict:
        """
        Apply seasonal adjustment to base demand

        Args:
            base_demand: Base demand to adjust
            sku_id: SKU identifier
            target_month: Month to adjust for (defaults to current month)
            warehouse: Warehouse for calculation

        Returns:
            Dictionary with adjusted demand and adjustment details
        """
        try:
            if target_month is None:
                target_month = datetime.now().month

            # Get seasonal factor
            factor_data = self.get_seasonal_factor(sku_id, target_month, warehouse)
            seasonal_factor = factor_data['seasonal_factor']

            # Apply adjustment
            adjusted_demand = base_demand * seasonal_factor

            # Calculate adjustment details
            adjustment_amount = adjusted_demand - base_demand
            adjustment_percentage = ((seasonal_factor - 1.0) * 100) if seasonal_factor != 1.0 else 0.0

            result = {
                'base_demand': round(base_demand, 2),
                'seasonal_factor': seasonal_factor,
                'adjusted_demand': round(adjusted_demand, 2),
                'adjustment_amount': round(adjustment_amount, 2),
                'adjustment_percentage': round(adjustment_percentage, 1),
                'factor_metadata': factor_data,
                'sku_id': sku_id,
                'target_month': target_month,
                'target_month_name': datetime(2024, target_month, 1).strftime('%B'),
                'warehouse': warehouse,
                'calculation_timestamp': datetime.now().isoformat()
            }

            # Log significant adjustments
            if abs(adjustment_percentage) > 10:
                logger.info(f"Significant seasonal adjustment for {sku_id}: "
                           f"{base_demand:.1f} -> {adjusted_demand:.1f} "
                           f"({adjustment_percentage:+.1f}%) using {factor_data['source']} factor")

            return result

        except Exception as e:
            logger.error(f"Failed to apply seasonal adjustment for {sku_id}: {e}")
            return {
                'base_demand': base_demand,
                'seasonal_factor': 1.0,
                'adjusted_demand': base_demand,
                'adjustment_amount': 0.0,
                'adjustment_percentage': 0.0,
                'factor_metadata': self._get_neutral_factor('error'),
                'error': str(e)
            }

    def update_seasonal_factors_for_sku(self, sku_id: str, warehouse: str = 'kentucky',
                                      years_back: int = 3, force_update: bool = False) -> Dict:
        """
        Update seasonal factors for a specific SKU using historical analysis

        Args:
            sku_id: SKU identifier
            warehouse: Warehouse to analyze
            years_back: Years of historical data to analyze
            force_update: Force update even if recent data exists

        Returns:
            Dictionary with update results
        """
        try:
            logger.info(f"Updating seasonal factors for {sku_id} ({warehouse})")

            # Check if recent analysis exists (unless forcing update)
            if not force_update and self._has_recent_analysis(sku_id, warehouse):
                logger.debug(f"Recent analysis exists for {sku_id}, skipping update")
                return {
                    'status': 'skipped',
                    'reason': 'recent_analysis_exists',
                    'sku_id': sku_id,
                    'warehouse': warehouse
                }

            # Perform seasonal analysis
            analyzer = SeasonalAnalyzer()
            analysis_result = analyzer.analyze_sku_seasonality(sku_id, years_back, warehouse)

            if 'error' in analysis_result:
                logger.warning(f"Seasonal analysis failed for {sku_id}: {analysis_result['error']}")
                return {
                    'status': 'failed',
                    'error': analysis_result['error'],
                    'sku_id': sku_id,
                    'warehouse': warehouse
                }

            # Store results in database
            storage_result = self._store_seasonal_analysis(analysis_result)

            if storage_result['success']:
                logger.info(f"Successfully updated seasonal factors for {sku_id}")
                return {
                    'status': 'success',
                    'pattern_type': analysis_result['pattern_type'],
                    'pattern_strength': analysis_result['pattern_strength'],
                    'statistical_significance': analysis_result['statistical_significance']['is_significant'],
                    'factors_stored': storage_result['factors_stored'],
                    'sku_id': sku_id,
                    'warehouse': warehouse
                }
            else:
                return {
                    'status': 'storage_failed',
                    'error': storage_result['error'],
                    'sku_id': sku_id,
                    'warehouse': warehouse
                }

        except Exception as e:
            logger.error(f"Failed to update seasonal factors for {sku_id}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'sku_id': sku_id,
                'warehouse': warehouse
            }

    def _has_recent_analysis(self, sku_id: str, warehouse: str) -> bool:
        """
        Check if SKU has recent seasonal analysis

        Args:
            sku_id: SKU identifier
            warehouse: Warehouse name

        Returns:
            True if recent analysis exists
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor()

            query = """
            SELECT COUNT(*) as count
            FROM seasonal_patterns_summary
            WHERE sku_id = %s
                AND warehouse = %s
                AND last_analyzed >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            """

            cursor.execute(query, (sku_id, warehouse, self.cache_duration_hours))
            result = cursor.fetchone()
            cursor.close()
            db.close()

            return result[0] > 0

        except Exception as e:
            logger.error(f"Failed to check recent analysis: {e}")
            return False

    def _store_seasonal_analysis(self, analysis_result: Dict) -> Dict:
        """
        Store seasonal analysis results in database

        Args:
            analysis_result: Results from seasonal analysis

        Returns:
            Dictionary with storage status
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor()

            sku_id = analysis_result['sku_id']
            warehouse = analysis_result['warehouse']

            # Store pattern summary
            summary_query = """
            INSERT INTO seasonal_patterns_summary (
                sku_id, warehouse, pattern_type, pattern_strength, overall_confidence,
                statistical_significance, f_statistic, p_value, years_analyzed,
                months_of_data, date_range_start, date_range_end, yearly_average,
                peak_months, low_months
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pattern_type = VALUES(pattern_type),
                pattern_strength = VALUES(pattern_strength),
                overall_confidence = VALUES(overall_confidence),
                statistical_significance = VALUES(statistical_significance),
                f_statistic = VALUES(f_statistic),
                p_value = VALUES(p_value),
                years_analyzed = VALUES(years_analyzed),
                months_of_data = VALUES(months_of_data),
                date_range_start = VALUES(date_range_start),
                date_range_end = VALUES(date_range_end),
                yearly_average = VALUES(yearly_average),
                peak_months = VALUES(peak_months),
                low_months = VALUES(low_months)
            """

            # Extract peak and low months
            seasonal_factors = analysis_result['seasonal_factors']
            sorted_months = sorted(seasonal_factors.items(), key=lambda x: x[1])
            low_months = ','.join([str(month) for month, _ in sorted_months[:3]])
            peak_months = ','.join([str(month) for month, _ in sorted_months[-3:]])

            # Get statistical data
            stats = analysis_result.get('statistical_significance', {})

            summary_values = (
                sku_id, warehouse,
                analysis_result['pattern_type'],
                analysis_result['pattern_strength'],
                stats.get('confidence_level', 0),
                stats.get('is_significant', False),
                stats.get('f_statistic'),
                stats.get('p_value'),
                analysis_result.get('years_analyzed', 3),
                analysis_result['data_months'],
                analysis_result.get('date_range', {}).get('start'),
                analysis_result.get('date_range', {}).get('end'),
                analysis_result['yearly_average'],
                peak_months,
                low_months
            )

            cursor.execute(summary_query, summary_values)

            # Store monthly factors
            factors_stored = 0
            for month, factor in analysis_result['seasonal_factors'].items():
                confidence = analysis_result['factor_confidence'].get(month, 0)

                factor_query = """
                INSERT INTO seasonal_factors (
                    sku_id, warehouse, month_number, seasonal_factor,
                    confidence_level, data_points_used, pattern_type, pattern_strength
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    seasonal_factor = VALUES(seasonal_factor),
                    confidence_level = VALUES(confidence_level),
                    data_points_used = VALUES(data_points_used),
                    pattern_type = VALUES(pattern_type),
                    pattern_strength = VALUES(pattern_strength)
                """

                factor_values = (
                    sku_id, warehouse, month, factor, confidence,
                    analysis_result['data_months'],
                    analysis_result['pattern_type'],
                    analysis_result['pattern_strength']
                )

                cursor.execute(factor_query, factor_values)
                factors_stored += 1

            db.commit()
            cursor.close()
            db.close()

            return {
                'success': True,
                'factors_stored': factors_stored,
                'summary_updated': True
            }

        except Exception as e:
            logger.error(f"Failed to store seasonal analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def bulk_update_seasonal_factors(self, limit: int = None) -> Dict:
        """
        Update seasonal factors for all active SKUs

        Args:
            limit: Maximum number of SKUs to process

        Returns:
            Dictionary with bulk update results
        """
        try:
            logger.info("Starting bulk seasonal factors update")

            # Get active SKUs with seasonal patterns
            query = """
            SELECT sku_id, seasonal_pattern, category
            FROM skus
            WHERE status = 'Active'
                AND (seasonal_pattern != 'unknown' OR seasonal_pattern IS NULL)
            ORDER BY abc_code, sku_id
            """

            if limit:
                query += f" LIMIT {limit}"

            db = database.get_database_connection()
            cursor = db.cursor(database.pymysql.cursors.DictCursor)
            cursor.execute(query)
            sku_list = cursor.fetchall()
            cursor.close()
            db.close()

            logger.info(f"Found {len(sku_list)} SKUs to analyze")

            results = {
                'total_skus': len(sku_list),
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'errors': []
            }

            for sku_record in sku_list:
                try:
                    sku_id = sku_record['sku_id']

                    # Update for both warehouses
                    for warehouse in ['kentucky', 'burnaby']:
                        update_result = self.update_seasonal_factors_for_sku(
                            sku_id, warehouse, force_update=False
                        )

                        if update_result['status'] == 'success':
                            results['successful'] += 1
                        elif update_result['status'] == 'skipped':
                            results['skipped'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append({
                                'sku_id': sku_id,
                                'warehouse': warehouse,
                                'error': update_result.get('error', 'Unknown error')
                            })

                    results['processed'] += 1

                    # Progress logging
                    if results['processed'] % 50 == 0:
                        logger.info(f"Processed {results['processed']}/{len(sku_list)} SKUs")

                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'sku_id': sku_record.get('sku_id', 'unknown'),
                        'error': str(e)
                    })

            logger.info(f"Bulk update completed: {results}")
            return results

        except Exception as e:
            logger.error(f"Bulk seasonal factors update failed: {e}")
            return {
                'total_skus': 0,
                'processed': 0,
                'successful': 0,
                'failed': 1,
                'skipped': 0,
                'errors': [{'error': str(e)}]
            }


def test_seasonal_factor_calculator():
    """
    Test function for SeasonalFactorCalculator
    """
    try:
        logger.info("Testing SeasonalFactorCalculator...")

        calculator = SeasonalFactorCalculator()

        # Test with known seasonal SKU
        test_sku = 'UB-YTX14-BS'  # Motorcycle battery (should be seasonal)

        # Test getting seasonal factor
        factor_result = calculator.get_seasonal_factor(test_sku)
        logger.info(f"Seasonal factor for {test_sku}: {factor_result}")

        # Test applying seasonal adjustment
        base_demand = 100.0
        adjustment_result = calculator.apply_seasonal_adjustment(base_demand, test_sku)
        logger.info(f"Seasonal adjustment for {test_sku}: {adjustment_result}")

        # Test updating factors
        update_result = calculator.update_seasonal_factors_for_sku(test_sku, force_update=True)
        logger.info(f"Update result for {test_sku}: {update_result}")

        logger.info("SeasonalFactorCalculator tests completed successfully")
        return True

    except Exception as e:
        logger.error(f"SeasonalFactorCalculator test failed: {e}")
        return False


if __name__ == "__main__":
    # Set up logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run tests
    test_seasonal_factor_calculator()