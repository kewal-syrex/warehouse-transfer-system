"""
Core business logic and calculations for transfer recommendations
Implements stockout correction and ABC-XYZ classification algorithms
Enhanced with seasonal pattern detection and viral growth analysis
"""
import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
try:
    from . import database
except ImportError:
    import database
import logging

logger = logging.getLogger(__name__)

class StockoutCorrector:
    """
    Handles stockout detection and demand correction calculations
    Enhanced with year-over-year lookups and category averages
    """

    @staticmethod
    def correct_monthly_demand(monthly_sales: int, stockout_days: int, days_in_month: int = 30) -> float:
        """
        Calculate stockout-corrected demand using the simplified monthly approach
        
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
            
            return round(corrected_demand, 2)

        return float(monthly_sales)

    @staticmethod
    def correct_monthly_demand_enhanced(sku_id: str, monthly_sales: int, stockout_days: int,
                                      year_month: str = None, days_in_month: int = 30) -> float:
        """
        Enhanced stockout correction with year-over-year and category fallbacks

        Args:
            sku_id: SKU identifier for historical lookup
            monthly_sales: Actual units sold in the month
            stockout_days: Number of days out of stock in the month
            year_month: Period for analysis (defaults to current)
            days_in_month: Total days in the month

        Returns:
            Corrected demand accounting for stockout periods with historical context
        """
        try:
            # Handle zero sales with significant stockout period
            if monthly_sales == 0 and stockout_days > 20:
                logger.info(f"Zero sales with {stockout_days} stockout days for {sku_id}, using enhanced logic")

                # Try year-over-year lookup first
                yoy_demand = StockoutCorrector.get_same_month_last_year(sku_id, year_month)
                if yoy_demand > 0:
                    # Apply growth factor for year-over-year data
                    return round(yoy_demand * 1.1, 2)  # 10% growth assumption

                # Fall back to category average
                category_avg = StockoutCorrector.get_category_average(sku_id)
                if category_avg > 0:
                    return round(category_avg, 2)

                # Final fallback to basic correction
                return 10.0  # Minimum viable demand estimate

            # Use standard correction for all other cases
            return StockoutCorrector.correct_monthly_demand(monthly_sales, stockout_days, days_in_month)

        except Exception as e:
            logger.error(f"Enhanced correction failed for {sku_id}: {e}")
            return StockoutCorrector.correct_monthly_demand(monthly_sales, stockout_days, days_in_month)

    @staticmethod
    def get_same_month_last_year(sku_id: str, current_year_month: str = None) -> float:
        """
        Get demand from the same month in the previous year for seasonal comparison

        Args:
            sku_id: SKU identifier
            current_year_month: Current period (format: YYYY-MM)

        Returns:
            Previous year demand for same month, 0 if not found
        """
        try:
            if not current_year_month:
                # Get the latest month for this SKU
                query = """
                SELECT MAX(year_month) as latest_month
                FROM monthly_sales
                WHERE sku_id = %s
                """
                result = database.execute_query(query, (sku_id,), fetch_one=True)
                current_year_month = result['latest_month'] if result else None

            if not current_year_month:
                return 0.0

            # Calculate previous year month
            year, month = current_year_month.split('-')
            prev_year = int(year) - 1
            prev_year_month = f"{prev_year}-{month}"

            # Query for previous year data
            query = """
            SELECT kentucky_sales, corrected_demand_kentucky
            FROM monthly_sales
            WHERE sku_id = %s AND year_month = %s
            """

            result = database.execute_query(query, (sku_id, prev_year_month), fetch_one=True)

            if result:
                # Use corrected demand if available, otherwise raw sales
                demand = result['corrected_demand_kentucky'] or result['kentucky_sales'] or 0
                logger.debug(f"Found {prev_year_month} demand for {sku_id}: {demand}")
                return float(demand)

            return 0.0

        except Exception as e:
            logger.error(f"Year-over-year lookup failed for {sku_id}: {e}")
            return 0.0

    @staticmethod
    def get_category_average(sku_id: str) -> float:
        """
        Get category average demand for SKUs without historical data

        Args:
            sku_id: SKU identifier to get category for

        Returns:
            Average category demand, 0 if not available
        """
        try:
            # Get SKU category
            sku_query = """
            SELECT category FROM skus WHERE sku_id = %s AND category IS NOT NULL
            """
            sku_result = database.execute_query(sku_query, (sku_id,), fetch_one=True)

            if not sku_result or not sku_result['category']:
                logger.debug(f"No category found for {sku_id}")
                return 0.0

            category = sku_result['category']

            # Get category average from view
            avg_query = """
            SELECT avg_corrected_demand, avg_monthly_sales
            FROM v_category_averages
            WHERE category = %s
            """

            avg_result = database.execute_query(avg_query, (category,), fetch_one=True)

            if avg_result:
                # Use corrected demand average if available, otherwise sales average
                avg_demand = avg_result['avg_corrected_demand'] or avg_result['avg_monthly_sales'] or 0
                logger.debug(f"Category {category} average for {sku_id}: {avg_demand}")
                return float(avg_demand)

            return 0.0

        except Exception as e:
            logger.error(f"Category average lookup failed for {sku_id}: {e}")
            return 0.0

class ABCXYZClassifier:
    """Handles ABC-XYZ classification for inventory management"""
    
    @staticmethod
    def classify_abc(annual_value: float, total_value: float) -> str:
        """
        Classify SKU based on annual value (Pareto 80/15/5 rule)
        
        Args:
            annual_value: Annual sales value for the SKU
            total_value: Total annual sales value across all SKUs
        
        Returns:
            ABC classification ('A', 'B', or 'C')
        """
        if total_value == 0:
            return 'C'
        
        percentage = (annual_value / total_value) * 100
        
        if percentage >= 80:  # Top 80% of value
            return 'A'
        elif percentage >= 15:  # Next 15% of value
            return 'B'
        else:  # Bottom 5% of value
            return 'C'
    
    @staticmethod
    def classify_xyz(sales_data: List[float]) -> str:
        """
        Classify SKU based on demand variability (coefficient of variation)
        
        Args:
            sales_data: List of monthly sales figures
        
        Returns:
            XYZ classification ('X', 'Y', or 'Z')
        """
        if len(sales_data) < 2:
            return 'Z'  # Insufficient data = irregular
        
        mean_sales = sum(sales_data) / len(sales_data)
        if mean_sales == 0:
            return 'Z'
        
        # Calculate standard deviation
        variance = sum((x - mean_sales) ** 2 for x in sales_data) / (len(sales_data) - 1)
        std_dev = math.sqrt(variance)
        
        # Coefficient of variation
        cv = std_dev / mean_sales
        
        if cv < 0.25:
            return 'X'  # Stable demand
        elif cv < 0.50:
            return 'Y'  # Variable demand
        else:
            return 'Z'  # Irregular demand


class SeasonalPatternDetector:
    """
    Detects seasonal patterns in SKU demand using historical data analysis
    Classifies patterns as spring_summer, fall_winter, holiday, or year_round
    """

    @staticmethod
    def detect_seasonal_pattern(sku_id: str) -> str:
        """
        Analyze 2+ years of monthly data to classify seasonal patterns

        Args:
            sku_id: SKU identifier to analyze

        Returns:
            Seasonal pattern classification string
        """
        try:
            # Get historical monthly sales data (2+ years)
            query = """
            SELECT
                year_month,
                kentucky_sales,
                corrected_demand_kentucky,
                MONTH(STR_TO_DATE(CONCAT(year_month, '-01'), '%Y-%m-%d')) as month_num,
                YEAR(STR_TO_DATE(CONCAT(year_month, '-01'), '%Y-%m-%d')) as year_num
            FROM monthly_sales
            WHERE sku_id = %s
                AND year_month >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 24 MONTH), '%Y-%m')
            ORDER BY year_month
            """

            sales_data = database.execute_query(query, (sku_id,))

            if not sales_data or len(sales_data) < 12:
                logger.debug(f"Insufficient data for seasonal analysis: {sku_id}")
                return 'year_round'  # Default when insufficient data

            # Aggregate sales by month across years
            monthly_totals = defaultdict(list)
            for record in sales_data:
                month = record['month_num']
                sales = record['corrected_demand_kentucky'] or record['kentucky_sales'] or 0
                monthly_totals[month].append(sales)

            # Calculate average sales by month
            monthly_averages = {}
            for month in range(1, 13):
                if month in monthly_totals and monthly_totals[month]:
                    monthly_averages[month] = np.mean(monthly_totals[month])
                else:
                    monthly_averages[month] = 0

            # Analyze patterns
            pattern = SeasonalPatternDetector._classify_pattern(monthly_averages)
            logger.info(f"Detected seasonal pattern for {sku_id}: {pattern}")

            return pattern

        except Exception as e:
            logger.error(f"Seasonal pattern detection failed for {sku_id}: {e}")
            return 'year_round'

    @staticmethod
    def _classify_pattern(monthly_averages: Dict[int, float]) -> str:
        """
        Classify seasonal pattern based on monthly averages

        Args:
            monthly_averages: Dict mapping month number to average sales

        Returns:
            Pattern classification string
        """
        if not monthly_averages or all(v == 0 for v in monthly_averages.values()):
            return 'year_round'

        total_avg = np.mean(list(monthly_averages.values()))
        if total_avg == 0:
            return 'year_round'

        # Calculate seasonal indicators
        spring_summer = np.mean([monthly_averages[m] for m in [3, 4, 5, 6, 7, 8]])  # Mar-Aug
        fall_winter = np.mean([monthly_averages[m] for m in [9, 10, 11, 12, 1, 2]])  # Sep-Feb
        holiday = np.mean([monthly_averages[m] for m in [11, 12]])  # Nov-Dec

        # Normalize by total average to get relative strength
        spring_summer_ratio = spring_summer / total_avg if total_avg > 0 else 1
        fall_winter_ratio = fall_winter / total_avg if total_avg > 0 else 1
        holiday_ratio = holiday / total_avg if total_avg > 0 else 1

        # Classification thresholds
        SEASONAL_THRESHOLD = 1.3  # 30% above average
        HOLIDAY_THRESHOLD = 1.5   # 50% above average for holiday

        # Classification logic
        if holiday_ratio >= HOLIDAY_THRESHOLD:
            return 'holiday'
        elif spring_summer_ratio >= SEASONAL_THRESHOLD and spring_summer_ratio > fall_winter_ratio:
            return 'spring_summer'
        elif fall_winter_ratio >= SEASONAL_THRESHOLD and fall_winter_ratio > spring_summer_ratio:
            return 'fall_winter'
        else:
            return 'year_round'

    @staticmethod
    def get_seasonal_multiplier(pattern: str, current_month: int) -> float:
        """
        Get seasonal adjustment multiplier based on pattern and month

        Args:
            pattern: Seasonal pattern classification
            current_month: Current month number (1-12)

        Returns:
            Multiplier for seasonal adjustment (typically 0.8-1.5)
        """
        # Define seasonal multipliers by pattern and month
        multipliers = {
            'spring_summer': {
                1: 0.8, 2: 0.8, 3: 1.1, 4: 1.2, 5: 1.3, 6: 1.3,
                7: 1.2, 8: 1.1, 9: 0.9, 10: 0.9, 11: 0.8, 12: 0.8
            },
            'fall_winter': {
                1: 1.2, 2: 1.1, 3: 0.9, 4: 0.8, 5: 0.8, 6: 0.8,
                7: 0.8, 8: 0.9, 9: 1.1, 10: 1.2, 11: 1.3, 12: 1.2
            },
            'holiday': {
                1: 0.8, 2: 0.8, 3: 0.9, 4: 0.9, 5: 0.9, 6: 0.9,
                7: 0.9, 8: 0.9, 9: 1.0, 10: 1.1, 11: 1.4, 12: 1.5
            },
            'year_round': {month: 1.0 for month in range(1, 13)}
        }

        return multipliers.get(pattern, multipliers['year_round']).get(current_month, 1.0)


class ViralGrowthDetector:
    """
    Detects viral growth patterns in SKU demand
    Compares recent 3 months to previous 3 months to identify rapid growth
    """

    @staticmethod
    def detect_viral_growth(sku_id: str) -> str:
        """
        Compare recent 3 months to previous 3 months to detect viral growth

        Args:
            sku_id: SKU identifier to analyze

        Returns:
            Growth status: 'viral', 'normal', or 'declining'
        """
        try:
            # Get last 6 months of sales data
            query = """
            SELECT
                year_month,
                kentucky_sales,
                corrected_demand_kentucky,
                ROW_NUMBER() OVER (ORDER BY year_month DESC) as recency_rank
            FROM monthly_sales
            WHERE sku_id = %s
                AND year_month >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 6 MONTH), '%Y-%m')
            ORDER BY year_month DESC
            LIMIT 6
            """

            sales_data = database.execute_query(query, (sku_id,))

            if not sales_data or len(sales_data) < 6:
                logger.debug(f"Insufficient data for viral growth analysis: {sku_id}")
                return 'normal'

            # Split into recent 3 months vs previous 3 months
            recent_sales = []
            previous_sales = []

            for record in sales_data:
                sales = record['corrected_demand_kentucky'] or record['kentucky_sales'] or 0
                if record['recency_rank'] <= 3:
                    recent_sales.append(sales)
                else:
                    previous_sales.append(sales)

            # Calculate averages
            recent_avg = np.mean(recent_sales) if recent_sales else 0
            previous_avg = np.mean(previous_sales) if previous_sales else 0

            # Determine growth status
            growth_status = ViralGrowthDetector._classify_growth(recent_avg, previous_avg)
            logger.info(f"Growth analysis for {sku_id}: recent={recent_avg:.1f}, previous={previous_avg:.1f}, status={growth_status}")

            return growth_status

        except Exception as e:
            logger.error(f"Viral growth detection failed for {sku_id}: {e}")
            return 'normal'

    @staticmethod
    def _classify_growth(recent_avg: float, previous_avg: float) -> str:
        """
        Classify growth based on recent vs previous averages

        Args:
            recent_avg: Average demand in recent 3 months
            previous_avg: Average demand in previous 3 months

        Returns:
            Growth classification: 'viral', 'normal', or 'declining'
        """
        if previous_avg == 0:
            return 'viral' if recent_avg > 10 else 'normal'  # New product with demand

        growth_ratio = recent_avg / previous_avg

        # Classification thresholds
        VIRAL_THRESHOLD = 2.0      # 100% growth = viral
        DECLINING_THRESHOLD = 0.5  # 50% decline = declining

        if growth_ratio >= VIRAL_THRESHOLD:
            return 'viral'
        elif growth_ratio <= DECLINING_THRESHOLD:
            return 'declining'
        else:
            return 'normal'

    @staticmethod
    def get_growth_multiplier(growth_status: str) -> float:
        """
        Get demand multiplier based on growth status

        Args:
            growth_status: Growth classification

        Returns:
            Multiplier for demand adjustment
        """
        multipliers = {
            'viral': 1.5,      # Increase demand estimates for viral products
            'normal': 1.0,     # No adjustment for normal growth
            'declining': 0.8   # Reduce demand estimates for declining products
        }

        return multipliers.get(growth_status, 1.0)

class TransferCalculator:
    """
    Main calculator for transfer recommendations
    Enhanced with seasonal patterns and viral growth detection
    """

    # Burnaby retention configuration parameters
    BURNABY_MIN_COVERAGE_MONTHS = 2.0    # Never go below this threshold
    BURNABY_TARGET_COVERAGE_MONTHS = 6.0  # Default target retention
    BURNABY_COVERAGE_WITH_PENDING = 1.5   # When pending arrivals < 45 days

    def __init__(self):
        self.corrector = StockoutCorrector()
        self.classifier = ABCXYZClassifier()
        self.seasonal_detector = SeasonalPatternDetector()
        self.growth_detector = ViralGrowthDetector()
    
    def get_coverage_target(self, abc_class: str, xyz_class: str) -> float:
        """
        Get coverage target in months based on ABC-XYZ classification
        
        Args:
            abc_class: ABC classification ('A', 'B', 'C')
            xyz_class: XYZ classification ('X', 'Y', 'Z')
        
        Returns:
            Target coverage in months
        """
        # Coverage matrix from PRD
        coverage_matrix = {
            'AX': 4, 'AY': 5, 'AZ': 6,
            'BX': 3, 'BY': 4, 'BZ': 5,
            'CX': 2, 'CY': 2, 'CZ': 1
        }
        
        key = f"{abc_class}{xyz_class}"
        return coverage_matrix.get(key, 6)  # Default 6 months if unknown
    
    def round_to_multiple(self, quantity: int, multiple: int) -> int:
        """
        Round transfer quantity to appropriate multiple
        
        Args:
            quantity: Calculated transfer quantity
            multiple: Transfer multiple (25, 50, 100)
        
        Returns:
            Rounded quantity respecting minimum transfer of 10 units
        """
        if quantity < 10:
            return 0  # Below minimum transfer threshold
        
        return math.ceil(quantity / multiple) * multiple

    def get_pending_orders_data(self, sku_id: str) -> Dict[str, Any]:
        """
        Get pending orders data for a specific SKU from database views

        Args:
            sku_id: SKU identifier

        Returns:
            Dictionary with pending orders information
        """
        try:
            db = database.get_database_connection()
            import pymysql
            cursor = db.cursor(pymysql.cursors.DictCursor)

            # Query the pending quantities view
            query = """
            SELECT
                burnaby_pending,
                kentucky_pending,
                total_pending,
                earliest_arrival
            FROM v_pending_quantities
            WHERE sku_id = %s
            """

            cursor.execute(query, (sku_id,))
            result = cursor.fetchone()
            cursor.close()
            db.close()

            if result:
                # Calculate days until arrival
                days_until_arrival = None
                if result['earliest_arrival']:
                    days_until_arrival = (result['earliest_arrival'] - datetime.now().date()).days

                return {
                    'burnaby_pending': result['burnaby_pending'] or 0,
                    'kentucky_pending': result['kentucky_pending'] or 0,
                    'total_pending': result['total_pending'] or 0,
                    'earliest_arrival': result['earliest_arrival'],
                    'days_until_arrival': days_until_arrival
                }

            return {
                'burnaby_pending': 0,
                'kentucky_pending': 0,
                'total_pending': 0,
                'earliest_arrival': None,
                'days_until_arrival': None
            }

        except Exception as e:
            logger.error(f"Failed to get pending orders for {sku_id}: {e}")
            return {
                'burnaby_pending': 0,
                'kentucky_pending': 0,
                'total_pending': 0,
                'earliest_arrival': None,
                'days_until_arrival': None
            }

    def check_stockout_override(self, sku_id: str, warehouse: str = 'kentucky') -> Dict[str, Any]:
        """
        Check if a SKU is marked as out-of-stock in stockout_dates table

        Args:
            sku_id: SKU identifier
            warehouse: Warehouse to check ('kentucky' or 'burnaby')

        Returns:
            Dictionary with override information
        """
        try:
            db = database.get_database_connection()
            import pymysql
            cursor = db.cursor(pymysql.cursors.DictCursor)

            # Check for active stockouts (no date_back_in or future date)
            query = """
            SELECT COUNT(*) as active_stockouts
            FROM stockout_dates
            WHERE sku_id = %s
            AND warehouse = %s
            AND (date_back_in IS NULL OR date_back_in > CURDATE())
            """

            cursor.execute(query, (sku_id, warehouse))
            result = cursor.fetchone()
            cursor.close()
            db.close()

            active_stockouts = result['active_stockouts'] if result else 0

            return {
                'is_overridden': active_stockouts > 0,
                'override_reason': f"Active stockout in {warehouse}" if active_stockouts > 0 else None
            }

        except Exception as e:
            logger.error(f"Failed to check stockout override for {sku_id}: {e}")
            return {
                'is_overridden': False,
                'override_reason': None
            }

    def calculate_burnaby_retention(self, burnaby_qty: int, burnaby_demand: float,
                                   pending_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate how much inventory Burnaby should retain based on pending orders

        Args:
            burnaby_qty: Current Burnaby inventory
            burnaby_demand: Monthly demand for Burnaby
            pending_data: Pending orders data from get_pending_orders_data()

        Returns:
            Dictionary with retention calculation details
        """
        try:
            days_until_arrival = pending_data.get('days_until_arrival')
            burnaby_pending = pending_data.get('burnaby_pending', 0)

            # Determine retention strategy based on pending arrivals
            if days_until_arrival is not None and days_until_arrival < 45 and burnaby_pending > 0:
                # Reduce retention when pending orders are imminent
                burnaby_min_retain = burnaby_demand * self.BURNABY_COVERAGE_WITH_PENDING
                retention_reason = f"Reduced retention due to pending arrival in {days_until_arrival} days"
            else:
                # Standard retention
                burnaby_min_retain = burnaby_demand * self.BURNABY_MIN_COVERAGE_MONTHS
                retention_reason = "Standard retention policy"

            # Calculate available for transfer
            available_for_transfer = max(0, burnaby_qty - burnaby_min_retain)

            # Calculate coverage after considering pending
            total_available = burnaby_qty + burnaby_pending
            coverage_with_pending = total_available / max(burnaby_demand, 1)

            return {
                'burnaby_min_retain': int(burnaby_min_retain),
                'available_for_transfer': int(available_for_transfer),
                'retention_reason': retention_reason,
                'coverage_with_pending': round(coverage_with_pending, 1),
                'burnaby_pending': burnaby_pending
            }

        except Exception as e:
            logger.error(f"Burnaby retention calculation failed: {e}")
            # Safe fallback
            burnaby_min_retain = burnaby_demand * self.BURNABY_MIN_COVERAGE_MONTHS
            return {
                'burnaby_min_retain': int(burnaby_min_retain),
                'available_for_transfer': max(0, int(burnaby_qty - burnaby_min_retain)),
                'retention_reason': "Fallback retention calculation",
                'coverage_with_pending': burnaby_qty / max(burnaby_demand, 1),
                'burnaby_pending': 0
            }

    def calculate_transfer_recommendation(self, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate transfer recommendation for a single SKU
        
        Args:
            sku_data: Dictionary containing SKU information
        
        Returns:
            Dictionary with transfer recommendation
        """
        try:
            # Extract data
            sku_id = sku_data['sku_id']
            burnaby_qty = sku_data.get('burnaby_qty', 0)
            kentucky_qty = sku_data.get('kentucky_qty', 0)
            kentucky_sales = sku_data.get('kentucky_sales', 0)
            stockout_days = sku_data.get('kentucky_stockout_days', 0)
            abc_class = sku_data.get('abc_code', 'C')
            xyz_class = sku_data.get('xyz_code', 'Z')
            transfer_multiple = sku_data.get('transfer_multiple', 50)
            
            # Calculate corrected demand using enhanced method
            corrected_demand = self.corrector.correct_monthly_demand_enhanced(
                sku_id, kentucky_sales, stockout_days, '2024-03'
            )
            
            # Update database with corrected demand
            database.update_corrected_demand(sku_id, '2024-03', corrected_demand)
            
            # Calculate target inventory
            coverage_months = self.get_coverage_target(abc_class, xyz_class)
            target_inventory = corrected_demand * coverage_months
            
            # Account for pending inventory (simplified - assume none for now)
            pending_qty = 0
            
            # Calculate transfer need
            current_position = kentucky_qty + pending_qty
            transfer_need = target_inventory - current_position
            
            # Check Burnaby availability
            available_to_transfer = min(transfer_need, burnaby_qty)
            
            # Round to multiple
            recommended_qty = self.round_to_multiple(available_to_transfer, transfer_multiple)
            
            # Calculate priority
            if kentucky_qty == 0:
                priority = "CRITICAL"
            elif kentucky_qty / max(corrected_demand, 1) < 1:  # Less than 1 month coverage
                priority = "HIGH"
            elif kentucky_qty / max(corrected_demand, 1) < 2:  # Less than 2 months coverage
                priority = "MEDIUM"
            else:
                priority = "LOW"
            
            # Create reason
            reason_parts = []
            if stockout_days > 0:
                reason_parts.append(f"Stockout correction applied ({stockout_days} days out)")
            if kentucky_qty == 0:
                reason_parts.append("Currently out of stock")
            elif kentucky_qty / max(corrected_demand, 1) < coverage_months:
                reason_parts.append(f"Below target coverage ({coverage_months:.1f} months)")
            
            reason = "; ".join(reason_parts) if reason_parts else "Maintain optimal stock level"
            
            return {
                'sku_id': sku_id,
                'description': sku_data.get('description', ''),
                'current_kentucky_qty': kentucky_qty,
                'current_burnaby_qty': burnaby_qty,
                'corrected_monthly_demand': corrected_demand,
                'recommended_transfer_qty': recommended_qty,
                'coverage_months': round(kentucky_qty / max(corrected_demand, 1), 1),
                'target_coverage_months': coverage_months,
                'priority': priority,
                'reason': reason,
                'abc_class': abc_class,
                'xyz_class': xyz_class,
                'transfer_multiple': transfer_multiple,
                'stockout_days': stockout_days
            }
            
        except Exception as e:
            logger.error(f"Calculation failed for SKU {sku_data.get('sku_id', 'unknown')}: {e}")
            return None

    def calculate_enhanced_transfer_recommendation(self, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate transfer recommendation with enhanced seasonal and growth adjustments

        Args:
            sku_data: Dictionary containing SKU information

        Returns:
            Dictionary with enhanced transfer recommendation
        """
        try:
            # Get basic recommendation first
            basic_rec = self.calculate_transfer_recommendation(sku_data)
            if not basic_rec:
                return None

            sku_id = sku_data['sku_id']
            current_month = datetime.now().month
            stockout_days = sku_data.get('kentucky_stockout_days', 0)

            # Detect and apply seasonal patterns
            seasonal_pattern = self.seasonal_detector.detect_seasonal_pattern(sku_id)
            seasonal_multiplier = self.seasonal_detector.get_seasonal_multiplier(seasonal_pattern, current_month)

            # Detect and apply growth patterns
            growth_status = self.growth_detector.detect_viral_growth(sku_id)
            growth_multiplier = self.growth_detector.get_growth_multiplier(growth_status)

            # Apply enhancements to demand
            base_demand = basic_rec['corrected_monthly_demand']
            enhanced_demand = base_demand * seasonal_multiplier * growth_multiplier

            # Recalculate target inventory with enhanced demand
            coverage_months = self.get_coverage_target(basic_rec['abc_class'], basic_rec['xyz_class'])
            enhanced_target = enhanced_demand * coverage_months

            # Recalculate transfer need
            kentucky_qty = basic_rec['current_kentucky_qty']
            transfer_need = enhanced_target - kentucky_qty
            available_to_transfer = min(transfer_need, basic_rec['current_burnaby_qty'])
            enhanced_transfer_qty = self.round_to_multiple(available_to_transfer, basic_rec['transfer_multiple'])

            # Check for seasonal pre-positioning needs
            seasonal_positioning = self.get_seasonal_pre_positioning(sku_id, seasonal_pattern, current_month)

            # Apply seasonal pre-positioning multiplier if needed
            final_demand = enhanced_demand
            if seasonal_positioning['needs_pre_positioning']:
                pre_position_multiplier = seasonal_positioning['multiplier']
                final_demand = enhanced_demand * pre_position_multiplier

                # Recalculate transfer need with pre-positioning
                coverage_months = self.get_coverage_target(basic_rec['abc_class'], basic_rec['xyz_class'])
                pre_position_target = final_demand * coverage_months
                transfer_need = pre_position_target - kentucky_qty
                available_to_transfer = min(transfer_need, basic_rec['current_burnaby_qty'])
                enhanced_transfer_qty = self.round_to_multiple(available_to_transfer, basic_rec['transfer_multiple'])

            # Calculate priority score using new scoring system
            score_data = {
                'kentucky_stockout_days': stockout_days,
                'kentucky_qty': kentucky_qty,
                'corrected_demand': final_demand,
                'abc_code': basic_rec['abc_class'],
                'growth_status': growth_status
            }
            priority_analysis = self.calculate_priority_score(score_data)
            enhanced_priority = priority_analysis['priority_level']

            # Generate detailed transfer reason
            reason_factors = {
                'base_reason': basic_rec['reason'],
                'stockout_days': stockout_days,
                'growth_status': growth_status,
                'seasonal_info': seasonal_positioning,
                'current_coverage': kentucky_qty / max(final_demand, 1),
                'target_coverage': coverage_months,
                'abc_class': basic_rec['abc_class'],
                'kentucky_qty': kentucky_qty
            }
            enhanced_reason = self.generate_detailed_transfer_reason(reason_factors)

            # Update database with patterns
            self._update_sku_patterns(sku_id, seasonal_pattern, growth_status)

            # Create enhanced recommendation
            enhanced_rec = basic_rec.copy()
            enhanced_rec.update({
                'corrected_monthly_demand': round(final_demand, 2),
                'recommended_transfer_qty': enhanced_transfer_qty,
                'priority': enhanced_priority,
                'reason': enhanced_reason,
                'seasonal_pattern': seasonal_pattern,
                'growth_status': growth_status,
                'seasonal_multiplier': round(seasonal_multiplier, 2),
                'growth_multiplier': round(growth_multiplier, 2),
                'coverage_months': round(kentucky_qty / max(final_demand, 1), 1),
                'enhanced_calculation': True,
                'seasonal_positioning': seasonal_positioning,
                'priority_analysis': priority_analysis
            })

            return enhanced_rec

        except Exception as e:
            logger.error(f"Enhanced calculation failed for SKU {sku_data.get('sku_id', 'unknown')}: {e}")
            # Fallback to basic calculation
            return self.calculate_transfer_recommendation(sku_data)

    def calculate_enhanced_transfer_with_economic_validation(self, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate transfer recommendation with economic validation to prevent source warehouse stockouts

        This enhanced method adds critical business logic to prevent transfers that would
        leave the source warehouse (Burnaby) understocked relative to its own demand.

        Key Features:
        - Economic validation: prevents transfers when CA demand > KY demand * 1.5
        - Enhanced retention logic with proper Burnaby demand calculation
        - Comprehensive coverage calculations for both warehouses
        - Detailed business justification for all recommendations

        Args:
            sku_data: Dictionary containing SKU information including sales and inventory data

        Returns:
            Dictionary with enhanced transfer recommendation including economic validation

        Raises:
            ValueError: If required SKU data is missing or invalid
        """
        try:
            # Extract SKU data with proper null handling
            sku_id = sku_data['sku_id']
            burnaby_qty = sku_data.get('burnaby_qty') or 0
            kentucky_qty = sku_data.get('kentucky_qty') or 0
            kentucky_sales = sku_data.get('kentucky_sales') or 0
            burnaby_sales = sku_data.get('burnaby_sales') or 0
            stockout_days = sku_data.get('kentucky_stockout_days') or 0
            burnaby_stockout_days = sku_data.get('burnaby_stockout_days') or 0
            abc_class = sku_data.get('abc_code', 'C')
            xyz_class = sku_data.get('xyz_code', 'Z')
            transfer_multiple = sku_data.get('transfer_multiple', 50)

            # Step 1: Calculate corrected demand for BOTH warehouses
            current_month = datetime.now().strftime('%Y-%m')

            kentucky_corrected_demand = self.corrector.correct_monthly_demand_enhanced(
                sku_id, kentucky_sales, stockout_days, current_month
            )

            burnaby_corrected_demand = self.corrector.correct_monthly_demand_enhanced(
                sku_id, burnaby_sales, burnaby_stockout_days, current_month
            )

            # Step 2: Economic Validation - Don't transfer if CA demand significantly higher than KY
            economic_validation_passed = True
            economic_reason = ""

            if burnaby_corrected_demand > kentucky_corrected_demand * 1.5:
                economic_validation_passed = False
                economic_reason = f"CA demand ({burnaby_corrected_demand:.0f}) too high vs KY demand ({kentucky_corrected_demand:.0f}). Transfer would risk CA stockout."

            # Step 3: Calculate Burnaby minimum retention (never go below 2 months)
            burnaby_min_retain = burnaby_corrected_demand * self.BURNABY_MIN_COVERAGE_MONTHS
            available_for_transfer = max(0, burnaby_qty - burnaby_min_retain)

            # Step 4: Calculate transfer need for Kentucky
            coverage_months = self.get_coverage_target(abc_class, xyz_class)
            target_inventory = kentucky_corrected_demand * coverage_months
            transfer_need = max(0, target_inventory - kentucky_qty)

            # Step 5: Determine final transfer quantity
            if not economic_validation_passed:
                # Economic validation failed - no transfer
                final_transfer_qty = 0
                priority = "LOW"
                reason = economic_reason
            elif available_for_transfer <= 0:
                # Insufficient inventory after retention
                final_transfer_qty = 0
                priority = "LOW" if kentucky_qty > kentucky_corrected_demand else "MEDIUM"
                reason = f"Insufficient CA inventory for transfer. CA needs {burnaby_min_retain:.0f} for 2-month coverage, only has {burnaby_qty}"
            else:
                # Normal transfer calculation
                recommended_qty = min(transfer_need, available_for_transfer)
                final_transfer_qty = self.round_to_multiple(recommended_qty, transfer_multiple)

                # Calculate priority based on Kentucky situation
                if kentucky_qty == 0:
                    priority = "CRITICAL"
                elif kentucky_qty < kentucky_corrected_demand:
                    priority = "HIGH"
                elif kentucky_qty < kentucky_corrected_demand * 2:
                    priority = "MEDIUM"
                else:
                    priority = "LOW"

                # Generate comprehensive reason
                if final_transfer_qty > 0:
                    reason = f"Transfer {final_transfer_qty} units. CA retains {burnaby_min_retain:.0f} for 2-month coverage. Economic validation passed."
                else:
                    reason = f"No transfer needed. KY has {kentucky_qty} units vs {kentucky_corrected_demand:.0f} monthly demand."

            # Step 6: Calculate coverage after transfer
            burnaby_coverage_after = (burnaby_qty - final_transfer_qty) / max(burnaby_corrected_demand, 1)
            kentucky_coverage_after = (kentucky_qty + final_transfer_qty) / max(kentucky_corrected_demand, 1)

            # Step 7: Return comprehensive recommendation
            return {
                'sku_id': sku_id,
                'description': sku_data.get('description', ''),
                'current_burnaby_qty': burnaby_qty,
                'current_kentucky_qty': kentucky_qty,
                'corrected_monthly_demand': kentucky_corrected_demand,
                'burnaby_corrected_demand': burnaby_corrected_demand,
                'recommended_transfer_qty': final_transfer_qty,
                'transfer_multiple': transfer_multiple,
                'priority': priority,
                'reason': reason,
                'abc_class': abc_class,
                'xyz_class': xyz_class,
                'stockout_days': stockout_days,
                'coverage_months': kentucky_qty / max(kentucky_corrected_demand, 1),
                'target_coverage_months': coverage_months,
                'burnaby_coverage_after_transfer': round(burnaby_coverage_after, 1),
                'kentucky_coverage_after_transfer': round(kentucky_coverage_after, 1),
                'economic_validation_passed': economic_validation_passed,
                'available_from_burnaby': available_for_transfer,
                'burnaby_min_retain': burnaby_min_retain
            }

        except Exception as e:
            logger.error(f"Enhanced transfer calculation with economic validation failed for SKU {sku_id}: {e}")
            # Return safe fallback
            return {
                'sku_id': sku_id,
                'description': sku_data.get('description', ''),
                'current_burnaby_qty': burnaby_qty,
                'current_kentucky_qty': kentucky_qty,
                'corrected_monthly_demand': 0,
                'burnaby_corrected_demand': 0,
                'recommended_transfer_qty': 0,
                'transfer_multiple': transfer_multiple,
                'priority': "LOW",
                'reason': f"Calculation error: {str(e)}",
                'abc_class': abc_class,
                'xyz_class': xyz_class,
                'stockout_days': 0,
                'coverage_months': 0,
                'target_coverage_months': self.get_coverage_target(abc_class, xyz_class),
                'burnaby_coverage_after_transfer': 0,
                'kentucky_coverage_after_transfer': 0,
                'economic_validation_passed': False,
                'available_from_burnaby': 0,
                'burnaby_min_retain': 0
            }

    def calculate_enhanced_transfer_with_pending(self, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate transfer recommendation with full pending orders and stockout override support

        This method incorporates:
        - Pending orders data from v_pending_quantities view
        - Burnaby retention logic with configurable coverage
        - Stockout overrides for Kentucky quantities
        - Enhanced seasonal and growth patterns
        - Comprehensive priority scoring

        Args:
            sku_data: Dictionary containing SKU information

        Returns:
            Dictionary with comprehensive transfer recommendation
        """
        try:
            sku_id = sku_data['sku_id']
            burnaby_qty = sku_data.get('burnaby_qty', 0)
            kentucky_qty = sku_data.get('kentucky_qty', 0)
            kentucky_sales = sku_data.get('kentucky_sales', 0)
            burnaby_sales = sku_data.get('burnaby_sales', 0)
            stockout_days = sku_data.get('kentucky_stockout_days', 0)
            burnaby_stockout_days = sku_data.get('burnaby_stockout_days', 0)
            abc_class = sku_data.get('abc_code', 'C')
            xyz_class = sku_data.get('xyz_code', 'Z')
            transfer_multiple = sku_data.get('transfer_multiple', 50)

            # Step 1: Get pending orders data
            pending_data = self.get_pending_orders_data(sku_id)

            # Step 2: Check for stockout overrides
            kentucky_override = self.check_stockout_override(sku_id, 'kentucky')
            burnaby_override = self.check_stockout_override(sku_id, 'burnaby')

            # Step 3: Apply stockout overrides to quantities
            effective_kentucky_qty = 0 if kentucky_override['is_overridden'] else kentucky_qty
            effective_burnaby_qty = 0 if burnaby_override['is_overridden'] else burnaby_qty

            # Step 4: Calculate enhanced demand for Kentucky
            kentucky_corrected_demand = self.corrector.correct_monthly_demand_enhanced(
                sku_id, kentucky_sales, stockout_days, datetime.now().strftime('%Y-%m')
            )

            # Calculate Burnaby demand for retention calculation
            burnaby_corrected_demand = self.corrector.correct_monthly_demand_enhanced(
                sku_id, burnaby_sales, burnaby_stockout_days, datetime.now().strftime('%Y-%m')
            )

            # Step 5: Calculate Burnaby retention with pending orders
            burnaby_retention = self.calculate_burnaby_retention(
                effective_burnaby_qty, burnaby_corrected_demand, pending_data
            )

            # Step 6: Apply seasonal and growth patterns
            current_month = datetime.now().month
            seasonal_pattern = self.seasonal_detector.detect_seasonal_pattern(sku_id)
            seasonal_multiplier = self.seasonal_detector.get_seasonal_multiplier(seasonal_pattern, current_month)

            growth_status = self.growth_detector.detect_viral_growth(sku_id)
            growth_multiplier = self.growth_detector.get_growth_multiplier(growth_status)

            # Apply enhancements to demand
            enhanced_kentucky_demand = kentucky_corrected_demand * seasonal_multiplier * growth_multiplier

            # Step 7: Calculate target inventory considering pending orders
            coverage_months = self.get_coverage_target(abc_class, xyz_class)
            target_inventory = enhanced_kentucky_demand * coverage_months

            # Account for pending Kentucky orders
            kentucky_pending = pending_data.get('kentucky_pending', 0)
            current_position = effective_kentucky_qty + kentucky_pending

            # Step 8: Calculate transfer need
            transfer_need = max(0, target_inventory - current_position)

            # Step 9: Apply Burnaby availability constraint
            available_from_burnaby = burnaby_retention['available_for_transfer']
            recommended_qty = min(transfer_need, available_from_burnaby)

            # Step 10: Round to multiple and apply minimum threshold
            final_transfer_qty = self.round_to_multiple(recommended_qty, transfer_multiple)

            # Step 11: Calculate priority with comprehensive scoring
            score_data = {
                'kentucky_stockout_days': stockout_days,
                'kentucky_qty': effective_kentucky_qty,
                'corrected_demand': enhanced_kentucky_demand,
                'abc_code': abc_class,
                'growth_status': growth_status
            }
            priority_analysis = self.calculate_priority_score(score_data)

            # Step 12: Calculate coverage metrics
            current_coverage = effective_kentucky_qty / max(enhanced_kentucky_demand, 1)
            coverage_after_transfer = (effective_kentucky_qty + final_transfer_qty) / max(enhanced_kentucky_demand, 1)
            coverage_after_pending = (current_position + final_transfer_qty) / max(enhanced_kentucky_demand, 1)

            # Step 13: Generate comprehensive reason
            reason_factors = {
                'pending_orders': pending_data,
                'stockout_overrides': {
                    'kentucky': kentucky_override,
                    'burnaby': burnaby_override
                },
                'burnaby_retention': burnaby_retention,
                'stockout_days': stockout_days,
                'growth_status': growth_status,
                'seasonal_info': {
                    'pattern': seasonal_pattern,
                    'multiplier': seasonal_multiplier
                },
                'current_coverage': current_coverage,
                'target_coverage': coverage_months,
                'abc_class': abc_class,
                'kentucky_qty': effective_kentucky_qty
            }
            comprehensive_reason = self.generate_comprehensive_transfer_reason(reason_factors)

            # Step 14: Assemble comprehensive result
            result = {
                'sku_id': sku_id,
                'description': sku_data.get('description', ''),

                # Current state
                'current_kentucky_qty': kentucky_qty,
                'effective_kentucky_qty': effective_kentucky_qty,
                'current_burnaby_qty': burnaby_qty,
                'effective_burnaby_qty': effective_burnaby_qty,

                # Pending orders
                'kentucky_pending': kentucky_pending,
                'burnaby_pending': pending_data.get('burnaby_pending', 0),
                'days_until_arrival': pending_data.get('days_until_arrival'),

                # Demand calculations
                'corrected_monthly_demand': round(enhanced_kentucky_demand, 2),
                'seasonal_multiplier': round(seasonal_multiplier, 2),
                'growth_multiplier': round(growth_multiplier, 2),

                # Transfer recommendation
                'recommended_transfer_qty': final_transfer_qty,
                'available_from_burnaby': available_from_burnaby,
                'burnaby_min_retain': burnaby_retention['burnaby_min_retain'],

                # Coverage analysis
                'coverage_months': round(current_coverage, 1),
                'coverage_after_transfer': round(coverage_after_transfer, 1),
                'coverage_after_pending': round(coverage_after_pending, 1),
                'target_coverage_months': coverage_months,

                # Priority and classification
                'priority': priority_analysis['priority_level'],
                'priority_score': priority_analysis.get('total_score', 0),
                'abc_class': abc_class,
                'xyz_class': xyz_class,

                # Additional metadata
                'seasonal_pattern': seasonal_pattern,
                'growth_status': growth_status,
                'stockout_days': stockout_days,
                'transfer_multiple': transfer_multiple,
                'reason': comprehensive_reason,
                'enhanced_calculation': True,
                'pending_orders_included': True,
                'stockout_overrides_applied': kentucky_override['is_overridden'] or burnaby_override['is_overridden'],

                # Override details
                'kentucky_override': kentucky_override,
                'burnaby_override': burnaby_override,
                'burnaby_retention_details': burnaby_retention
            }

            # Update database with detected patterns
            self._update_sku_patterns(sku_id, seasonal_pattern, growth_status)

            return result

        except Exception as e:
            logger.error(f"Comprehensive enhanced calculation failed for SKU {sku_data.get('sku_id', 'unknown')}: {e}")
            # Fallback to existing enhanced calculation
            return self.calculate_enhanced_transfer_recommendation(sku_data)

    def generate_comprehensive_transfer_reason(self, factors: Dict[str, Any]) -> str:
        """
        Generate detailed transfer reason incorporating all enhancement factors

        Args:
            factors: Dictionary containing all reason factors

        Returns:
            Comprehensive reason string
        """
        try:
            reason_parts = []

            # Stockout override information
            kentucky_override = factors.get('stockout_overrides', {}).get('kentucky', {})
            if kentucky_override.get('is_overridden'):
                reason_parts.append("🚨 Kentucky marked as out-of-stock (quantity overridden to 0)")

            # Stockout correction information
            stockout_days = factors.get('stockout_days', 0)
            if stockout_days > 20:
                reason_parts.append(f"📊 Severe stockout correction applied ({stockout_days} days out)")
            elif stockout_days > 10:
                reason_parts.append(f"📊 Stockout correction applied ({stockout_days} days out)")

            # Pending orders impact
            pending_orders = factors.get('pending_orders', {})
            kentucky_pending = pending_orders.get('kentucky_pending', 0)
            days_until_arrival = pending_orders.get('days_until_arrival')

            if kentucky_pending > 0 and days_until_arrival:
                if days_until_arrival < 15:
                    reason_parts.append(f"📦 Pending order ({kentucky_pending} units) arriving in {days_until_arrival} days")
                elif days_until_arrival < 45:
                    reason_parts.append(f"📦 Pending order ({kentucky_pending} units) arriving in {days_until_arrival} days")

            # Burnaby retention impact
            burnaby_retention = factors.get('burnaby_retention', {})
            retention_reason = burnaby_retention.get('retention_reason', '')
            if 'Reduced retention' in retention_reason:
                reason_parts.append("🏭 Burnaby retention reduced due to imminent pending arrival")

            # Growth pattern
            growth_status = factors.get('growth_status', 'normal')
            if growth_status == 'viral':
                reason_parts.append("📈 Viral growth detected - increased priority")
            elif growth_status == 'declining':
                reason_parts.append("📉 Declining trend noted")

            # Seasonal information
            seasonal_info = factors.get('seasonal_info', {})
            seasonal_pattern = seasonal_info.get('pattern', 'year_round')
            seasonal_multiplier = seasonal_info.get('multiplier', 1.0)

            if seasonal_pattern != 'year_round' and seasonal_multiplier > 1.1:
                reason_parts.append(f"🌟 Seasonal peak approaching ({seasonal_pattern} pattern)")

            # Coverage analysis
            current_coverage = factors.get('current_coverage', 0)
            target_coverage = factors.get('target_coverage', 6)
            abc_class = factors.get('abc_class', 'C')

            if factors.get('kentucky_qty', 0) == 0:
                reason_parts.append("🔴 Currently out of stock")
            elif current_coverage < 1:
                reason_parts.append(f"⚠️ Below 1 month coverage (Class {abc_class}: target {target_coverage:.1f} months)")
            elif current_coverage < target_coverage:
                reason_parts.append(f"📊 Below target coverage (Class {abc_class}: target {target_coverage:.1f} months)")

            # Combine all reasons
            if reason_parts:
                return " | ".join(reason_parts)
            else:
                return "📊 Maintain optimal stock level with pending orders consideration"

        except Exception as e:
            logger.error(f"Failed to generate comprehensive reason: {e}")
            return "📊 Enhanced transfer calculation with pending orders"

    def _calculate_enhanced_priority(self, kentucky_qty: int, enhanced_demand: float,
                                   growth_status: str, seasonal_pattern: str, stockout_days: int) -> str:
        """
        Calculate priority with enhanced factors

        Args:
            kentucky_qty: Current Kentucky quantity
            enhanced_demand: Enhanced demand calculation
            growth_status: Growth status (viral, normal, declining)
            seasonal_pattern: Seasonal pattern
            stockout_days: Stockout days

        Returns:
            Priority level string
        """
        if kentucky_qty == 0:
            return "CRITICAL"

        # Calculate coverage in months
        coverage_months = kentucky_qty / max(enhanced_demand, 1)

        # Base priority on coverage
        if coverage_months < 0.5:
            base_priority = "CRITICAL"
        elif coverage_months < 1.0:
            base_priority = "HIGH"
        elif coverage_months < 2.0:
            base_priority = "MEDIUM"
        else:
            base_priority = "LOW"

        # Upgrade priority for special cases
        if growth_status == 'viral' and base_priority != "CRITICAL":
            # Upgrade viral products by one level
            priority_upgrade = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "CRITICAL"}
            base_priority = priority_upgrade.get(base_priority, base_priority)

        if stockout_days > 15 and base_priority in ["MEDIUM", "LOW"]:
            # Upgrade items with long stockout history
            base_priority = "HIGH"

        return base_priority

    def _generate_enhanced_reason(self, base_reason: str, seasonal_pattern: str, growth_status: str,
                                seasonal_multiplier: float, growth_multiplier: float) -> str:
        """
        Generate enhanced reason string with pattern information

        Args:
            base_reason: Original reason
            seasonal_pattern: Detected seasonal pattern
            growth_status: Growth status
            seasonal_multiplier: Seasonal adjustment factor
            growth_multiplier: Growth adjustment factor

        Returns:
            Enhanced reason string
        """
        reason_parts = [base_reason]

        # Add seasonal information
        if seasonal_pattern != 'year_round' and seasonal_multiplier != 1.0:
            if seasonal_multiplier > 1.1:
                reason_parts.append(f"Seasonal peak period ({seasonal_pattern})")
            elif seasonal_multiplier < 0.9:
                reason_parts.append(f"Seasonal low period ({seasonal_pattern})")

        # Add growth information
        if growth_status == 'viral':
            reason_parts.append("Viral growth detected (2x recent demand)")
        elif growth_status == 'declining':
            reason_parts.append("Declining trend detected")

        # Add adjustment information if significant
        total_adjustment = seasonal_multiplier * growth_multiplier
        if total_adjustment > 1.2:
            reason_parts.append(f"Demand adjusted up {(total_adjustment-1)*100:.0f}%")
        elif total_adjustment < 0.8:
            reason_parts.append(f"Demand adjusted down {(1-total_adjustment)*100:.0f}%")

        return "; ".join(reason_parts)

    def get_seasonal_pre_positioning(self, sku_id: str, seasonal_pattern: str, current_month: int) -> Dict[str, Any]:
        """
        Determine if SKU needs seasonal pre-positioning for upcoming peak seasons

        Args:
            sku_id: SKU identifier
            seasonal_pattern: Detected seasonal pattern
            current_month: Current month (1-12)

        Returns:
            Dictionary with pre-positioning recommendation
        """
        try:
            # Define peak months for each seasonal pattern
            peak_months = {
                'spring_summer': [4, 5, 6, 7],  # Apr-Jul
                'fall_winter': [10, 11, 12, 1, 2],  # Oct-Feb
                'holiday': [11, 12],  # Nov-Dec
                'year_round': []  # No specific peaks
            }

            if seasonal_pattern not in peak_months:
                return {'needs_pre_positioning': False, 'reason': 'No seasonal pattern detected'}

            peaks = peak_months[seasonal_pattern]
            if not peaks:
                return {'needs_pre_positioning': False, 'reason': 'Year-round demand pattern'}

            # Check if we're 1-2 months before a peak
            needs_positioning = False
            upcoming_peak = None
            months_ahead = 0

            for peak_month in peaks:
                # Calculate months ahead (handle year wrap-around)
                if peak_month >= current_month:
                    diff = peak_month - current_month
                else:
                    diff = (12 - current_month) + peak_month

                # Pre-position 1-2 months ahead
                if 1 <= diff <= 2:
                    needs_positioning = True
                    upcoming_peak = peak_month
                    months_ahead = diff
                    break

            if needs_positioning:
                season_name = seasonal_pattern.replace('_', ' ').title()
                peak_month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][upcoming_peak]

                return {
                    'needs_pre_positioning': True,
                    'seasonal_pattern': seasonal_pattern,
                    'upcoming_peak_month': upcoming_peak,
                    'months_ahead': months_ahead,
                    'reason': f"Pre-position for {season_name} season (peak in {peak_month_name})",
                    'multiplier': 1.3 if months_ahead == 1 else 1.2  # Stronger positioning closer to peak
                }
            else:
                return {'needs_pre_positioning': False, 'reason': 'No upcoming seasonal peak within 2 months'}

        except Exception as e:
            logger.error(f"Seasonal pre-positioning check failed for {sku_id}: {e}")
            return {'needs_pre_positioning': False, 'reason': 'Error in seasonal analysis'}

    def generate_detailed_transfer_reason(self, factors: Dict[str, Any]) -> str:
        """
        Generate detailed, contextual transfer reason with business justification

        Args:
            factors: Dictionary containing various factors affecting the transfer decision
                - base_reason: Original transfer reason
                - stockout_days: Number of stockout days
                - growth_status: Growth classification (viral, normal, declining)
                - seasonal_info: Pre-positioning information
                - current_coverage: Coverage months
                - abc_class: ABC classification
                - kentucky_qty: Current Kentucky quantity

        Returns:
            Detailed transfer reason string
        """
        try:
            reason_components = []

            # Start with urgency level based on current stock
            kentucky_qty = factors.get('kentucky_qty', 0)
            if kentucky_qty == 0:
                reason_components.append("CRITICAL: Currently out of stock")
            elif factors.get('current_coverage', 0) < 0.5:
                reason_components.append("URGENT: Less than 2 weeks coverage remaining")

            # Add stockout impact
            stockout_days = factors.get('stockout_days', 0)
            if stockout_days > 0:
                if stockout_days >= 20:
                    reason_components.append(f"Severe stockout impact: {stockout_days} days out of stock last month")
                elif stockout_days >= 10:
                    reason_components.append(f"Moderate stockout impact: {stockout_days} days out of stock")
                else:
                    reason_components.append(f"Recent stockout: {stockout_days} days affected")

            # Add seasonal pre-positioning
            seasonal_info = factors.get('seasonal_info', {})
            if seasonal_info.get('needs_pre_positioning'):
                reason_components.append(seasonal_info['reason'])

            # Add growth context
            growth_status = factors.get('growth_status', 'normal')
            if growth_status == 'viral':
                reason_components.append("High priority: Viral growth detected (2x+ demand increase)")
            elif growth_status == 'declining':
                reason_components.append("Trend alert: Declining demand pattern")

            # Add business importance context
            abc_class = factors.get('abc_class', 'C')
            if abc_class == 'A':
                reason_components.append("High-value item (Class A)")

            # Add coverage context if relevant
            coverage = factors.get('current_coverage', 0)
            target_coverage = factors.get('target_coverage', 6)
            if coverage < target_coverage * 0.5:
                reason_components.append(f"Below minimum coverage (target: {target_coverage:.1f} months)")

            # Fallback to base reason if no specific components
            if not reason_components and factors.get('base_reason'):
                reason_components.append(factors['base_reason'])

            # Join components with proper formatting
            if not reason_components:
                return "Maintain optimal inventory levels"

            return " | ".join(reason_components)

        except Exception as e:
            logger.error(f"Failed to generate detailed transfer reason: {e}")
            return factors.get('base_reason', 'Transfer recommended')

    def calculate_priority_score(self, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate weighted priority score for stockout-affected SKUs

        Args:
            sku_data: Dictionary containing SKU information including:
                - kentucky_stockout_days: Stockout days
                - kentucky_qty: Current Kentucky quantity
                - corrected_demand: Monthly corrected demand
                - abc_code: ABC classification
                - growth_status: Growth status
                - last_stockout_date: Most recent stockout date

        Returns:
            Dictionary with priority score and breakdown
        """
        try:
            # Initialize scoring components
            stockout_score = 0
            coverage_score = 0
            abc_score = 0
            growth_score = 0

            # 1. Stockout Days Score (40% weight) - 0-40 points
            stockout_days = sku_data.get('kentucky_stockout_days', 0)
            if stockout_days >= 25:
                stockout_score = 40  # Severe stockout
            elif stockout_days >= 15:
                stockout_score = 32  # Major stockout
            elif stockout_days >= 10:
                stockout_score = 24  # Moderate stockout
            elif stockout_days >= 5:
                stockout_score = 16  # Minor stockout
            elif stockout_days > 0:
                stockout_score = 8   # Minimal stockout
            # 0 stockout days = 0 points

            # 2. Coverage Ratio Score (30% weight) - 0-30 points
            kentucky_qty = sku_data.get('kentucky_qty', 0)
            corrected_demand = sku_data.get('corrected_demand', 1)

            if kentucky_qty == 0:
                coverage_score = 30  # Out of stock
            else:
                coverage_months = kentucky_qty / max(corrected_demand, 1)
                if coverage_months < 0.5:
                    coverage_score = 25  # Less than 2 weeks
                elif coverage_months < 1.0:
                    coverage_score = 20  # Less than 1 month
                elif coverage_months < 2.0:
                    coverage_score = 15  # Less than 2 months
                elif coverage_months < 4.0:
                    coverage_score = 10  # Less than 4 months
                else:
                    coverage_score = 0   # Adequate coverage

            # 3. ABC Classification Score (20% weight) - 0-20 points
            abc_code = sku_data.get('abc_code', 'C')
            abc_scores = {'A': 20, 'B': 12, 'C': 5}
            abc_score = abc_scores.get(abc_code, 5)

            # 4. Growth Status Score (10% weight) - 0-10 points
            growth_status = sku_data.get('growth_status', 'normal')
            growth_scores = {'viral': 10, 'normal': 5, 'declining': 0}
            growth_score = growth_scores.get(growth_status, 5)

            # Calculate total score
            total_score = stockout_score + coverage_score + abc_score + growth_score

            # Convert score to priority level
            if total_score >= 80:
                priority_level = "CRITICAL"
            elif total_score >= 60:
                priority_level = "HIGH"
            elif total_score >= 40:
                priority_level = "MEDIUM"
            else:
                priority_level = "LOW"

            return {
                'total_score': total_score,
                'priority_level': priority_level,
                'score_breakdown': {
                    'stockout_score': stockout_score,
                    'coverage_score': coverage_score,
                    'abc_score': abc_score,
                    'growth_score': growth_score
                },
                'score_details': {
                    'stockout_days': stockout_days,
                    'coverage_months': round(kentucky_qty / max(corrected_demand, 1), 1),
                    'abc_class': abc_code,
                    'growth_status': growth_status
                }
            }

        except Exception as e:
            logger.error(f"Priority score calculation failed for SKU {sku_data.get('sku_id', 'unknown')}: {e}")
            return {
                'total_score': 50,
                'priority_level': "MEDIUM",
                'score_breakdown': {'error': str(e)},
                'score_details': {}
            }

    def _update_sku_patterns(self, sku_id: str, seasonal_pattern: str, growth_status: str):
        """
        Update SKU record with detected patterns

        Args:
            sku_id: SKU identifier
            seasonal_pattern: Detected seasonal pattern
            growth_status: Growth status
        """
        try:
            update_query = """
            UPDATE skus
            SET seasonal_pattern = %s, growth_status = %s, updated_at = NOW()
            WHERE sku_id = %s
            """

            db = database.get_database_connection()
            cursor = db.cursor()
            cursor.execute(update_query, (seasonal_pattern, growth_status, sku_id))
            db.close()

            logger.debug(f"Updated patterns for {sku_id}: {seasonal_pattern}, {growth_status}")

        except Exception as e:
            logger.error(f"Failed to update patterns for {sku_id}: {e}")

    def consolidate_discontinued_items(self) -> List[Dict[str, Any]]:
        """
        Generate consolidation recommendations for discontinued items

        Returns:
            List of consolidation recommendations
        """
        try:
            # Get discontinued items with inventory in both warehouses
            query = """
            SELECT
                s.sku_id,
                s.description,
                ic.burnaby_qty,
                ic.kentucky_qty,
                s.cost_per_unit,
                COALESCE(ms.kentucky_sales, 0) as recent_kentucky_sales,
                COALESCE(ms.burnaby_sales, 0) as recent_burnaby_sales
            FROM skus s
            INNER JOIN inventory_current ic ON s.sku_id = ic.sku_id
            LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id AND ms.year_month = '2024-03'
            WHERE s.status IN ('Death Row', 'Discontinued')
                AND ic.burnaby_qty > 0
                AND ic.kentucky_qty > 0
            ORDER BY (ic.kentucky_qty * s.cost_per_unit) DESC
            """

            discontinued_items = database.execute_query(query)
            recommendations = []

            for item in discontinued_items:
                # Determine consolidation direction based on recent sales
                kentucky_sales = item['recent_kentucky_sales'] or 0
                burnaby_sales = item['recent_burnaby_sales'] or 0

                if kentucky_sales >= burnaby_sales:
                    # Keep in Kentucky, transfer from Burnaby
                    transfer_qty = item['burnaby_qty']
                    destination = "Kentucky"
                    reason = f"Consolidate discontinued item to higher-selling warehouse (KY: {kentucky_sales}, BC: {burnaby_sales})"
                else:
                    # Keep in Burnaby, no transfer needed (this tool focuses on transfers to Kentucky)
                    continue

                recommendations.append({
                    'sku_id': item['sku_id'],
                    'description': item['description'],
                    'consolidation_type': 'discontinued',
                    'recommended_transfer_qty': transfer_qty,
                    'destination': destination,
                    'reason': reason,
                    'priority': 'MEDIUM',
                    'current_kentucky_qty': item['kentucky_qty'],
                    'current_burnaby_qty': item['burnaby_qty'],
                    'value_impact': round(transfer_qty * (item['cost_per_unit'] or 0), 2)
                })

            logger.info(f"Generated {len(recommendations)} discontinued item consolidation recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"Discontinued item consolidation failed: {e}")
            return []

def calculate_all_transfer_recommendations(use_enhanced: bool = True) -> List[Dict[str, Any]]:
    """
    Calculate transfer recommendations for all active SKUs using enhanced or basic calculations

    Args:
        use_enhanced: Whether to use enhanced calculations with seasonal/growth analysis

    Returns:
        List of transfer recommendations sorted by priority
    """
    try:
        # Get all active SKUs with current inventory and latest sales for BOTH warehouses
        query = """
        SELECT
            s.sku_id,
            s.description,
            s.abc_code,
            s.xyz_code,
            s.transfer_multiple,
            ic.burnaby_qty,
            ic.kentucky_qty,
            COALESCE(ms.kentucky_sales, 0) as kentucky_sales,
            COALESCE(ms.kentucky_stockout_days, 0) as kentucky_stockout_days,
            COALESCE(ms.burnaby_sales, 0) as burnaby_sales,
            COALESCE(ms.burnaby_stockout_days, 0) as burnaby_stockout_days
        FROM skus s
        LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
        LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id AND ms.`year_month` = '2024-03'
        WHERE s.status = 'Active'
        ORDER BY s.sku_id
        """
        
        sku_data_list = database.execute_query(query)
        
        if not sku_data_list:
            return []
        
        calculator = TransferCalculator()
        recommendations = []

        for sku_data in sku_data_list:
            # Use the new economic validation method to prevent stockouts
            recommendation = calculator.calculate_enhanced_transfer_with_economic_validation(sku_data)

            if recommendation:
                recommendations.append(recommendation)
        
        # Sort by priority (CRITICAL -> HIGH -> MEDIUM -> LOW)
        priority_order = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
        recommendations.sort(key=lambda x: (
            priority_order.get(x['priority'], 5),
            -x['corrected_monthly_demand']  # Higher demand first within same priority
        ))
        
        logger.info(f"Generated {len(recommendations)} transfer recommendations")
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to calculate transfer recommendations: {e}")
        raise

def update_abc_xyz_classifications():
    """
    Update ABC-XYZ classifications for all SKUs based on recent sales data
    This would typically be run monthly after new sales data is imported
    """
    try:
        # Get sales data for classification
        sales_query = """
        SELECT 
            s.sku_id,
            s.cost_per_unit,
            ms.kentucky_sales,
            ms.`year_month`
        FROM skus s
        LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id
        WHERE s.status = 'Active'
            AND ms.`year_month` >= '2024-01'  # Last 3 months
        ORDER BY s.sku_id, ms.`year_month`
        """
        
        sales_data = database.execute_query(sales_query)
        
        # Group by SKU
        sku_sales = {}
        for row in sales_data:
            sku_id = row['sku_id']
            if sku_id not in sku_sales:
                sku_sales[sku_id] = {
                    'cost_per_unit': row['cost_per_unit'] or 0,
                    'sales': []
                }
            sku_sales[sku_id]['sales'].append(row['kentucky_sales'] or 0)
        
        classifier = ABCXYZClassifier()
        
        # Calculate total annual value for ABC classification
        total_annual_value = 0
        for sku_data in sku_sales.values():
            annual_sales = sum(sku_data['sales']) * 4  # Extrapolate from 3 months
            annual_value = annual_sales * sku_data['cost_per_unit']
            total_annual_value += annual_value
        
        # Update classifications
        for sku_id, sku_data in sku_sales.items():
            annual_sales = sum(sku_data['sales']) * 4
            annual_value = annual_sales * sku_data['cost_per_unit']
            
            abc_class = classifier.classify_abc(annual_value, total_annual_value)
            xyz_class = classifier.classify_xyz(sku_data['sales'])
            
            # Update database
            update_query = """
            UPDATE skus 
            SET abc_code = %s, xyz_code = %s, updated_at = NOW()
            WHERE sku_id = %s
            """
            
            db = database.get_database_connection()
            cursor = db.cursor()
            cursor.execute(update_query, (abc_class, xyz_class, sku_id))
            db.close()
        
        logger.info(f"Updated ABC-XYZ classifications for {len(sku_sales)} SKUs")
        return True

    except Exception as e:
        logger.error(f"Failed to update ABC-XYZ classifications: {e}")
        return False


def update_all_seasonal_and_growth_patterns():
    """
    Update seasonal patterns and growth status for all active SKUs
    This should be run monthly after new sales data is imported
    """
    try:
        # Get all active SKUs
        query = """
        SELECT sku_id FROM skus WHERE status = 'Active' ORDER BY sku_id
        """

        sku_list = database.execute_query(query)
        if not sku_list:
            logger.warning("No active SKUs found for pattern update")
            return False

        detector = SeasonalPatternDetector()
        growth_detector = ViralGrowthDetector()
        updated_count = 0

        for sku_record in sku_list:
            sku_id = sku_record['sku_id']

            try:
                # Detect patterns
                seasonal_pattern = detector.detect_seasonal_pattern(sku_id)
                growth_status = growth_detector.detect_viral_growth(sku_id)

                # Update database
                update_query = """
                UPDATE skus
                SET seasonal_pattern = %s, growth_status = %s, updated_at = NOW()
                WHERE sku_id = %s
                """

                db = database.get_database_connection()
                cursor = db.cursor()
                cursor.execute(update_query, (seasonal_pattern, growth_status, sku_id))
                db.close()

                updated_count += 1
                logger.debug(f"Updated patterns for {sku_id}: {seasonal_pattern}, {growth_status}")

            except Exception as e:
                logger.error(f"Failed to update patterns for {sku_id}: {e}")
                continue

        logger.info(f"Updated seasonal and growth patterns for {updated_count} SKUs")
        return True

    except Exception as e:
        logger.error(f"Failed to update seasonal and growth patterns: {e}")
        return False


def test_enhanced_calculations():
    """
    Test the enhanced calculation system with sample data
    Returns test results for validation
    """
    try:
        logger.info("Starting enhanced calculation tests...")

        # Test 1: Year-over-year lookup
        corrector = StockoutCorrector()
        yoy_result = corrector.get_same_month_last_year('CHG-001', '2024-03')
        logger.info(f"Test 1 - Year-over-year lookup for CHG-001: {yoy_result}")

        # Test 2: Category average
        category_result = corrector.get_category_average('CHG-001')
        logger.info(f"Test 2 - Category average for CHG-001: {category_result}")

        # Test 3: Enhanced correction for zero sales with stockout
        enhanced_result = corrector.correct_monthly_demand_enhanced('CHG-001', 0, 25, '2024-03')
        logger.info(f"Test 3 - Enhanced correction (0 sales, 25 stockout days): {enhanced_result}")

        # Test 4: Seasonal pattern detection
        seasonal_detector = SeasonalPatternDetector()
        seasonal_pattern = seasonal_detector.detect_seasonal_pattern('CHG-001')
        logger.info(f"Test 4 - Seasonal pattern for CHG-001: {seasonal_pattern}")

        # Test 5: Viral growth detection
        growth_detector = ViralGrowthDetector()
        growth_status = growth_detector.detect_viral_growth('CHG-001')
        logger.info(f"Test 5 - Growth status for CHG-001: {growth_status}")

        # Test 6: Enhanced transfer recommendation
        calculator = TransferCalculator()
        sample_sku_data = {
            'sku_id': 'CHG-001',
            'description': 'USB-C Fast Charger 65W',
            'burnaby_qty': 500,
            'kentucky_qty': 0,
            'kentucky_sales': 0,
            'kentucky_stockout_days': 25,
            'abc_code': 'A',
            'xyz_code': 'X',
            'transfer_multiple': 25
        }

        enhanced_recommendation = calculator.calculate_enhanced_transfer_recommendation(sample_sku_data)
        logger.info(f"Test 6 - Enhanced recommendation for CHG-001: {enhanced_recommendation}")

        # Test 7: Performance test with multiple calculations
        start_time = datetime.now()
        test_recommendations = calculate_all_transfer_recommendations(use_enhanced=True)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"Test 7 - Performance test: {len(test_recommendations)} recommendations in {duration:.2f}s")

        test_results = {
            'yoy_lookup': yoy_result,
            'category_average': category_result,
            'enhanced_correction': enhanced_result,
            'seasonal_pattern': seasonal_pattern,
            'growth_status': growth_status,
            'enhanced_recommendation': enhanced_recommendation is not None,
            'performance_test': {
                'recommendations_count': len(test_recommendations),
                'duration_seconds': duration,
                'meets_target': duration < 5.0  # Target: <5 seconds
            }
        }

        logger.info("Enhanced calculation tests completed successfully")
        return test_results

    except Exception as e:
        logger.error(f"Enhanced calculation tests failed: {e}")
        return {'error': str(e)}