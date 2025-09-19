"""
Weighted Demand Calculator Module

Advanced demand calculation using weighted moving averages and volatility analysis.
Reduces single-month bias by using historical data patterns for more stable predictions.

Features:
- Weighted 3-month and 6-month moving averages
- Demand volatility analysis using coefficient of variation
- ABC-XYZ specific calculation strategies
- Statistical safety stock calculations
- Forecast accuracy tracking integration

This module addresses the key limitation of relying solely on the latest month's sales
by incorporating historical trends while maintaining responsiveness to recent changes.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from scipy.stats import norm

try:
    from . import database
    from .seasonal_factors import SeasonalFactorCalculator
except ImportError:
    import database
    from seasonal_factors import SeasonalFactorCalculator

logger = logging.getLogger(__name__)


class WeightedDemandCalculator:
    """
    Advanced demand calculation using weighted moving averages and volatility analysis
    """

    def __init__(self):
        """Initialize the weighted demand calculator with configuration from database"""
        self.config = self._load_configuration()
        self.safety_stock_calculator = SafetyStockCalculator(self.config)
        self.seasonal_calculator = SeasonalFactorCalculator()

    def _load_configuration(self) -> dict:
        """
        Load configuration settings from the demand_calculation_config table

        Returns:
            Dictionary containing configuration values with defaults as fallback
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor(database.pymysql.cursors.DictCursor)

            cursor.execute("SELECT config_key, config_value, data_type FROM demand_calculation_config")
            config_rows = cursor.fetchall()

            cursor.close()
            db.close()

            # Convert database config to typed dictionary
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

            return config

        except Exception as e:
            logger.error(f"Failed to load demand calculation configuration: {e}")
            # Return safe defaults if database config fails
            return {
                'weighted_3mo_weights': '0.5,0.3,0.2',
                'weighted_6mo_enabled': True,
                'min_months_for_weighted': 3,
                'cv_low_threshold': 0.25,
                'cv_high_threshold': 0.75,
                'ax_use_6mo_average': True,
                'cz_use_single_month': False,
                'volatility_adjustment_factor': 1.2
            }

    def correct_monthly_demand(self, monthly_sales: int, stockout_days: int, days_in_month: int = 30) -> float:
        """
        Calculate stockout-corrected demand using the simplified monthly approach

        Inline implementation to avoid circular imports with calculations.py

        Args:
            monthly_sales: Actual units sold in the month
            stockout_days: Number of days out of stock in the month
            days_in_month: Total days in the month (default 30)

        Returns:
            Corrected demand accounting for stockout periods
        """
        if stockout_days == 0 or monthly_sales == 0:
            return float(monthly_sales)

        # Calculate availability rate
        availability_rate = (days_in_month - stockout_days) / days_in_month

        if availability_rate < 1.0:
            # Apply correction with 30% floor to prevent overcorrection
            correction_factor = max(availability_rate, 0.3)
            corrected_demand = monthly_sales / correction_factor

            # Cap at 50% increase for very low availability (safeguard)
            if availability_rate < 0.3:
                corrected_demand = min(corrected_demand, monthly_sales * 1.5)

            return corrected_demand

        return float(monthly_sales)

    def get_weighted_3month_average(self, sku_id: str, warehouse: str = 'kentucky') -> dict:
        """
        Calculate 3-month weighted average demand with configurable weights for specific warehouse

        Default weights: [0.5, 0.3, 0.2] (most recent month gets highest weight)
        This approach reduces noise while maintaining responsiveness to recent trends.
        Warehouse-specific calculations ensure accurate demand forecasting per location.

        Args:
            sku_id: SKU identifier to calculate average for
            warehouse: Warehouse to calculate demand for ('kentucky' or 'burnaby')

        Returns:
            Dictionary containing:
            - weighted_average: Calculated weighted average demand for specified warehouse
            - sample_months: Number of months used in calculation
            - data_quality: Quality score (0-1) based on data completeness
            - calculation_method: Method used for transparency
            - warehouse: Warehouse this calculation applies to

        Example:
            >>> calculator.get_weighted_3month_average('CHG-001', 'burnaby')
            {
                'weighted_average': 145.6,
                'sample_months': 3,
                'data_quality': 1.0,
                'calculation_method': 'weighted_3mo_standard',
                'warehouse': 'burnaby'
            }
        """
        try:
            # Validate warehouse parameter
            if warehouse.lower() not in ['kentucky', 'burnaby']:
                logger.warning(f"Invalid warehouse '{warehouse}' for SKU {sku_id}, defaulting to kentucky")
                warehouse = 'kentucky'

            # Parse weights from configuration
            weights_str = self.config.get('weighted_3mo_weights', '0.5,0.3,0.2')
            weights = [float(w.strip()) for w in weights_str.split(',')]

            # Dynamic column mapping based on warehouse
            warehouse = warehouse.lower()
            if warehouse == 'burnaby':
                demand_col = 'corrected_demand_burnaby'
                sales_col = 'burnaby_sales'
                stockout_col = 'burnaby_stockout_days'
            else:  # kentucky (default)
                demand_col = 'corrected_demand_kentucky'
                sales_col = 'kentucky_sales'
                stockout_col = 'kentucky_stockout_days'

            # Get last 3 months of warehouse-specific corrected demand data
            query = f"""
            SELECT
                {demand_col} as corrected_demand,
                {sales_col} as sales,
                {stockout_col} as stockout_days,
                `year_month`
            FROM monthly_sales
            WHERE sku_id = %s
            ORDER BY `year_month` DESC
            LIMIT 3
            """

            sales_data = database.execute_query(query, (sku_id,))

            if not sales_data:
                return {
                    'weighted_average': 0.0,
                    'sample_months': 0,
                    'data_quality': 0.0,
                    'calculation_method': 'no_data',
                    'warehouse': warehouse
                }

            # Calculate weighted average using corrected demand where available
            weighted_sum = 0.0
            weight_sum = 0.0
            valid_months = 0

            for i, month_data in enumerate(sales_data):
                if i >= len(weights):
                    break

                # Use corrected demand if available, otherwise raw sales (convert Decimal to float)
                # Now using warehouse-agnostic column aliases
                demand = month_data['corrected_demand'] or month_data['sales'] or 0
                demand = float(demand) if demand is not None else 0.0

                if demand >= 0:  # Include zero demand (valid data point)
                    weighted_sum += demand * weights[i]
                    weight_sum += weights[i]
                    valid_months += 1

            # Calculate final weighted average
            weighted_average = weighted_sum / weight_sum if weight_sum > 0 else 0.0

            # Calculate data quality score
            data_quality = min(1.0, valid_months / 3.0)  # Perfect score for 3 months of data

            # Determine calculation method
            if valid_months >= 3:
                method = 'weighted_3mo_standard'
            elif valid_months >= 2:
                method = 'weighted_3mo_partial'
            else:
                method = 'weighted_3mo_insufficient_data'

            return {
                'weighted_average': round(weighted_average, 2),
                'sample_months': valid_months,
                'data_quality': round(data_quality, 2),
                'calculation_method': method,
                'warehouse': warehouse
            }

        except Exception as e:
            logger.error(f"Failed to calculate 3-month weighted average for {sku_id} ({warehouse}): {e}")
            return {
                'weighted_average': 0.0,
                'sample_months': 0,
                'data_quality': 0.0,
                'calculation_method': 'calculation_error',
                'warehouse': warehouse
            }

    def get_weighted_6month_average(self, sku_id: str, warehouse: str = 'kentucky') -> dict:
        """
        Calculate 6-month exponentially weighted moving average for stable SKUs

        Uses exponential decay to give more weight to recent months while incorporating
        longer-term trends. Particularly effective for Class A and stable (X) SKUs.
        Supports warehouse-specific calculations for accurate demand forecasting.

        Args:
            sku_id: SKU identifier to calculate average for
            warehouse: Warehouse to calculate demand for ('kentucky' or 'burnaby')

        Returns:
            Dictionary with weighted average and calculation metadata including warehouse info
        """
        try:
            # Validate warehouse parameter
            if warehouse.lower() not in ['kentucky', 'burnaby']:
                logger.warning(f"Invalid warehouse '{warehouse}' for SKU {sku_id}, defaulting to kentucky")
                warehouse = 'kentucky'

            # Check if 6-month averaging is enabled
            if not self.config.get('weighted_6mo_enabled', True):
                return self.get_weighted_3month_average(sku_id, warehouse)

            # Dynamic column mapping based on warehouse
            warehouse = warehouse.lower()
            if warehouse == 'burnaby':
                demand_col = 'corrected_demand_burnaby'
                sales_col = 'burnaby_sales'
                stockout_col = 'burnaby_stockout_days'
            else:  # kentucky (default)
                demand_col = 'corrected_demand_kentucky'
                sales_col = 'kentucky_sales'
                stockout_col = 'kentucky_stockout_days'

            # Get last 6 months of warehouse-specific data
            query = f"""
            SELECT
                {demand_col} as corrected_demand,
                {sales_col} as sales,
                `year_month`,
                {stockout_col} as stockout_days
            FROM monthly_sales
            WHERE sku_id = %s
            ORDER BY `year_month` DESC
            LIMIT 6
            """

            sales_data = database.execute_query(query, (sku_id,))

            if len(sales_data) < 3:  # Need at least 3 months for 6-month calc
                return self.get_weighted_3month_average(sku_id, warehouse)

            # Exponential decay weights (alpha = 0.3 for 6-month smoothing)
            alpha = 0.3
            weights = [alpha * (1 - alpha) ** i for i in range(6)]

            # Normalize weights to sum to 1.0
            weight_sum = sum(weights)
            weights = [w / weight_sum for w in weights]

            # Calculate exponentially weighted average
            weighted_sum = 0.0
            valid_months = 0

            for i, month_data in enumerate(sales_data):
                # Use warehouse-agnostic column aliases
                demand = month_data['corrected_demand'] or month_data['sales'] or 0
                demand = float(demand) if demand is not None else 0.0

                if demand >= 0:
                    weighted_sum += demand * weights[i]
                    valid_months += 1

            # Data quality based on completeness
            data_quality = min(1.0, valid_months / 6.0)

            return {
                'weighted_average': round(weighted_sum, 2),
                'sample_months': valid_months,
                'data_quality': round(data_quality, 2),
                'calculation_method': 'exponential_6mo',
                'warehouse': warehouse
            }

        except Exception as e:
            logger.error(f"Failed to calculate 6-month weighted average for {sku_id} ({warehouse}): {e}")
            return self.get_weighted_3month_average(sku_id, warehouse)  # Fallback to 3-month

    def calculate_demand_volatility(self, sku_id: str, warehouse: str = 'kentucky') -> dict:
        """
        Calculate demand volatility using coefficient of variation (CV) for specific warehouse

        Volatility Classification:
        - Low (CV < 0.25): Stable, predictable demand
        - Medium (0.25 ≤ CV ≤ 0.75): Moderate variability
        - High (CV > 0.75): Highly variable, unpredictable demand

        Args:
            sku_id: SKU identifier to analyze
            warehouse: Warehouse to calculate volatility for ('kentucky' or 'burnaby')

        Returns:
            Dictionary containing volatility metrics and classification with warehouse info
        """
        try:
            # Validate warehouse parameter
            if warehouse.lower() not in ['kentucky', 'burnaby']:
                logger.warning(f"Invalid warehouse '{warehouse}' for SKU {sku_id}, defaulting to kentucky")
                warehouse = 'kentucky'

            # Dynamic column mapping based on warehouse
            warehouse = warehouse.lower()
            if warehouse == 'burnaby':
                demand_col = 'corrected_demand_burnaby'
                sales_col = 'burnaby_sales'
            else:  # kentucky (default)
                demand_col = 'corrected_demand_kentucky'
                sales_col = 'kentucky_sales'

            # Get 12 months of warehouse-specific demand data for volatility calculation
            query = f"""
            SELECT
                {demand_col} as corrected_demand,
                {sales_col} as sales,
                `year_month`
            FROM monthly_sales
            WHERE sku_id = %s
            ORDER BY `year_month` DESC
            LIMIT 12
            """

            sales_data = database.execute_query(query, (sku_id,))

            if len(sales_data) < 3:
                return {
                    'standard_deviation': 0.0,
                    'coefficient_variation': 0.0,
                    'volatility_class': 'insufficient_data',
                    'sample_size': len(sales_data),
                    'mean_demand': 0.0,
                    'warehouse': warehouse
                }

            # Extract demand values (convert Decimal to float)
            demands = []
            for month_data in sales_data:
                # Use warehouse-agnostic column aliases
                demand = month_data['corrected_demand'] or month_data['sales'] or 0
                demands.append(float(demand) if demand is not None else 0.0)

            # Calculate statistical measures
            mean_demand = np.mean(demands)
            std_deviation = np.std(demands, ddof=1)  # Sample standard deviation

            # Calculate coefficient of variation
            cv = std_deviation / mean_demand if mean_demand > 0 else 0.0

            # Classify volatility
            cv_low_thresh = self.config.get('cv_low_threshold', 0.25)
            cv_high_thresh = self.config.get('cv_high_threshold', 0.75)

            if cv < cv_low_thresh:
                volatility_class = 'low'
            elif cv > cv_high_thresh:
                volatility_class = 'high'
            else:
                volatility_class = 'medium'

            return {
                'standard_deviation': round(std_deviation, 2),
                'coefficient_variation': round(cv, 3),
                'volatility_class': volatility_class,
                'sample_size': len(demands),
                'mean_demand': round(mean_demand, 2),
                'warehouse': warehouse
            }

        except Exception as e:
            logger.error(f"Failed to calculate demand volatility for {sku_id} ({warehouse}): {e}")
            return {
                'standard_deviation': 0.0,
                'coefficient_variation': 0.0,
                'volatility_class': 'calculation_error',
                'sample_size': 0,
                'mean_demand': 0.0,
                'warehouse': warehouse
            }

    def get_enhanced_demand_calculation(self, sku_id: str, abc_class: str, xyz_class: str,
                                      current_month_sales: int = 0, stockout_days: int = 0,
                                      warehouse: str = 'kentucky') -> dict:
        """
        Calculate enhanced demand using weighted averages, volatility analysis, and ABC-XYZ strategy

        This is the main method that replaces single-month demand calculations with
        sophisticated weighted averages tailored to each SKU's characteristics and warehouse.

        Strategy by Classification:
        - AX (High value, stable): 6-month weighted average for maximum stability
        - CZ (Low value, volatile): 3-month weighted with higher safety margins
        - Others: Balanced approach based on volatility and data quality

        Args:
            sku_id: SKU identifier
            abc_class: ABC classification (A, B, C)
            xyz_class: XYZ classification (X, Y, Z)
            current_month_sales: Latest month sales (fallback if needed)
            stockout_days: Stockout days for correction factor
            warehouse: Warehouse to calculate demand for ('kentucky' or 'burnaby')

        Returns:
            Dictionary with enhanced demand calculation and supporting metrics including warehouse info
        """
        try:
            # Get volatility analysis first for the specified warehouse
            volatility_metrics = self.calculate_demand_volatility(sku_id, warehouse)
            volatility_class = volatility_metrics['volatility_class']
            cv = volatility_metrics['coefficient_variation']

            # Determine calculation strategy based on ABC-XYZ and volatility
            use_6mo_average = False

            # Strategy selection logic
            if abc_class == 'A' and xyz_class == 'X':
                # High value, stable - use 6-month for maximum stability
                use_6mo_average = self.config.get('ax_use_6mo_average', True)
            elif abc_class == 'C' and xyz_class == 'Z':
                # Low value, volatile - use single month or 3-month depending on config
                use_6mo_average = not self.config.get('cz_use_single_month', False)
            elif volatility_class == 'low':
                # Stable items benefit from longer averages
                use_6mo_average = True
            else:
                # Medium volatility items use 3-month weighted average
                use_6mo_average = False

            # Get appropriate weighted average for the specified warehouse
            if use_6mo_average:
                avg_result = self.get_weighted_6month_average(sku_id, warehouse)
                primary_method = '6mo_weighted'
            else:
                avg_result = self.get_weighted_3month_average(sku_id, warehouse)
                primary_method = '3mo_weighted'

            weighted_demand = avg_result['weighted_average']
            data_quality = avg_result['data_quality']
            sample_months = avg_result['sample_months']

            # Apply stockout correction to the weighted average
            corrected_weighted_demand = self.correct_monthly_demand(
                weighted_demand, stockout_days, 30
            )

            # Apply data-driven seasonal adjustment
            seasonal_adjustment_result = self.seasonal_calculator.apply_seasonal_adjustment(
                corrected_weighted_demand, sku_id, warehouse=warehouse
            )
            seasonally_adjusted_demand = seasonal_adjustment_result['adjusted_demand']

            # Apply volatility-based adjustment for safety
            volatility_adjustment = 1.0
            if volatility_class == 'high':
                volatility_adjustment = self.config.get('volatility_adjustment_factor', 1.2)
            elif volatility_class == 'low' and data_quality > 0.8:
                volatility_adjustment = 1.0  # No reduction for stable items to avoid underestimation

            final_demand = seasonally_adjusted_demand * volatility_adjustment

            # Fallback to current month if data quality is poor
            if data_quality < 0.5 or sample_months < 2:
                logger.info(f"Using fallback single-month calculation for {sku_id} (quality: {data_quality})")
                fallback_demand = self.correct_monthly_demand(
                    current_month_sales, stockout_days, 30
                )
                final_demand = max(final_demand, fallback_demand)
                calculation_method = f"{primary_method}_with_fallback"
            else:
                calculation_method = f"{primary_method}_enhanced"

            # Prepare comprehensive result
            result = {
                'enhanced_demand': round(final_demand, 2),
                'weighted_average_base': round(weighted_demand, 2),
                'stockout_corrected': round(corrected_weighted_demand, 2),
                'seasonally_adjusted': round(seasonally_adjusted_demand, 2),
                'volatility_adjustment': round(volatility_adjustment, 3),

                # Seasonal adjustment details
                'seasonal_factor': seasonal_adjustment_result['seasonal_factor'],
                'seasonal_adjustment_percentage': seasonal_adjustment_result['adjustment_percentage'],
                'seasonal_factor_source': seasonal_adjustment_result['factor_metadata']['source'],
                'seasonal_pattern_type': seasonal_adjustment_result['factor_metadata']['pattern_type'],

                # Calculation metadata
                'calculation_method': calculation_method,
                'primary_method': primary_method,
                'sample_months': sample_months,
                'data_quality_score': data_quality,

                # Volatility metrics
                'volatility_class': volatility_class,
                'coefficient_variation': cv,
                'standard_deviation': volatility_metrics['standard_deviation'],

                # Strategy context
                'abc_class': abc_class,
                'xyz_class': xyz_class,
                'strategy_reason': self._get_strategy_reason(abc_class, xyz_class, volatility_class, use_6mo_average),
                'warehouse': warehouse
            }

            # Store/update demand statistics in database
            self._store_demand_statistics(sku_id, result, volatility_metrics)

            return result

        except Exception as e:
            logger.error(f"Enhanced demand calculation failed for {sku_id} ({warehouse}): {e}")
            # Fallback to corrected current month
            fallback_demand = self.correct_monthly_demand(current_month_sales, stockout_days, 30)
            return {
                'enhanced_demand': fallback_demand,
                'calculation_method': 'error_fallback',
                'error': str(e),
                'warehouse': warehouse
            }

    def _get_strategy_reason(self, abc_class: str, xyz_class: str, volatility_class: str, use_6mo: bool) -> str:
        """Generate human-readable explanation for calculation strategy chosen"""
        if abc_class == 'A' and xyz_class == 'X':
            return f"High-value stable item using {'6-month' if use_6mo else '3-month'} weighted average"
        elif abc_class == 'C' and xyz_class == 'Z':
            return f"Low-value volatile item using {'6-month' if use_6mo else '3-month'} approach"
        elif volatility_class == 'low':
            return "Stable demand pattern - using longer average for precision"
        elif volatility_class == 'high':
            return "High volatility - using shorter average with safety adjustment"
        else:
            return f"Balanced approach for {abc_class}-{xyz_class} classification"

    def _store_demand_statistics(self, sku_id: str, calculation_result: dict, volatility_metrics: dict):
        """
        Store calculated demand statistics in the sku_demand_stats table

        This enables tracking of calculation quality and provides data for the UI
        """
        try:
            # Prepare data for storage
            insert_query = """
            INSERT INTO sku_demand_stats (
                sku_id, demand_3mo_weighted, demand_6mo_weighted,
                demand_std_dev, coefficient_variation, volatility_class,
                sample_size_months, data_quality_score, calculation_method,
                last_calculated
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON DUPLICATE KEY UPDATE
                demand_3mo_weighted = VALUES(demand_3mo_weighted),
                demand_6mo_weighted = VALUES(demand_6mo_weighted),
                demand_std_dev = VALUES(demand_std_dev),
                coefficient_variation = VALUES(coefficient_variation),
                volatility_class = VALUES(volatility_class),
                sample_size_months = VALUES(sample_size_months),
                data_quality_score = VALUES(data_quality_score),
                calculation_method = VALUES(calculation_method),
                last_calculated = VALUES(last_calculated)
            """

            # Determine which average to store based on method
            if calculation_result.get('primary_method') == '6mo_weighted':
                demand_3mo = 0  # Not calculated in this case
                demand_6mo = calculation_result.get('weighted_average_base', 0)
            else:
                demand_3mo = calculation_result.get('weighted_average_base', 0)
                demand_6mo = 0  # Not calculated in this case

            values = (
                sku_id,
                demand_3mo,
                demand_6mo,
                volatility_metrics.get('standard_deviation', 0),
                volatility_metrics.get('coefficient_variation', 0),
                volatility_metrics.get('volatility_class', 'medium'),
                calculation_result.get('sample_months', 0),
                calculation_result.get('data_quality_score', 0),
                calculation_result.get('calculation_method', 'unknown')
            )

            db = database.get_database_connection()
            cursor = db.cursor()
            cursor.execute(insert_query, values)
            db.commit()

            cursor.close()
            db.close()

            logger.debug(f"Stored demand statistics for {sku_id}")

        except Exception as e:
            logger.error(f"Failed to store demand statistics for {sku_id}: {e}")

    def refresh_all_sku_statistics(self, limit: int = None) -> dict:
        """
        Batch refresh demand statistics for all active SKUs

        This method should be run monthly after sales data import to ensure
        all SKUs have up-to-date demand statistics.

        Args:
            limit: Maximum number of SKUs to process (None for all)

        Returns:
            Dictionary with processing summary
        """
        try:
            # Get list of active SKUs
            query = """
            SELECT sku_id, abc_code, xyz_code
            FROM skus
            WHERE status = 'Active'
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

            processed = 0
            errors = 0
            start_time = datetime.now()

            logger.info(f"Starting demand statistics refresh for {len(sku_list)} SKUs")

            for sku_record in sku_list:
                try:
                    sku_id = sku_record['sku_id']
                    abc_class = sku_record['abc_code'] or 'C'
                    xyz_class = sku_record['xyz_code'] or 'Z'

                    # Calculate enhanced demand (this will automatically store statistics)
                    self.get_enhanced_demand_calculation(sku_id, abc_class, xyz_class, 0, 0)

                    processed += 1

                    # Progress logging every 100 SKUs
                    if processed % 100 == 0:
                        logger.info(f"Processed {processed}/{len(sku_list)} SKUs")

                except Exception as e:
                    errors += 1
                    logger.error(f"Failed to refresh statistics for {sku_record.get('sku_id', 'unknown')}: {e}")

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                'total_skus': len(sku_list),
                'processed_successfully': processed,
                'errors': errors,
                'duration_seconds': round(duration, 2),
                'skus_per_second': round(processed / duration, 2) if duration > 0 else 0,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }

            logger.info(f"Demand statistics refresh completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to refresh demand statistics: {e}")
            return {
                'total_skus': 0,
                'processed_successfully': 0,
                'errors': 1,
                'error_message': str(e)
            }

    def calculate_coverage_with_safety_stock(self, sku_id: str, abc_class: str,
                                           enhanced_demand: float, supplier: str = None) -> dict:
        """
        Calculate optimal coverage target including safety stock considerations

        Integrates volatility analysis with safety stock calculations to determine
        appropriate coverage targets that balance inventory costs with service levels.

        Args:
            sku_id: SKU identifier
            abc_class: ABC classification
            enhanced_demand: Enhanced monthly demand from weighted calculations
            supplier: Supplier name for lead time lookup

        Returns:
            Dictionary with coverage recommendations and safety stock details
        """
        try:
            # Get volatility metrics
            volatility_metrics = self.calculate_demand_volatility(sku_id)

            # Convert monthly demand to weekly for safety stock calculation
            weekly_demand = enhanced_demand / 4.33  # Average weeks per month
            demand_std = volatility_metrics['standard_deviation'] / 4.33  # Weekly std dev

            # Calculate safety stock
            safety_stock_result = self.safety_stock_calculator.calculate_safety_stock(
                demand_std=demand_std,
                abc_class=abc_class,
                supplier=supplier,
                mean_demand=weekly_demand
            )

            # Get service level recommendations based on volatility
            service_recommendations = self.safety_stock_calculator.get_service_level_recommendations(
                abc_class, volatility_metrics['volatility_class']
            )

            # Calculate base coverage target (in months)
            base_coverage_months = self._get_base_coverage_target(abc_class, volatility_metrics['volatility_class'])

            # Convert safety stock from weeks to months of coverage
            safety_stock_months = (safety_stock_result['safety_stock'] / weekly_demand) / 4.33 if weekly_demand > 0 else 0

            # Adjust coverage based on volatility
            volatility_adjustment = self._calculate_volatility_adjustment(
                volatility_metrics['volatility_class'],
                volatility_metrics['coefficient_variation']
            )

            # Final coverage target
            adjusted_coverage_months = base_coverage_months + safety_stock_months + volatility_adjustment

            # Ensure reasonable bounds (2-12 months)
            final_coverage_months = max(2.0, min(12.0, adjusted_coverage_months))

            return {
                'recommended_coverage_months': round(final_coverage_months, 1),
                'base_coverage_months': base_coverage_months,
                'safety_stock_months': round(safety_stock_months, 2),
                'volatility_adjustment_months': round(volatility_adjustment, 2),
                'safety_stock_details': safety_stock_result,
                'service_level_info': service_recommendations,
                'volatility_metrics': volatility_metrics,
                'weekly_demand': round(weekly_demand, 2),
                'calculation_breakdown': {
                    'base': base_coverage_months,
                    'safety_stock': round(safety_stock_months, 2),
                    'volatility_adj': round(volatility_adjustment, 2),
                    'total_raw': round(adjusted_coverage_months, 2),
                    'final_bounded': round(final_coverage_months, 1)
                }
            }

        except Exception as e:
            logger.error(f"Coverage calculation failed for {sku_id}: {e}")
            # Return safe defaults
            return {
                'recommended_coverage_months': 6.0,
                'base_coverage_months': 6.0,
                'safety_stock_months': 0.0,
                'volatility_adjustment_months': 0.0,
                'error': str(e)
            }

    def _get_base_coverage_target(self, abc_class: str, volatility_class: str) -> float:
        """
        Get base coverage target in months based on ABC class and volatility

        Args:
            abc_class: ABC classification
            volatility_class: Volatility classification

        Returns:
            Base coverage target in months
        """
        # Base targets by ABC class
        base_targets = {
            'A': 4.0,  # High-value items: lower base coverage, rely on safety stock
            'B': 5.0,  # Medium-value items: balanced approach
            'C': 6.0   # Low-value items: higher base coverage, lower safety stock
        }

        base_coverage = base_targets.get(abc_class, 6.0)

        # Adjust for volatility
        if volatility_class == 'high':
            base_coverage += 0.5  # Add buffer for high volatility
        elif volatility_class == 'low':
            base_coverage -= 0.5  # Reduce for stable items

        return max(2.0, base_coverage)  # Minimum 2 months

    def _calculate_volatility_adjustment(self, volatility_class: str, cv: float) -> float:
        """
        Calculate additional coverage adjustment based on demand volatility

        Args:
            volatility_class: Volatility classification
            cv: Coefficient of variation

        Returns:
            Additional coverage in months
        """
        if volatility_class == 'high':
            # High volatility: significant buffer
            return min(2.0, cv * 3.0)  # Up to 2 months extra
        elif volatility_class == 'medium':
            # Medium volatility: moderate buffer
            return min(1.0, cv * 2.0)  # Up to 1 month extra
        else:
            # Low volatility: minimal buffer
            return min(0.5, cv * 1.0)  # Up to 0.5 months extra


class SafetyStockCalculator:
    """
    Statistical Safety Stock Calculator

    Implements standard safety stock formulas using demand volatility and lead time
    to calculate appropriate buffer stock levels based on service level targets.

    Safety Stock Formula: z_score * demand_std * sqrt(lead_time)

    Service Level Targets by ABC Classification:
    - A: 99% (z=2.33)
    - B: 95% (z=1.65)
    - C: 90% (z=1.28)
    """

    def __init__(self, config: dict = None):
        """
        Initialize SafetyStockCalculator with configuration

        Args:
            config: Configuration dictionary with service level targets and lead times
        """
        self.logger = logging.getLogger(__name__)

        # Default configuration
        self.config = {
            'service_levels': {
                'A': 0.99,  # 99% service level for A items
                'B': 0.95,  # 95% service level for B items
                'C': 0.90   # 90% service level for C items
            },
            'z_scores': {
                'A': 2.33,  # Z-score for 99% service level
                'B': 1.65,  # Z-score for 95% service level
                'C': 1.28   # Z-score for 90% service level
            },
            'default_lead_time_weeks': 3,  # Default lead time in weeks
            'lead_time_by_supplier': {},   # Supplier-specific lead times
            'min_safety_stock': 1,         # Minimum safety stock units
            'max_safety_stock_ratio': 2.0  # Max safety stock as ratio of average demand
        }

        # Override with provided config
        if config:
            self.config.update(config)

        self.logger.info("SafetyStockCalculator initialized")

    def get_z_score(self, abc_class: str, service_level: float = None) -> float:
        """
        Get Z-score for given ABC class or service level

        Args:
            abc_class: ABC classification (A, B, C)
            service_level: Optional specific service level (overrides ABC default)

        Returns:
            Z-score for statistical calculation
        """
        if service_level:
            # Calculate Z-score for custom service level using inverse normal distribution
            return norm.ppf(service_level)

        # Use predefined Z-scores for ABC classes
        return self.config['z_scores'].get(abc_class, self.config['z_scores']['C'])

    def get_lead_time(self, supplier: str = None) -> float:
        """
        Get lead time in weeks for supplier or default

        Args:
            supplier: Supplier name for specific lead time lookup

        Returns:
            Lead time in weeks
        """
        if supplier and supplier in self.config['lead_time_by_supplier']:
            return self.config['lead_time_by_supplier'][supplier]

        return self.config['default_lead_time_weeks']

    def calculate_safety_stock(self, demand_std: float, abc_class: str,
                             lead_time_weeks: float = None, supplier: str = None,
                             mean_demand: float = None) -> dict:
        """
        Calculate safety stock using statistical formula

        Formula: safety_stock = z_score * demand_std * sqrt(lead_time)

        Args:
            demand_std: Standard deviation of demand (from volatility calculation)
            abc_class: ABC classification for service level determination
            lead_time_weeks: Lead time in weeks (optional, uses default/supplier specific)
            supplier: Supplier name for lead time lookup
            mean_demand: Mean demand for validation checks

        Returns:
            Dictionary with safety stock calculation details
        """
        try:
            # Get lead time
            if lead_time_weeks is None:
                lead_time_weeks = self.get_lead_time(supplier)

            # Get Z-score for ABC class
            z_score = self.get_z_score(abc_class)
            service_level = self.config['service_levels'].get(abc_class, 0.90)

            # Calculate safety stock using formula
            safety_stock_raw = z_score * demand_std * np.sqrt(lead_time_weeks)

            # Apply minimum safety stock
            safety_stock = max(safety_stock_raw, self.config['min_safety_stock'])

            # Apply maximum safety stock validation if mean demand provided
            if mean_demand and mean_demand > 0:
                max_safety_stock = mean_demand * self.config['max_safety_stock_ratio']
                if safety_stock > max_safety_stock:
                    safety_stock = max_safety_stock
                    self.logger.warning(f"Safety stock capped at {max_safety_stock:.1f} "
                                      f"(raw calculation: {safety_stock_raw:.1f})")

            return {
                'safety_stock': round(safety_stock, 1),
                'safety_stock_raw': round(safety_stock_raw, 2),
                'z_score': z_score,
                'service_level': service_level,
                'demand_std': demand_std,
                'lead_time_weeks': lead_time_weeks,
                'abc_class': abc_class,
                'supplier': supplier,
                'calculation_method': 'statistical_safety_stock',
                'formula': f'{z_score:.2f} * {demand_std:.2f} * √{lead_time_weeks} = {safety_stock:.1f}'
            }

        except Exception as e:
            self.logger.error(f"Safety stock calculation failed: {e}")
            return {
                'safety_stock': self.config['min_safety_stock'],
                'safety_stock_raw': 0,
                'z_score': 0,
                'service_level': 0,
                'demand_std': demand_std,
                'lead_time_weeks': lead_time_weeks or 3,
                'abc_class': abc_class,
                'supplier': supplier,
                'calculation_method': 'fallback_minimum',
                'error': str(e)
            }

    def calculate_reorder_point(self, mean_demand: float, demand_std: float,
                              abc_class: str, lead_time_weeks: float = None,
                              supplier: str = None) -> dict:
        """
        Calculate reorder point including safety stock

        Formula: reorder_point = (mean_demand * lead_time) + safety_stock

        Args:
            mean_demand: Average weekly demand
            demand_std: Standard deviation of demand
            abc_class: ABC classification
            lead_time_weeks: Lead time in weeks
            supplier: Supplier name

        Returns:
            Dictionary with reorder point calculation
        """
        try:
            # Calculate safety stock
            safety_stock_result = self.calculate_safety_stock(
                demand_std, abc_class, lead_time_weeks, supplier, mean_demand
            )

            # Get lead time
            lead_time = safety_stock_result['lead_time_weeks']

            # Calculate reorder point
            average_demand_during_lead_time = mean_demand * lead_time
            reorder_point = average_demand_during_lead_time + safety_stock_result['safety_stock']

            return {
                'reorder_point': round(reorder_point, 1),
                'average_demand_lead_time': round(average_demand_during_lead_time, 1),
                'safety_stock': safety_stock_result['safety_stock'],
                'safety_stock_details': safety_stock_result,
                'mean_weekly_demand': mean_demand,
                'lead_time_weeks': lead_time,
                'calculation_formula': f'({mean_demand:.1f} * {lead_time}) + {safety_stock_result["safety_stock"]:.1f} = {reorder_point:.1f}'
            }

        except Exception as e:
            self.logger.error(f"Reorder point calculation failed: {e}")
            return {
                'reorder_point': mean_demand * 3 if mean_demand else 10,  # Fallback
                'error': str(e)
            }

    def get_service_level_recommendations(self, abc_class: str, volatility_class: str) -> dict:
        """
        Get recommended service levels based on ABC class and volatility

        Args:
            abc_class: ABC classification
            volatility_class: Volatility classification (low/medium/high)

        Returns:
            Dictionary with service level recommendations
        """
        base_service_level = self.config['service_levels'].get(abc_class, 0.90)

        # Adjust for volatility
        if volatility_class == 'high':
            # High volatility items may need higher service levels
            adjusted_service_level = min(base_service_level + 0.02, 0.995)
        elif volatility_class == 'low':
            # Low volatility items can use slightly lower service levels
            adjusted_service_level = max(base_service_level - 0.01, 0.85)
        else:
            adjusted_service_level = base_service_level

        return {
            'recommended_service_level': adjusted_service_level,
            'base_service_level': base_service_level,
            'volatility_adjustment': adjusted_service_level - base_service_level,
            'abc_class': abc_class,
            'volatility_class': volatility_class,
            'z_score': self.get_z_score(abc_class, adjusted_service_level)
        }


def test_weighted_demand_calculator():
    """
    Test function for the WeightedDemandCalculator
    """
    try:
        logger.info("Testing WeightedDemandCalculator...")

        calculator = WeightedDemandCalculator()

        # Test with a known SKU (replace with actual SKU from your database)
        test_sku = 'CHG-001'

        # Test 3-month weighted average
        result_3mo = calculator.get_weighted_3month_average(test_sku)
        logger.info(f"3-month weighted average for {test_sku}: {result_3mo}")

        # Test 6-month weighted average
        result_6mo = calculator.get_weighted_6month_average(test_sku)
        logger.info(f"6-month weighted average for {test_sku}: {result_6mo}")

        # Test volatility calculation
        volatility = calculator.calculate_demand_volatility(test_sku)
        logger.info(f"Demand volatility for {test_sku}: {volatility}")

        # Test enhanced demand calculation
        enhanced = calculator.get_enhanced_demand_calculation(test_sku, 'A', 'X', 100, 5)
        logger.info(f"Enhanced demand calculation for {test_sku}: {enhanced}")

        logger.info("WeightedDemandCalculator tests completed successfully")
        return True

    except Exception as e:
        logger.error(f"WeightedDemandCalculator test failed: {e}")
        return False


if __name__ == "__main__":
    # Set up logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run tests
    test_weighted_demand_calculator()