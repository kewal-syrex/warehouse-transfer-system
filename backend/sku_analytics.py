"""
SKU Analytics Module

This module provides detailed analytics for individual SKU performance,
including trends, seasonality, lifecycle analysis, and actionable insights.

Focuses on single-SKU deep-dive analysis to support strategic inventory
and product management decisions.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from decimal import Decimal
import statistics
import logging
import math
from .database import execute_query

logger = logging.getLogger(__name__)

class SKUAnalytics:
    """
    Deep-dive analytics engine for individual SKU analysis.

    Provides comprehensive analysis including:
    - Performance metrics and trends
    - Seasonal pattern detection
    - Stockout impact analysis
    - Lifecycle stage determination
    - Automated insight generation
    """

    def __init__(self):
        """Initialize SKU analytics with database connection."""
        pass

    def get_sku_performance_metrics(
        self,
        sku_id: str,
        months_back: int = 24
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics for a specific SKU.

        Args:
            sku_id: SKU identifier to analyze
            months_back: Number of months of history to analyze

        Returns:
            Dictionary with complete SKU analysis data
        """
        try:
            # Get basic SKU information
            sku_info_query = """
            SELECT sku_id, description, category, supplier, abc_code, xyz_code, status
            FROM skus
            WHERE sku_id = %s
            """

            sku_info = execute_query(sku_info_query, (sku_id,), fetch_one=True)

            if not sku_info:
                return {'error': f'SKU {sku_id} not found'}

            # Get sales history
            sales_query = """
            SELECT
                `year_month`,
                COALESCE(burnaby_sales, 0) as burnaby_sales,
                COALESCE(kentucky_sales, 0) as kentucky_sales,
                COALESCE(burnaby_revenue, 0) as burnaby_revenue,
                COALESCE(kentucky_revenue, 0) as kentucky_revenue,
                COALESCE(burnaby_stockout_days, 0) as burnaby_stockout_days,
                COALESCE(kentucky_stockout_days, 0) as kentucky_stockout_days,
                COALESCE(corrected_demand_burnaby, burnaby_sales, 0) as corrected_demand_burnaby,
                COALESCE(corrected_demand_kentucky, kentucky_sales, 0) as corrected_demand_kentucky
            FROM monthly_sales
            WHERE sku_id = %s
                AND `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %s MONTH), '%%Y-%%m')
            ORDER BY `year_month` ASC
            """

            sales_history = execute_query(sales_query, (sku_id, months_back))

            if not sales_history:
                return {'error': f'No sales data found for SKU {sku_id}'}

            # Calculate performance metrics
            total_sales = sum((row['burnaby_sales'] or 0) + (row['kentucky_sales'] or 0) for row in sales_history)
            total_revenue = sum((row['burnaby_revenue'] or 0) + (row['kentucky_revenue'] or 0) for row in sales_history)

            months_with_sales = len([row for row in sales_history if ((row['burnaby_sales'] or 0) + (row['kentucky_sales'] or 0)) > 0])

            # Calculate averages
            avg_monthly_sales = total_sales / len(sales_history) if sales_history else 0
            avg_selling_price = total_revenue / total_sales if total_sales > 0 else 0

            # Calculate growth trend (last 6 months vs previous 6 months)
            if len(sales_history) >= 12:
                recent_sales = sum((row['burnaby_sales'] or 0) + (row['kentucky_sales'] or 0) for row in sales_history[-6:])
                previous_sales = sum((row['burnaby_sales'] or 0) + (row['kentucky_sales'] or 0) for row in sales_history[-12:-6])
                growth_rate = ((recent_sales - previous_sales) / previous_sales * 100) if previous_sales > 0 else 0
            else:
                growth_rate = 0

            # Calculate stockout impact
            total_stockout_days = sum((row['burnaby_stockout_days'] or 0) + (row['kentucky_stockout_days'] or 0) for row in sales_history)
            total_corrected_demand = sum((row['corrected_demand_burnaby'] or 0) + (row['corrected_demand_kentucky'] or 0) for row in sales_history)
            lost_sales_estimate = total_corrected_demand - total_sales

            # Get seasonal patterns
            seasonal_patterns = self._get_seasonal_patterns(sku_id)

            # Get current inventory position
            inventory_query = """
            SELECT burnaby_qty, kentucky_qty
            FROM inventory_current
            WHERE sku_id = %s
            """

            inventory = execute_query(inventory_query, (sku_id,), fetch_one=True)
            current_inventory = {
                'burnaby_qty': (inventory['burnaby_qty'] if inventory else 0) or 0,
                'kentucky_qty': (inventory['kentucky_qty'] if inventory else 0) or 0
            }

            return {
                'sku_info': sku_info,
                'sales_history': sales_history,
                'performance_metrics': {
                    'total_sales_units': total_sales,
                    'total_revenue': round(total_revenue, 2),
                    'avg_monthly_sales': round(avg_monthly_sales, 2),
                    'avg_selling_price': round(avg_selling_price, 2),
                    'months_with_sales': months_with_sales,
                    'months_analyzed': len(sales_history),
                    'sales_consistency': round(months_with_sales / len(sales_history) * 100, 1) if sales_history else 0,
                    'growth_rate_6m': round(growth_rate, 2),
                    'total_stockout_days': total_stockout_days,
                    'estimated_lost_sales': round(lost_sales_estimate, 2)
                },
                'seasonal_patterns': seasonal_patterns,
                'current_inventory': current_inventory,
                'analysis_period': {
                    'months_back': months_back,
                    'start_date': sales_history[0]['year_month'] if sales_history else None,
                    'end_date': sales_history[-1]['year_month'] if sales_history else None
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing SKU {sku_id}: {e}")
            return {'error': f'Analysis failed for SKU {sku_id}: {str(e)}'}

    def _get_seasonal_patterns(self, sku_id: str) -> Dict[str, Any]:
        """
        Analyze seasonal patterns for a specific SKU.

        Args:
            sku_id: SKU identifier

        Returns:
            Dictionary with seasonal analysis data
        """
        try:
            # Get sales by month across multiple years
            query = """
            SELECT
                MONTH(`year_month`) as month_num,
                MONTHNAME(STR_TO_DATE(`year_month`, '%%Y-%%m')) as month_name,
                AVG(COALESCE(burnaby_sales, 0) + COALESCE(kentucky_sales, 0)) as avg_sales,
                COUNT(*) as data_points
            FROM monthly_sales
            WHERE sku_id = %s
                AND (COALESCE(burnaby_sales, 0) + COALESCE(kentucky_sales, 0)) > 0
            GROUP BY month_num, month_name
            HAVING data_points >= 2
            ORDER BY month_num
            """

            monthly_patterns = execute_query(query, (sku_id,))

            if not monthly_patterns or len(monthly_patterns) < 6:
                return {
                    'has_seasonal_pattern': False,
                    'monthly_averages': [],
                    'peak_months': [],
                    'low_months': [],
                    'seasonality_strength': 0
                }

            # Calculate seasonality strength (coefficient of variation of monthly averages)
            monthly_sales = [row['avg_sales'] for row in monthly_patterns]
            if len(monthly_sales) > 1:
                cv = statistics.stdev(monthly_sales) / statistics.mean(monthly_sales)
                seasonality_strength = min(cv * 100, 100)  # Cap at 100%
            else:
                seasonality_strength = 0

            # Identify peak and low months
            sorted_months = sorted(monthly_patterns, key=lambda x: x['avg_sales'], reverse=True)
            peak_months = [row['month_name'] for row in sorted_months[:2]]
            low_months = [row['month_name'] for row in sorted_months[-2:]]

            return {
                'has_seasonal_pattern': seasonality_strength > 25,  # >25% CV indicates seasonality
                'monthly_averages': monthly_patterns,
                'peak_months': peak_months,
                'low_months': low_months,
                'seasonality_strength': round(seasonality_strength, 1)
            }

        except Exception as e:
            logger.error(f"Error calculating seasonal patterns for {sku_id}: {e}")
            return {
                'has_seasonal_pattern': False,
                'monthly_averages': [],
                'peak_months': [],
                'low_months': [],
                'seasonality_strength': 0
            }

    def generate_sku_insights(
        self,
        sku_id: str,
        analysis_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable insights based on SKU analysis data.

        Args:
            sku_id: SKU identifier
            analysis_data: Complete analysis data from get_sku_performance_metrics

        Returns:
            List of insight dictionaries with type, message, and priority
        """
        insights = []

        try:
            metrics = analysis_data.get('performance_metrics', {})
            seasonal = analysis_data.get('seasonal_patterns', {})
            inventory = analysis_data.get('current_inventory', {})

            # Growth trend insights
            growth_rate = metrics.get('growth_rate_6m', 0)
            if growth_rate > 50:
                insights.append({
                    'type': 'growth',
                    'priority': 'high',
                    'message': f'Strong growth trend: {growth_rate:.1f}% increase in last 6 months. Consider increasing inventory levels.',
                    'metric': growth_rate
                })
            elif growth_rate < -30:
                insights.append({
                    'type': 'decline',
                    'priority': 'medium',
                    'message': f'Declining sales: {abs(growth_rate):.1f}% decrease in last 6 months. Review pricing and marketing strategy.',
                    'metric': growth_rate
                })

            # Stockout impact insights
            lost_sales = metrics.get('estimated_lost_sales', 0)
            stockout_days = metrics.get('total_stockout_days', 0)
            if lost_sales > 100:
                insights.append({
                    'type': 'stockout',
                    'priority': 'high',
                    'message': f'High stockout impact: Estimated {lost_sales:.0f} units lost to stockouts over {stockout_days} days. Improve safety stock levels.',
                    'metric': lost_sales
                })
            elif stockout_days > 30:
                insights.append({
                    'type': 'stockout',
                    'priority': 'medium',
                    'message': f'Frequent stockouts: Out of stock for {stockout_days} days total. Consider reducing lead times.',
                    'metric': stockout_days
                })

            # Seasonal insights
            if seasonal.get('has_seasonal_pattern', False):
                peak_months = seasonal.get('peak_months', [])
                seasonality_strength = seasonal.get('seasonality_strength', 0)
                if peak_months:
                    insights.append({
                        'type': 'seasonal',
                        'priority': 'medium',
                        'message': f'Strong seasonal pattern ({seasonality_strength:.1f}% variation). Peak months: {", ".join(peak_months)}. Plan inventory accordingly.',
                        'metric': seasonality_strength
                    })

            # Inventory position insights
            kentucky_qty = inventory.get('kentucky_qty', 0)
            avg_monthly_sales = metrics.get('avg_monthly_sales', 0)
            if kentucky_qty == 0 and avg_monthly_sales > 10:
                insights.append({
                    'type': 'stockout',
                    'priority': 'critical',
                    'message': 'Currently out of stock in Kentucky warehouse despite consistent sales. Immediate transfer needed.',
                    'metric': 0
                })
            elif avg_monthly_sales > 0:
                months_of_coverage = kentucky_qty / avg_monthly_sales if avg_monthly_sales > 0 else 0
                if months_of_coverage < 1:
                    insights.append({
                        'type': 'inventory',
                        'priority': 'high',
                        'message': f'Low inventory coverage: Only {months_of_coverage:.1f} months of stock remaining based on average sales.',
                        'metric': months_of_coverage
                    })

            # Sales consistency insights
            consistency = metrics.get('sales_consistency', 0)
            if consistency < 50:
                insights.append({
                    'type': 'consistency',
                    'priority': 'medium',
                    'message': f'Irregular sales pattern: Only {consistency:.1f}% of months had sales. Consider demand forecasting improvements.',
                    'metric': consistency
                })

            # Sort insights by priority
            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            insights.sort(key=lambda x: priority_order.get(x['priority'], 3))

            return insights

        except Exception as e:
            logger.error(f"Error generating insights for {sku_id}: {e}")
            return [{
                'type': 'error',
                'priority': 'low',
                'message': 'Unable to generate insights due to data processing error.',
                'metric': 0
            }]


def search_skus(search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for SKUs by ID or description.

    Args:
        search_term: Search query string
        limit: Maximum number of results to return

    Returns:
        List of matching SKUs with basic information
    """
    try:
        # Search in both SKU ID and description
        query = """
        SELECT
            s.sku_id,
            s.description,
            s.category,
            s.abc_code,
            s.xyz_code,
            s.status,
            COALESCE(ic.kentucky_qty, 0) as current_stock,
            recent_sales.avg_monthly_sales
        FROM skus s
        LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
        LEFT JOIN (
            SELECT
                sku_id,
                AVG(COALESCE(burnaby_sales, 0) + COALESCE(kentucky_sales, 0)) as avg_monthly_sales
            FROM monthly_sales
            WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%%Y-%%m')
            GROUP BY sku_id
        ) as recent_sales ON s.sku_id = recent_sales.sku_id
        WHERE (s.sku_id LIKE %s OR s.description LIKE %s)
            AND s.status = 'Active'
        ORDER BY
            CASE WHEN s.sku_id LIKE %s THEN 1 ELSE 2 END,
            recent_sales.avg_monthly_sales DESC
        LIMIT %s
        """

        search_pattern = f"%{search_term}%"
        exact_match_pattern = f"{search_term}%"

        results = execute_query(query, (search_pattern, search_pattern, exact_match_pattern, limit))

        return results or []

    except Exception as e:
        logger.error(f"Error searching SKUs with term '{search_term}': {e}")
        return []


def get_quick_lists() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get quick access lists for common SKU selections.

    Returns:
        Dictionary with different quick access lists
    """
    try:
        # Top selling SKUs
        top_sellers_query = """
        SELECT
            s.sku_id,
            s.description,
            SUM(COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) as total_sales
        FROM skus s
        JOIN monthly_sales ms ON s.sku_id = ms.sku_id
        WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%%Y-%%m')
            AND s.status = 'Active'
        GROUP BY s.sku_id, s.description
        ORDER BY total_sales DESC
        LIMIT 20
        """

        top_sellers = execute_query(top_sellers_query)

        # Recently out of stock SKUs
        out_of_stock_query = """
        SELECT
            s.sku_id,
            s.description,
            ic.kentucky_qty,
            recent_sales.avg_monthly_sales
        FROM skus s
        JOIN inventory_current ic ON s.sku_id = ic.sku_id
        LEFT JOIN (
            SELECT
                sku_id,
                AVG(COALESCE(kentucky_sales, 0)) as avg_monthly_sales
            FROM monthly_sales
            WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%%Y-%%m')
            GROUP BY sku_id
        ) as recent_sales ON s.sku_id = recent_sales.sku_id
        WHERE ic.kentucky_qty = 0
            AND recent_sales.avg_monthly_sales > 0
            AND s.status = 'Active'
        ORDER BY recent_sales.avg_monthly_sales DESC
        LIMIT 15
        """

        out_of_stock = execute_query(out_of_stock_query)

        # High growth SKUs
        high_growth_query = """
        SELECT
            s.sku_id,
            s.description,
            recent.recent_sales,
            older.older_sales,
            CASE WHEN older.older_sales > 0
                THEN ((recent.recent_sales - older.older_sales) / older.older_sales * 100)
                ELSE 0
            END as growth_rate
        FROM skus s
        JOIN (
            SELECT sku_id, SUM(COALESCE(burnaby_sales, 0) + COALESCE(kentucky_sales, 0)) as recent_sales
            FROM monthly_sales
            WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%%Y-%%m')
            GROUP BY sku_id
        ) as recent ON s.sku_id = recent.sku_id
        JOIN (
            SELECT sku_id, SUM(COALESCE(burnaby_sales, 0) + COALESCE(kentucky_sales, 0)) as older_sales
            FROM monthly_sales
            WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%%Y-%%m')
                AND `year_month` < DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%%Y-%%m')
            GROUP BY sku_id
        ) as older ON s.sku_id = older.sku_id
        WHERE s.status = 'Active'
            AND older.older_sales > 0
            AND recent.recent_sales > older.older_sales
        ORDER BY growth_rate DESC
        LIMIT 15
        """

        high_growth = execute_query(high_growth_query)

        return {
            'top_sellers': top_sellers or [],
            'out_of_stock': out_of_stock or [],
            'high_growth': high_growth or []
        }

    except Exception as e:
        logger.error(f"Error getting quick lists: {e}")
        return {
            'top_sellers': [],
            'out_of_stock': [],
            'high_growth': []
        }