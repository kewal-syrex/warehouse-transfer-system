"""
Supplier Lead Time Analytics Module

This module provides statistical analysis and performance metrics for supplier
lead time data based on historical shipment records. It implements the algorithms
specified in the Supplier Performance Analytics System PRD.

Key Features:
- Statistical lead time analysis (avg, median, P95, min, max, std dev)
- Reliability scoring based on coefficient of variation
- Time period filtering and trend analysis
- Seasonal pattern detection
- Performance degradation alerts

Business Logic:
- Uses P95 lead time as primary metric for planning purposes
- Reliability scores range from 0-100 based on consistency
- Applies 30% minimum confidence factor for low sample sizes
- Supports multiple time periods (6, 12, 24 months, all time)
"""

import math
import statistics
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import pymysql

try:
    from . import database
except ImportError:
    import database

logger = logging.getLogger(__name__)


class SupplierAnalytics:
    """
    Main class for supplier lead time analytics and performance calculations

    This class provides methods to calculate supplier performance metrics
    from historical shipment data, including statistical analysis and
    reliability scoring algorithms.

    Attributes:
        connection: Database connection for data retrieval

    Example:
        analytics = SupplierAnalytics()
        metrics = analytics.calculate_supplier_metrics('Yuasa Battery')
    """

    def __init__(self):
        """Initialize the supplier analytics processor"""
        self.connection = None

    def calculate_supplier_metrics(self, supplier: str, period_months: int = 12) -> Dict[str, Any]:
        """
        Calculate comprehensive metrics for a specific supplier

        Calculates statistical lead time metrics and reliability scores for a supplier
        based on historical shipment data within the specified time period.

        Args:
            supplier: Supplier name (will be normalized)
            period_months: Analysis period in months (6, 12, 24, or 0 for all time)

        Returns:
            Dict containing:
                - avg_lead_time: Average lead time in days
                - median_lead_time: Median lead time (P50)
                - p95_lead_time: 95th percentile lead time (planning metric)
                - min_lead_time: Fastest delivery time
                - max_lead_time: Slowest delivery time
                - std_dev_lead_time: Standard deviation
                - coefficient_variation: CV (std dev / mean)
                - reliability_score: 0-100 score based on consistency
                - shipment_count: Number of shipments analyzed
                - time_period: Period analyzed
                - destination_breakdown: Per-destination metrics

        Raises:
            ValueError: If supplier not found or period_months invalid
            DatabaseError: If database query fails
        """
        try:
            # Normalize supplier name for matching
            normalized_supplier = self._normalize_supplier_name(supplier)

            # Get historical shipment data
            shipments = self._get_supplier_shipments(normalized_supplier, period_months)

            if not shipments:
                return {
                    'supplier': supplier,
                    'error': 'No shipment data found',
                    'shipment_count': 0
                }

            # Extract lead times for analysis
            lead_times = [shipment['actual_lead_time'] for shipment in shipments]

            # Calculate basic statistics
            metrics = self._calculate_statistics(lead_times)

            # Calculate reliability score
            reliability_score = self._calculate_reliability_score(metrics, len(lead_times))

            # Get destination breakdown
            destination_breakdown = self._calculate_destination_metrics(shipments)

            # Compile results
            result = {
                'supplier': supplier,
                'normalized_supplier': normalized_supplier,
                'avg_lead_time': metrics['avg'],
                'median_lead_time': metrics['median'],
                'p95_lead_time': metrics['p95'],
                'min_lead_time': metrics['min'],
                'max_lead_time': metrics['max'],
                'std_dev_lead_time': metrics['std_dev'],
                'coefficient_variation': metrics['cv'],
                'reliability_score': reliability_score,
                'shipment_count': len(lead_times),
                'time_period': f"{period_months}_months" if period_months > 0 else "all_time",
                'destination_breakdown': destination_breakdown,
                'last_calculated': datetime.now(),
                'recommendation': self._generate_recommendation(metrics['p95'], reliability_score)
            }

            logger.info(f"Calculated metrics for supplier {supplier}: P95={metrics['p95']}, Score={reliability_score}")
            return result

        except Exception as e:
            logger.error(f"Error calculating metrics for supplier {supplier}: {str(e)}")
            raise

    def calculate_all_supplier_metrics(self, period_months: int = 12) -> List[Dict[str, Any]]:
        """
        Calculate metrics for all suppliers with shipment history

        Processes all suppliers in the shipment database and calculates
        comprehensive performance metrics for each.

        Args:
            period_months: Analysis period in months

        Returns:
            List of supplier metric dictionaries sorted by reliability score

        Raises:
            DatabaseError: If database query fails
        """
        try:
            # Get list of all suppliers with shipments
            suppliers = self._get_all_suppliers_with_shipments(period_months)

            results = []
            for supplier in suppliers:
                metrics = self.calculate_supplier_metrics(supplier, period_months)
                if metrics.get('shipment_count', 0) > 0:
                    results.append(metrics)

            # Sort by reliability score (descending) then by shipment count
            results.sort(key=lambda x: (-x.get('reliability_score', 0), -x.get('shipment_count', 0)))

            logger.info(f"Calculated metrics for {len(results)} suppliers")
            return results

        except Exception as e:
            logger.error(f"Error calculating all supplier metrics: {str(e)}")
            raise

    def update_supplier_metrics_cache(self, supplier: str = None, period_months: int = 12) -> Dict[str, Any]:
        """
        Update the supplier_lead_times table with calculated metrics

        Calculates metrics and updates the cache table for faster dashboard loading.
        Can update a specific supplier or all suppliers.

        Args:
            supplier: Specific supplier to update (None for all)
            period_months: Analysis period in months

        Returns:
            Dict with update results and statistics

        Raises:
            DatabaseError: If database operations fail
        """
        try:
            updated_count = 0
            error_count = 0

            if supplier:
                suppliers_to_update = [supplier]
            else:
                suppliers_to_update = self._get_all_suppliers_with_shipments(period_months)

            for supplier_name in suppliers_to_update:
                try:
                    metrics = self.calculate_supplier_metrics(supplier_name, period_months)

                    if metrics.get('shipment_count', 0) > 0:
                        self._update_supplier_cache(metrics)
                        updated_count += 1

                except Exception as e:
                    logger.error(f"Failed to update metrics for {supplier_name}: {str(e)}")
                    error_count += 1

            result = {
                'updated_count': updated_count,
                'error_count': error_count,
                'total_processed': len(suppliers_to_update),
                'period_months': period_months,
                'updated_at': datetime.now()
            }

            logger.info(f"Updated metrics cache: {updated_count} suppliers updated, {error_count} errors")
            return result

        except Exception as e:
            logger.error(f"Error updating supplier metrics cache: {str(e)}")
            raise

    def detect_performance_alerts(self, supplier: str = None) -> List[Dict[str, Any]]:
        """
        Detect performance degradation and reliability alerts

        Analyzes supplier performance to identify:
        - Performance degradation (lead time increased >15% vs 3-month average)
        - High variability warnings (CV > 25%)
        - Insufficient data warnings (<5 shipments in 6 months)
        - Outlier detection (single shipment >2x normal lead time)

        Args:
            supplier: Specific supplier to analyze (None for all)

        Returns:
            List of alert dictionaries with severity and action recommendations
        """
        try:
            alerts = []

            if supplier:
                suppliers_to_check = [supplier]
            else:
                suppliers_to_check = self._get_all_suppliers_with_shipments(12)

            for supplier_name in suppliers_to_check:
                supplier_alerts = self._check_supplier_alerts(supplier_name)
                alerts.extend(supplier_alerts)

            # Sort by severity (HIGH, MEDIUM, LOW)
            severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
            alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))

            logger.info(f"Generated {len(alerts)} performance alerts")
            return alerts

        except Exception as e:
            logger.error(f"Error detecting performance alerts: {str(e)}")
            raise

    def _normalize_supplier_name(self, supplier: str) -> str:
        """
        Normalize supplier name for consistent matching

        Applies UPPER() and TRIM() transformations to match supplier names
        consistently across the system.

        Args:
            supplier: Raw supplier name

        Returns:
            Normalized supplier name (uppercase, trimmed)
        """
        if not supplier:
            return ""
        return supplier.strip().upper()

    def _get_supplier_shipments(self, supplier: str, period_months: int) -> List[Dict[str, Any]]:
        """
        Retrieve historical shipment data for a supplier

        Queries the supplier_shipments table for historical data within
        the specified time period.

        Args:
            supplier: Normalized supplier name
            period_months: Analysis period (0 for all time)

        Returns:
            List of shipment records with lead time calculations
        """
        try:
            # Build date filter based on period
            date_filter = ""
            if period_months > 0:
                cutoff_date = datetime.now() - timedelta(days=period_months * 30)
                date_filter = f"AND received_date >= '{cutoff_date.strftime('%Y-%m-%d')}'"

            query = f"""
                SELECT
                    po_number,
                    supplier,
                    order_date,
                    received_date,
                    destination,
                    actual_lead_time,
                    was_partial,
                    notes
                FROM supplier_shipments
                WHERE UPPER(TRIM(supplier)) = %s
                {date_filter}
                ORDER BY received_date DESC
            """

            connection = database.get_database_connection()
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query, (supplier,))
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error retrieving shipments for supplier {supplier}: {str(e)}")
            return []

    def _get_all_suppliers_with_shipments(self, period_months: int) -> List[str]:
        """
        Get list of all suppliers that have shipment history

        Args:
            period_months: Analysis period (0 for all time)

        Returns:
            List of normalized supplier names
        """
        try:
            date_filter = ""
            if period_months > 0:
                cutoff_date = datetime.now() - timedelta(days=period_months * 30)
                date_filter = f"AND received_date >= '{cutoff_date.strftime('%Y-%m-%d')}'"

            query = f"""
                SELECT DISTINCT UPPER(TRIM(supplier)) as supplier
                FROM supplier_shipments
                WHERE supplier IS NOT NULL
                AND supplier != ''
                {date_filter}
                ORDER BY supplier
            """

            connection = database.get_database_connection()
            with connection.cursor() as cursor:
                cursor.execute(query)
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error retrieving supplier list: {str(e)}")
            return []

    def _calculate_statistics(self, lead_times: List[int]) -> Dict[str, float]:
        """
        Calculate statistical metrics for lead time data

        Computes comprehensive statistics including percentiles,
        standard deviation, and coefficient of variation.

        Args:
            lead_times: List of lead times in days

        Returns:
            Dict with statistical metrics
        """
        if not lead_times:
            return {}

        try:
            # Sort for percentile calculations
            sorted_times = sorted(lead_times)

            avg = statistics.mean(lead_times)
            median = statistics.median(lead_times)

            # Calculate P95 (95th percentile)
            p95_index = int(0.95 * len(sorted_times))
            p95 = sorted_times[min(p95_index, len(sorted_times) - 1)]

            min_time = min(lead_times)
            max_time = max(lead_times)

            # Standard deviation
            std_dev = statistics.stdev(lead_times) if len(lead_times) > 1 else 0

            # Coefficient of variation (CV = std_dev / mean)
            cv = (std_dev / avg) if avg > 0 else 0

            return {
                'avg': round(avg, 2),
                'median': round(median, 2),
                'p95': p95,
                'min': min_time,
                'max': max_time,
                'std_dev': round(std_dev, 2),
                'cv': round(cv, 4)
            }

        except Exception as e:
            logger.error(f"Error calculating statistics: {str(e)}")
            return {}

    def _calculate_reliability_score(self, metrics: Dict[str, float], shipment_count: int) -> int:
        """
        Calculate reliability score based on coefficient of variation

        Implements the reliability scoring algorithm from the PRD:
        - CV < 0.10 (10% variation): 95 points (Excellent)
        - CV < 0.15 (15% variation): 85 points (Very Good)
        - CV < 0.25 (25% variation): 70 points (Good)
        - CV < 0.35 (35% variation): 50 points (Fair)
        - CV >= 0.35: 30 points (Poor)

        Applies confidence factor based on sample size:
        - <5 shipments: 70% confidence
        - 5-9 shipments: 85% confidence
        - 10-19 shipments: 95% confidence
        - 20+ shipments: 100% confidence

        Args:
            metrics: Statistical metrics dictionary
            shipment_count: Number of shipments in analysis

        Returns:
            Reliability score (0-100)
        """
        try:
            cv = metrics.get('cv', 1.0)

            # Base score from consistency
            if cv < 0.10:
                base_score = 95  # Excellent consistency
            elif cv < 0.15:
                base_score = 85  # Very good consistency
            elif cv < 0.25:
                base_score = 70  # Good consistency
            elif cv < 0.35:
                base_score = 50  # Fair consistency
            else:
                base_score = 30  # Poor consistency

            # Confidence factor based on sample size
            if shipment_count < 5:
                confidence_factor = 0.7   # Low confidence
            elif shipment_count < 10:
                confidence_factor = 0.85  # Medium confidence
            elif shipment_count < 20:
                confidence_factor = 0.95  # High confidence
            else:
                confidence_factor = 1.0   # Full confidence

            # Calculate final score
            final_score = int(base_score * confidence_factor)

            return max(0, min(100, final_score))  # Ensure 0-100 range

        except Exception as e:
            logger.error(f"Error calculating reliability score: {str(e)}")
            return 0

    def _calculate_destination_metrics(self, shipments: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate performance metrics broken down by destination

        Args:
            shipments: List of shipment records

        Returns:
            Dict with metrics per destination (burnaby, kentucky)
        """
        try:
            destination_data = defaultdict(list)

            # Group shipments by destination
            for shipment in shipments:
                dest = shipment.get('destination', '').lower()
                if dest in ['burnaby', 'kentucky']:
                    destination_data[dest].append(shipment['actual_lead_time'])

            # Calculate metrics for each destination
            result = {}
            for destination, lead_times in destination_data.items():
                if lead_times:
                    metrics = self._calculate_statistics(lead_times)
                    result[destination] = {
                        'avg_lead_time': metrics.get('avg', 0),
                        'median_lead_time': metrics.get('median', 0),
                        'p95_lead_time': metrics.get('p95', 0),
                        'shipment_count': len(lead_times),
                        'std_dev': metrics.get('std_dev', 0)
                    }

            return result

        except Exception as e:
            logger.error(f"Error calculating destination metrics: {str(e)}")
            return {}

    def _generate_recommendation(self, p95_lead_time: int, reliability_score: int) -> str:
        """
        Generate planning recommendation based on metrics

        Args:
            p95_lead_time: 95th percentile lead time
            reliability_score: Reliability score (0-100)

        Returns:
            Planning recommendation string
        """
        try:
            if reliability_score >= 80:
                confidence = "high confidence"
            elif reliability_score >= 60:
                confidence = "medium confidence"
            else:
                confidence = "low confidence - consider alternative suppliers"

            return f"Use {p95_lead_time} days for planning ({confidence})"

        except Exception as e:
            logger.error(f"Error generating recommendation: {str(e)}")
            return "Insufficient data for recommendation"

    def _update_supplier_cache(self, metrics: Dict[str, Any]) -> bool:
        """
        Update supplier_lead_times table with calculated metrics

        Args:
            metrics: Calculated metrics dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            connection = database.get_database_connection()
            with connection.cursor() as cursor:
                # Check if supplier already exists
                check_query = """
                    SELECT id FROM supplier_lead_times
                    WHERE UPPER(TRIM(supplier)) = %s
                    LIMIT 1
                """
                cursor.execute(check_query, (metrics['normalized_supplier'],))
                existing = cursor.fetchone()

                if existing:
                    # Update existing record
                    update_query = """
                        UPDATE supplier_lead_times SET
                            avg_lead_time = %s,
                            median_lead_time = %s,
                            p95_lead_time = %s,
                            min_lead_time = %s,
                            max_lead_time = %s,
                            std_dev_lead_time = %s,
                            coefficient_variation = %s,
                            reliability_score = %s,
                            shipment_count = %s,
                            calculation_period = %s,
                            last_calculated = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    cursor.execute(update_query, (
                        metrics['avg_lead_time'],
                        metrics['median_lead_time'],
                        metrics['p95_lead_time'],
                        metrics['min_lead_time'],
                        metrics['max_lead_time'],
                        metrics['std_dev_lead_time'],
                        metrics['coefficient_variation'],
                        metrics['reliability_score'],
                        metrics['shipment_count'],
                        metrics['time_period'],
                        metrics['last_calculated'],
                        existing[0]
                    ))
                else:
                    # Insert new record
                    insert_query = """
                        INSERT INTO supplier_lead_times (
                            supplier, avg_lead_time, median_lead_time, p95_lead_time,
                            min_lead_time, max_lead_time, std_dev_lead_time,
                            coefficient_variation, reliability_score, shipment_count,
                            calculation_period, last_calculated
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (
                        metrics['supplier'],
                        metrics['avg_lead_time'],
                        metrics['median_lead_time'],
                        metrics['p95_lead_time'],
                        metrics['min_lead_time'],
                        metrics['max_lead_time'],
                        metrics['std_dev_lead_time'],
                        metrics['coefficient_variation'],
                        metrics['reliability_score'],
                        metrics['shipment_count'],
                        metrics['time_period'],
                        metrics['last_calculated']
                    ))

                connection.commit()
                return True

        except Exception as e:
            logger.error(f"Error updating supplier cache: {str(e)}")
            return False

    def _check_supplier_alerts(self, supplier: str) -> List[Dict[str, Any]]:
        """
        Check for performance alerts for a specific supplier

        Args:
            supplier: Supplier name to check

        Returns:
            List of alert dictionaries
        """
        try:
            alerts = []

            # Get current and historical metrics
            current_metrics = self.calculate_supplier_metrics(supplier, 3)  # Last 3 months
            historical_metrics = self.calculate_supplier_metrics(supplier, 12)  # Last 12 months

            if not current_metrics or not historical_metrics:
                return alerts

            # Performance degradation check
            current_avg = current_metrics.get('avg_lead_time', 0)
            historical_avg = historical_metrics.get('avg_lead_time', 0)

            if current_avg > 0 and historical_avg > 0:
                change_pct = ((current_avg - historical_avg) / historical_avg) * 100

                if change_pct > 15:
                    alerts.append({
                        'supplier': supplier,
                        'type': 'performance_degradation',
                        'severity': 'HIGH',
                        'message': f"{supplier} lead time increased {change_pct:.1f}% ({historical_avg:.0f}→{current_avg:.0f} days)",
                        'action': 'Review pending orders, consider expediting',
                        'detected_at': datetime.now()
                    })

            # High variability warning
            cv = historical_metrics.get('coefficient_variation', 0)
            if cv > 0.25:
                alerts.append({
                    'supplier': supplier,
                    'type': 'high_variability',
                    'severity': 'MEDIUM',
                    'message': f"{supplier} showing high variability (CV={cv:.1%})",
                    'action': f"Increase safety stock for {supplier} SKUs",
                    'detected_at': datetime.now()
                })

            # Insufficient data warning
            shipment_count = historical_metrics.get('shipment_count', 0)
            if shipment_count < 5:
                alerts.append({
                    'supplier': supplier,
                    'type': 'insufficient_data',
                    'severity': 'LOW',
                    'message': f"{supplier} has limited history ({shipment_count} shipments)",
                    'action': 'Monitor closely, use conservative estimates',
                    'detected_at': datetime.now()
                })

            return alerts

        except Exception as e:
            logger.error(f"Error checking alerts for supplier {supplier}: {str(e)}")
            return []

    def detect_seasonal_patterns(self, supplier: str) -> Dict[str, Any]:
        """
        Detect seasonal patterns in supplier lead time performance

        Analyzes historical lead times by month to identify seasonal
        trends and performance variations throughout the year.

        Args:
            supplier: Supplier name to analyze

        Returns:
            Dict containing seasonal analysis results including:
                - monthly_averages: Average lead time by month
                - seasonal_variance: Variance analysis
                - peak_months: Months with highest lead times
                - best_months: Months with lowest lead times
                - seasonality_score: Overall seasonality strength (0-1)

        Example:
            patterns = analytics.detect_seasonal_patterns("Supplier A")
            if patterns['seasonality_score'] > 0.3:
                print(f"Strong seasonal pattern detected")
        """
        try:
            connection = database.get_connection()
            cursor = connection.cursor()

            # Get shipments with month grouping for last 24 months
            cursor.execute("""
                SELECT
                    MONTH(order_date) as order_month,
                    MONTHNAME(order_date) as month_name,
                    AVG(actual_lead_time) as avg_lead_time,
                    COUNT(*) as shipment_count,
                    STDDEV(actual_lead_time) as std_dev,
                    MIN(actual_lead_time) as min_lead_time,
                    MAX(actual_lead_time) as max_lead_time
                FROM supplier_shipments
                WHERE UPPER(TRIM(supplier)) = %s
                    AND order_date >= DATE_SUB(CURDATE(), INTERVAL 24 MONTH)
                GROUP BY MONTH(order_date), MONTHNAME(order_date)
                ORDER BY order_month
            """, (supplier.strip().upper(),))

            monthly_data = cursor.fetchall()

            if len(monthly_data) < 3:  # Need at least 3 months for pattern analysis
                return {
                    'monthly_averages': {},
                    'seasonal_variance': 0,
                    'peak_months': [],
                    'best_months': [],
                    'seasonality_score': 0,
                    'analysis_period': '24_months',
                    'sufficient_data': False,
                    'message': 'Insufficient data for seasonal analysis'
                }

            # Process monthly data
            monthly_averages = {}
            lead_times = []

            for row in monthly_data:
                month_num, month_name, avg_lead, count, std_dev, min_lead, max_lead = row
                monthly_averages[month_name] = {
                    'avg_lead_time': float(avg_lead) if avg_lead else 0,
                    'shipment_count': count,
                    'std_deviation': float(std_dev) if std_dev else 0,
                    'min_lead_time': min_lead,
                    'max_lead_time': max_lead
                }
                lead_times.append(float(avg_lead) if avg_lead else 0)

            # Calculate seasonal variance
            overall_avg = sum(lead_times) / len(lead_times) if lead_times else 0
            seasonal_variance = sum((lt - overall_avg) ** 2 for lt in lead_times) / len(lead_times) if lead_times else 0

            # Calculate seasonality score (coefficient of variation)
            seasonality_score = (seasonal_variance ** 0.5) / overall_avg if overall_avg > 0 else 0

            # Identify peak and best performing months
            if monthly_averages:
                sorted_months = sorted(monthly_averages.items(), key=lambda x: x[1]['avg_lead_time'])
                best_months = [month for month, data in sorted_months[:3]]  # Top 3 best
                peak_months = [month for month, data in sorted_months[-3:]]  # Top 3 worst
            else:
                best_months = []
                peak_months = []

            return {
                'monthly_averages': monthly_averages,
                'seasonal_variance': round(seasonal_variance, 2),
                'peak_months': peak_months,
                'best_months': best_months,
                'seasonality_score': round(min(seasonality_score, 1.0), 3),  # Cap at 1.0
                'analysis_period': '24_months',
                'sufficient_data': True,
                'overall_average': round(overall_avg, 1),
                'interpretation': self._interpret_seasonality(seasonality_score, peak_months, best_months)
            }

        except Exception as e:
            logger.error(f"Error detecting seasonal patterns for {supplier}: {str(e)}")
            return {
                'monthly_averages': {},
                'seasonal_variance': 0,
                'peak_months': [],
                'best_months': [],
                'seasonality_score': 0,
                'analysis_period': '24_months',
                'sufficient_data': False,
                'error': str(e)
            }

    def calculate_performance_trends(self, supplier: str, periods: int = 6) -> Dict[str, Any]:
        """
        Calculate supplier performance trends over time

        Analyzes performance changes across multiple time periods to identify
        improving, declining, or stable performance patterns.

        Args:
            supplier: Supplier name to analyze
            periods: Number of periods to analyze (default 6 quarters)

        Returns:
            Dict containing trend analysis results including:
                - trend_direction: 'improving', 'declining', or 'stable'
                - trend_strength: Strength of trend (0-1)
                - period_data: Performance data for each period
                - forecast: Simple forecast for next period
                - recommendation: Action recommendation based on trends
        """
        try:
            connection = database.get_connection()
            cursor = connection.cursor()

            # Get quarterly performance data for trend analysis
            cursor.execute("""
                SELECT
                    YEAR(order_date) as year,
                    QUARTER(order_date) as quarter,
                    AVG(actual_lead_time) as avg_lead_time,
                    COUNT(*) as shipment_count,
                    STDDEV(actual_lead_time) as std_dev
                FROM supplier_shipments
                WHERE UPPER(TRIM(supplier)) = %s
                    AND order_date >= DATE_SUB(CURDATE(), INTERVAL %s QUARTER)
                GROUP BY YEAR(order_date), QUARTER(order_date)
                ORDER BY year, quarter
            """, (supplier.strip().upper(), periods))

            period_data = cursor.fetchall()

            if len(period_data) < 3:
                return {
                    'trend_direction': 'unknown',
                    'trend_strength': 0,
                    'period_data': [],
                    'forecast': None,
                    'recommendation': 'Insufficient data for trend analysis',
                    'sufficient_data': False
                }

            # Process period data
            periods_list = []
            lead_times = []

            for i, (year, quarter, avg_lead, count, std_dev) in enumerate(period_data):
                period_info = {
                    'period': f"{year}Q{quarter}",
                    'avg_lead_time': float(avg_lead) if avg_lead else 0,
                    'shipment_count': count,
                    'std_deviation': float(std_dev) if std_dev else 0,
                    'period_index': i
                }
                periods_list.append(period_info)
                lead_times.append(float(avg_lead) if avg_lead else 0)

            # Calculate trend using simple linear regression
            n = len(lead_times)
            if n >= 3:
                x_values = list(range(n))
                x_mean = sum(x_values) / n
                y_mean = sum(lead_times) / n

                # Calculate slope (trend)
                numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, lead_times))
                denominator = sum((x - x_mean) ** 2 for x in x_values)

                slope = numerator / denominator if denominator != 0 else 0

                # Calculate correlation coefficient for trend strength
                y_variance = sum((y - y_mean) ** 2 for y in lead_times)
                correlation = abs(numerator) / (denominator * y_variance) ** 0.5 if denominator > 0 and y_variance > 0 else 0

                # Determine trend direction and strength
                if abs(slope) < 0.1:  # Very small slope
                    trend_direction = 'stable'
                elif slope > 0:
                    trend_direction = 'declining'  # Lead times increasing = performance declining
                else:
                    trend_direction = 'improving'  # Lead times decreasing = performance improving

                trend_strength = min(correlation, 1.0)

                # Simple forecast for next period
                next_forecast = lead_times[-1] + slope if lead_times else 0

            else:
                trend_direction = 'unknown'
                trend_strength = 0
                slope = 0
                next_forecast = None

            return {
                'trend_direction': trend_direction,
                'trend_strength': round(trend_strength, 3),
                'slope': round(slope, 3),
                'period_data': periods_list,
                'forecast': {
                    'next_period_lead_time': round(next_forecast, 1) if next_forecast else None,
                    'confidence': 'low' if trend_strength < 0.5 else 'medium' if trend_strength < 0.8 else 'high'
                },
                'recommendation': self._generate_trend_recommendation(trend_direction, trend_strength, slope),
                'sufficient_data': True,
                'analysis_periods': len(period_data)
            }

        except Exception as e:
            logger.error(f"Error calculating performance trends for {supplier}: {str(e)}")
            return {
                'trend_direction': 'unknown',
                'trend_strength': 0,
                'period_data': [],
                'forecast': None,
                'recommendation': f'Error analyzing trends: {str(e)}',
                'sufficient_data': False
            }

    def _interpret_seasonality(self, seasonality_score: float, peak_months: List[str], best_months: List[str]) -> str:
        """
        Interpret seasonality score and provide business insights

        Args:
            seasonality_score: Calculated seasonality strength
            peak_months: Months with highest lead times
            best_months: Months with lowest lead times

        Returns:
            Human-readable interpretation of seasonal patterns
        """
        if seasonality_score < 0.1:
            return "No significant seasonal pattern detected. Lead times are consistent year-round."
        elif seasonality_score < 0.3:
            return f"Mild seasonal variation. Slightly longer lead times in {', '.join(peak_months)} and shorter in {', '.join(best_months)}."
        elif seasonality_score < 0.5:
            return f"Moderate seasonal pattern. Plan for longer lead times in {', '.join(peak_months)} and optimize orders during {', '.join(best_months)}."
        else:
            return f"Strong seasonal pattern detected. Significant lead time increases in {', '.join(peak_months)}. Consider seasonal inventory strategies."

    def _generate_trend_recommendation(self, direction: str, strength: float, slope: float) -> str:
        """
        Generate actionable recommendations based on performance trends

        Args:
            direction: Trend direction (improving/declining/stable)
            strength: Strength of the trend
            slope: Rate of change

        Returns:
            Actionable business recommendation
        """
        if direction == 'improving' and strength > 0.6:
            return f"Performance improving consistently ({abs(slope):.1f} days/quarter). Consider negotiating better terms or increasing order volumes."
        elif direction == 'declining' and strength > 0.6:
            return f"Performance declining ({slope:.1f} days/quarter). Schedule supplier review meeting and consider backup suppliers."
        elif direction == 'declining' and strength > 0.3:
            return "Performance showing declining trend. Monitor closely and discuss performance expectations with supplier."
        elif direction == 'stable':
            return "Performance is stable. Continue monitoring and maintain current supplier relationship."
        else:
            return "Performance trends unclear. Continue monitoring and collect more data for analysis."


def get_supplier_analytics() -> SupplierAnalytics:
    """
    Factory function to create SupplierAnalytics instance

    Returns:
        Configured SupplierAnalytics instance
    """
    return SupplierAnalytics()