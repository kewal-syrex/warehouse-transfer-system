"""
Sales Analytics Module

This module provides comprehensive sales analytics calculations and metrics
for the warehouse transfer planning tool. It handles multi-SKU analysis,
revenue trends, warehouse comparisons, and high-level sales insights.

This module is completely separate from transfer planning calculations
to maintain system stability and modularity.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from decimal import Decimal
import statistics
import logging
from .database import execute_query

logger = logging.getLogger(__name__)

class SalesAnalytics:
    """
    Core sales analytics engine for multi-SKU analysis and reporting.

    Provides methods for:
    - Revenue trend analysis
    - Growth rate calculations
    - Warehouse performance comparison
    - ABC-XYZ classification
    - Top/bottom performer identification
    """

    def __init__(self):
        """Initialize sales analytics with database connection."""
        pass

    def get_revenue_trends(
        self,
        months_back: int = 12,
        warehouse: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate revenue trends over specified time period.

        Args:
            months_back: Number of months to analyze (default: 12)
            warehouse: Optional warehouse filter ('burnaby', 'kentucky', or None for both)

        Returns:
            Dictionary containing revenue trends, growth rates, and metrics
        """
        try:
            # Build warehouse filter condition
            warehouse_filter = ""
            if warehouse == 'burnaby':
                warehouse_filter = "AND burnaby_revenue > 0"
            elif warehouse == 'kentucky':
                warehouse_filter = "AND kentucky_revenue > 0"

            # Get monthly revenue trends
            query = """
            SELECT
                `year_month`,
                SUM(COALESCE(burnaby_revenue, 0)) as burnaby_revenue,
                SUM(COALESCE(kentucky_revenue, 0)) as kentucky_revenue,
                SUM(COALESCE(burnaby_revenue, 0) + COALESCE(kentucky_revenue, 0)) as total_revenue,
                COUNT(DISTINCT sku_id) as sku_count,
                SUM(COALESCE(burnaby_sales, 0) + COALESCE(kentucky_sales, 0)) as total_units
            FROM monthly_sales
            WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %s MONTH), '%%Y-%%m')
            {}
            GROUP BY `year_month`
            ORDER BY `year_month` ASC
            """.format(warehouse_filter)

            monthly_data = execute_query(query, (months_back,))

            if not monthly_data:
                return {
                    'monthly_trends': [],
                    'total_revenue': 0,
                    'growth_rate': 0,
                    'average_monthly': 0
                }

            # Calculate growth rate (current vs previous period)
            total_current = sum(row['total_revenue'] or 0 for row in monthly_data[-6:])
            total_previous = sum(row['total_revenue'] or 0 for row in monthly_data[-12:-6])

            growth_rate = 0
            if total_previous > 0:
                growth_rate = ((total_current - total_previous) / total_previous) * 100

            total_revenue = sum(row['total_revenue'] or 0 for row in monthly_data)
            avg_monthly = total_revenue / len(monthly_data) if monthly_data else 0

            return {
                'monthly_trends': monthly_data,
                'total_revenue': total_revenue,
                'growth_rate': round(growth_rate, 2),
                'average_monthly': round(avg_monthly, 2),
                'period_months': len(monthly_data)
            }

        except Exception as e:
            logger.error(f"Error calculating revenue trends: {e}")
            raise

    def get_top_performers(
        self,
        limit: int = 10,
        metric: str = 'revenue',
        period_months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get top performing SKUs by specified metric.

        Args:
            limit: Number of top performers to return
            metric: Metric to rank by ('revenue', 'units', 'growth')
            period_months: Time period for analysis

        Returns:
            List of top performer dictionaries with metrics
        """
        try:
            # Build ORDER BY clause based on metric
            if metric == 'revenue':
                order_by = "total_revenue DESC"
            elif metric == 'units':
                order_by = "total_units DESC"
            elif metric == 'growth':
                order_by = "growth_rate DESC"
            else:
                order_by = "total_revenue DESC"

            query = f"""
            SELECT
                s.sku_id,
                s.description,
                s.category,
                s.abc_code,
                s.xyz_code,
                SUM(COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) as total_revenue,
                SUM(COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) as total_units,
                AVG(CASE WHEN (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) > 0
                    THEN (COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) / (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0))
                    ELSE 0 END) as avg_selling_price,
                COUNT(ms.`year_month`) as months_with_sales
            FROM skus s
            JOIN monthly_sales ms ON s.sku_id = ms.sku_id
            WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %s MONTH), '%%Y-%%m')
              AND s.status = 'Active'
            GROUP BY s.sku_id, s.description, s.category, s.abc_code, s.xyz_code
            HAVING total_revenue > 0
            ORDER BY {order_by}
            LIMIT %s
            """

            performers = execute_query(query, (period_months, limit))

            # Calculate additional metrics
            for performer in performers:
                performer['avg_monthly_revenue'] = (
                    performer['total_revenue'] / period_months if period_months > 0 else 0
                )
                performer['avg_monthly_units'] = (
                    performer['total_units'] / period_months if period_months > 0 else 0
                )

            return performers or []

        except Exception as e:
            logger.error(f"Error getting top performers: {e}")
            return []

    def analyze_warehouse_split(self, months_back: int = 12) -> Dict[str, Any]:
        """
        Analyze sales distribution between Burnaby and Kentucky warehouses.

        Args:
            months_back: Number of months to analyze

        Returns:
            Dictionary with warehouse comparison metrics
        """
        try:
            query = """
            SELECT
                SUM(COALESCE(burnaby_revenue, 0)) as burnaby_total_revenue,
                SUM(COALESCE(kentucky_revenue, 0)) as kentucky_total_revenue,
                SUM(COALESCE(burnaby_sales, 0)) as burnaby_total_units,
                SUM(COALESCE(kentucky_sales, 0)) as kentucky_total_units,
                COUNT(DISTINCT CASE WHEN burnaby_sales > 0 THEN sku_id END) as burnaby_sku_count,
                COUNT(DISTINCT CASE WHEN kentucky_sales > 0 THEN sku_id END) as kentucky_sku_count,
                COUNT(DISTINCT sku_id) as total_sku_count
            FROM monthly_sales
            WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %s MONTH), '%%Y-%%m')
            """

            result = execute_query(query, (months_back,), fetch_one=True)

            if not result:
                return {}

            # Calculate percentages and metrics
            total_revenue = (result['burnaby_total_revenue'] or 0) + (result['kentucky_total_revenue'] or 0)
            total_units = (result['burnaby_total_units'] or 0) + (result['kentucky_total_units'] or 0)

            burnaby_revenue_pct = ((result['burnaby_total_revenue'] or 0) / total_revenue * 100) if total_revenue > 0 else 0
            kentucky_revenue_pct = ((result['kentucky_total_revenue'] or 0) / total_revenue * 100) if total_revenue > 0 else 0

            burnaby_asp = ((result['burnaby_total_revenue'] or 0) / (result['burnaby_total_units'] or 0)) if (result['burnaby_total_units'] or 0) > 0 else 0
            kentucky_asp = ((result['kentucky_total_revenue'] or 0) / (result['kentucky_total_units'] or 0)) if (result['kentucky_total_units'] or 0) > 0 else 0

            # Find SKUs exclusive to each warehouse
            exclusive_query = """
            SELECT
                COUNT(DISTINCT CASE WHEN burnaby_sales > 0 AND kentucky_sales = 0 THEN sku_id END) as burnaby_exclusive,
                COUNT(DISTINCT CASE WHEN kentucky_sales > 0 AND burnaby_sales = 0 THEN sku_id END) as kentucky_exclusive,
                COUNT(DISTINCT CASE WHEN burnaby_sales > 0 AND kentucky_sales > 0 THEN sku_id END) as both_warehouses
            FROM (
                SELECT sku_id, SUM(COALESCE(burnaby_sales, 0)) as burnaby_sales, SUM(COALESCE(kentucky_sales, 0)) as kentucky_sales
                FROM monthly_sales
                WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %s MONTH), '%%Y-%%m')
                GROUP BY sku_id
            ) as sku_totals
            """

            exclusivity = execute_query(exclusive_query, (months_back,), fetch_one=True)

            return {
                'burnaby': {
                    'revenue': result['burnaby_total_revenue'] or 0,
                    'revenue_percentage': round(burnaby_revenue_pct, 1),
                    'units': result['burnaby_total_units'] or 0,
                    'avg_selling_price': round(burnaby_asp, 2),
                    'sku_count': result['burnaby_sku_count'] or 0,
                    'exclusive_skus': (exclusivity['burnaby_exclusive'] if exclusivity else 0) or 0
                },
                'kentucky': {
                    'revenue': result['kentucky_total_revenue'] or 0,
                    'revenue_percentage': round(kentucky_revenue_pct, 1),
                    'units': result['kentucky_total_units'] or 0,
                    'avg_selling_price': round(kentucky_asp, 2),
                    'sku_count': result['kentucky_sku_count'] or 0,
                    'exclusive_skus': (exclusivity['kentucky_exclusive'] if exclusivity else 0) or 0
                },
                'shared_skus': (exclusivity['both_warehouses'] if exclusivity else 0) or 0,
                'total_skus': result['total_sku_count'] or 0,
                'total_revenue': total_revenue,
                'total_units': total_units
            }

        except Exception as e:
            logger.error(f"Error analyzing warehouse split: {e}")
            return {}

    def calculate_stockout_impact(self, months_back: int = 12) -> List[Dict[str, Any]]:
        """
        Calculate the revenue impact of stockouts across all SKUs.

        Args:
            months_back: Number of months to analyze

        Returns:
            List with stockout impact data for each affected SKU
        """
        try:
            query = """
            SELECT
                ms.sku_id,
                s.description,
                SUM(COALESCE(ms.kentucky_stockout_days, 0)) as total_stockout_days,
                SUM(COALESCE(ms.kentucky_sales, 0)) as actual_sales,
                SUM(COALESCE(ms.corrected_demand_kentucky, ms.kentucky_sales, 0)) as potential_sales
            FROM monthly_sales ms
            JOIN skus s ON ms.sku_id = s.sku_id
            WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %s MONTH), '%%Y-%%m')
                AND COALESCE(ms.kentucky_stockout_days, 0) > 0
            GROUP BY ms.sku_id, s.description
            HAVING total_stockout_days > 0
            ORDER BY (potential_sales - actual_sales) DESC
            LIMIT 100
            """

            impact = execute_query(query, (months_back,))
            return impact or []

        except Exception as e:
            logger.error(f"Error calculating stockout impact: {e}")
            return []

    def get_abc_xyz_distribution(self) -> List[Dict[str, Any]]:
        """
        Get the distribution of SKUs across ABC-XYZ classification matrix.

        This method retrieves the 9-box ABC-XYZ matrix data showing how SKUs
        are distributed by revenue importance (A/B/C) and demand volatility (X/Y/Z).
        The data is used to populate the interactive matrix visualization.

        Returns:
            List of classification data with counts and revenue for each combination:
            - abc_code: Revenue classification (A=High, B=Medium, C=Low)
            - xyz_code: Volatility classification (X=Stable, Y=Variable, Z=Erratic)
            - classification: Combined code (e.g., 'AX', 'BY', 'CZ')
            - sku_count: Number of SKUs in this classification
            - total_revenue: Total revenue for this classification
            - avg_revenue_per_sku: Average revenue per SKU
            - total_units: Total units sold for this classification
        """
        try:
            # Use the optimized view for better performance
            query = """
            SELECT * FROM v_abc_xyz_matrix
            ORDER BY abc_code, xyz_code
            """

            matrix_data = execute_query(query)

            # Ensure all 9 possible combinations are represented (A/B/C x X/Y/Z)
            all_combinations = []
            for abc in ['A', 'B', 'C']:
                for xyz in ['X', 'Y', 'Z']:
                    classification = abc + xyz

                    # Find existing data for this combination
                    existing = next((item for item in (matrix_data or [])
                                   if item['abc_code'] == abc and item['xyz_code'] == xyz), None)

                    if existing:
                        all_combinations.append({
                            'abc_code': abc,
                            'xyz_code': xyz,
                            'classification': classification,
                            'sku_count': existing.get('sku_count', 0) or 0,
                            'total_revenue': existing.get('total_revenue', 0) or 0,
                            'avg_revenue_per_sku': existing.get('avg_revenue_per_sku', 0) or 0,
                            'total_units': existing.get('total_units', 0) or 0
                        })
                    else:
                        # Add empty combination for completeness
                        all_combinations.append({
                            'abc_code': abc,
                            'xyz_code': xyz,
                            'classification': classification,
                            'sku_count': 0,
                            'total_revenue': 0,
                            'avg_revenue_per_sku': 0,
                            'total_units': 0
                        })

            return all_combinations

        except Exception as e:
            logger.error(f"Error getting ABC-XYZ distribution: {e}")
            return []


def get_sales_summary(months_back: int = 12) -> Dict[str, Any]:
    """
    Get high-level sales summary for dashboard display with enhanced calculations.

    This function returns comprehensive sales metrics including revenue averages,
    stockout impact estimates, and growth indicators needed for the dashboard KPIs.

    Args:
        months_back: Number of months to analyze (default: 12)

    Returns:
        Dictionary containing key sales metrics and insights including:
        - total_skus: Count of unique SKUs with sales
        - total_units: Total units sold across all warehouses
        - total_revenue: Total revenue across all warehouses
        - average_monthly_revenue: Average monthly revenue (not sales units)
        - estimated_stockout_loss: Estimated revenue lost due to stockouts
        - monthly_growth_rate: Growth rate comparison for recent periods
        - period_analyzed_months: Number of months included in analysis
    """
    try:
        # Use the new sales summary view for performance
        base_query = """
        SELECT * FROM v_sales_summary_12m
        """

        base_result = execute_query(base_query, fetch_one=True)

        if not base_result:
            return {}

        # Calculate additional metrics that aren't in the view
        # Get growth rate by comparing recent 3 months vs previous 3 months
        growth_query = """
        SELECT
            SUM(CASE
                WHEN ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%%Y-%%m')
                THEN COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)
                ELSE 0
            END) as recent_revenue,
            SUM(CASE
                WHEN ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%%Y-%%m')
                AND ms.`year_month` < DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%%Y-%%m')
                THEN COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)
                ELSE 0
            END) as previous_revenue
        FROM monthly_sales ms
        WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%%Y-%%m')
        """

        growth_result = execute_query(growth_query, fetch_one=True)

        # Calculate growth rate
        growth_rate = 0
        if growth_result and growth_result['previous_revenue'] and growth_result['previous_revenue'] > 0:
            growth_rate = ((growth_result['recent_revenue'] - growth_result['previous_revenue']) /
                          growth_result['previous_revenue'] * 100)

        # Calculate estimated lost revenue from stockouts
        lost_revenue_ky = 0
        lost_revenue_ca = 0

        if base_result.get('estimated_lost_sales_ky', 0) > 0:
            # Estimate lost revenue using average selling price
            avg_price_query = """
            SELECT
                AVG(CASE
                    WHEN (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) > 0
                    THEN (COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) /
                         (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0))
                    ELSE 0
                END) as avg_selling_price
            FROM monthly_sales ms
            WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %s MONTH), '%%Y-%%m')
                AND (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) > 0
            """

            avg_price_result = execute_query(avg_price_query, (months_back,), fetch_one=True)
            avg_price = avg_price_result['avg_selling_price'] if avg_price_result else 0

            if avg_price > 0:
                lost_revenue_ky = base_result.get('estimated_lost_sales_ky', 0) * avg_price
                lost_revenue_ca = base_result.get('estimated_lost_sales_ca', 0) * avg_price

        total_lost_revenue = lost_revenue_ky + lost_revenue_ca

        return {
            'total_skus': base_result.get('total_skus', 0),
            'total_units': base_result.get('total_units', 0),
            'total_revenue': base_result.get('total_revenue', 0),
            'average_monthly_revenue': base_result.get('avg_monthly_revenue', 0),  # Fixed: return revenue not sales
            'estimated_stockout_loss': round(total_lost_revenue, 2),  # Fixed: calculate actual loss
            'monthly_growth_rate': round(growth_rate, 2),
            'period_analyzed_months': months_back,
            'total_stockout_days': (base_result.get('total_stockout_days_ky', 0) +
                                   base_result.get('total_stockout_days_ca', 0)),
            'estimated_lost_sales_units': (base_result.get('estimated_lost_sales_ky', 0) +
                                         base_result.get('estimated_lost_sales_ca', 0))
        }

    except Exception as e:
        logger.error(f"Error getting sales summary: {e}")
        return {}