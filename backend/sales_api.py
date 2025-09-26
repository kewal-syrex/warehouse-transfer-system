"""
Sales Analytics API Endpoints

This module provides FastAPI endpoints for the sales analytics dashboard.
Completely separate from transfer planning to maintain system integrity.

Endpoints include:
- Sales summary and KPIs
- SKU search and analysis
- Revenue trends and comparisons
- ABC-XYZ matrix data
- Stockout impact analysis
"""

from fastapi import FastAPI, HTTPException, Query
from typing import Dict, List, Optional, Any
import logging
from . import sales_analytics
from .sales_analytics import SalesAnalytics, get_sales_summary
from . import sku_analytics
from .sku_analytics import SKUAnalytics, search_skus, get_quick_lists
from . import seasonal_analysis
from .seasonal_analysis import SeasonalAnalyzer
from .sales_analytics import calculate_growth_rates, calculate_detailed_stockout_impact, identify_bottom_performers
from . import database
from .database import execute_query

logger = logging.getLogger(__name__)

def setup_sales_routes(app: FastAPI):
    """
    Setup sales analytics routes on the FastAPI app.

    Args:
        app: FastAPI application instance
    """

    @app.get("/api/sales/summary")
    async def get_sales_dashboard_summary(
        months_back: int = Query(12, ge=1, le=60, description="Number of months to analyze")
    ) -> Dict[str, Any]:
        """
        Get high-level sales summary for dashboard KPIs.

        Returns key metrics including revenue trends, growth rates,
        warehouse split, and stockout impact.
        """
        try:
            summary = get_sales_summary(months_back)
            return {
                "success": True,
                "data": summary
            }
        except Exception as e:
            logger.error(f"Error getting sales summary: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sales/revenue-trends")
    async def get_revenue_trends(
        months_back: int = Query(12, ge=1, le=60),
        warehouse: Optional[str] = Query(None, regex="^(burnaby|kentucky)$")
    ) -> Dict[str, Any]:
        """
        Get detailed revenue trends over time.

        Args:
            months_back: Number of months to analyze
            warehouse: Optional warehouse filter

        Returns:
            Monthly revenue trends with growth calculations
        """
        try:
            analytics = SalesAnalytics()
            trends = analytics.get_revenue_trends(months_back, warehouse)
            return {
                "success": True,
                "data": trends
            }
        except Exception as e:
            logger.error(f"Error getting revenue trends: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sales/top-performers")
    async def get_top_performers(
        limit: int = Query(10, ge=1, le=100),
        metric: str = Query("revenue", regex="^(revenue|units|growth)$"),
        period_months: int = Query(12, ge=1, le=60)
    ) -> Dict[str, Any]:
        """
        Get top performing SKUs by specified metric.

        Args:
            limit: Number of top performers to return
            metric: Metric to rank by (revenue, units, growth)
            period_months: Time period for analysis

        Returns:
            List of top performing SKUs with metrics
        """
        try:
            analytics = SalesAnalytics()
            performers = analytics.get_top_performers(limit, metric, period_months)
            return {
                "success": True,
                "data": performers
            }
        except Exception as e:
            logger.error(f"Error getting top performers: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sales/warehouse-comparison")
    async def get_warehouse_comparison(
        months_back: int = Query(12, ge=1, le=60)
    ) -> Dict[str, Any]:
        """
        Get detailed warehouse performance comparison.

        Args:
            months_back: Number of months to analyze

        Returns:
            Comprehensive warehouse comparison metrics
        """
        try:
            analytics = SalesAnalytics()
            comparison = analytics.analyze_warehouse_split(months_back)
            return {
                "success": True,
                "data": comparison
            }
        except Exception as e:
            logger.error(f"Error getting warehouse comparison: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sales/stockout-impact")
    async def get_stockout_impact(
        months_back: int = Query(12, ge=1, le=60)
    ) -> Dict[str, Any]:
        """
        Get stockout impact analysis across all SKUs with frontend-compatible data structure.

        This endpoint transforms the stockout impact data from the analytics engine
        into a format that matches frontend expectations for the Pareto chart visualization.

        Data Structure Transformation:
        - Maps 'lost_sales' field to 'estimated_lost_revenue' for frontend compatibility
        - Calculates total_estimated_loss by summing all individual SKU losses
        - Wraps SKU array in 'affected_skus' property as expected by chart renderer
        - Ensures numeric values are properly formatted for JSON serialization

        Args:
            months_back: Number of months to analyze (1-60)

        Returns:
            Dict containing:
                - success: Boolean indicating operation status
                - data: Dict with:
                    - affected_skus: List of SKUs with stockout impact data
                    - total_estimated_loss: Total revenue loss across all SKUs
                    - period_months: Analysis period for context

        Raises:
            HTTPException: 500 if calculation fails or data transformation error occurs
        """
        try:
            analytics = SalesAnalytics()
            raw_impact_data = analytics.calculate_stockout_impact(months_back)

            # Transform data structure to match frontend expectations
            if not raw_impact_data or len(raw_impact_data) == 0:
                # Handle empty result case
                return {
                    "success": True,
                    "data": {
                        "affected_skus": [],
                        "total_estimated_loss": 0.0,
                        "period_months": months_back
                    }
                }

            # Map backend field names to frontend expectations and ensure numeric conversion
            affected_skus = []
            total_loss = 0.0

            for sku_data in raw_impact_data:
                # Convert lost_sales to estimated_lost_revenue with proper numeric handling
                lost_revenue = float(sku_data.get('lost_sales', 0))
                total_loss += lost_revenue

                # Create frontend-compatible SKU record
                transformed_sku = {
                    'sku_id': sku_data.get('sku_id', ''),
                    'description': sku_data.get('description', ''),
                    'total_stockout_days': float(sku_data.get('total_stockout_days', 0)),
                    'actual_sales': float(sku_data.get('actual_sales', 0)),
                    'potential_sales': float(sku_data.get('potential_sales', 0)),
                    'estimated_lost_revenue': lost_revenue  # Key field mapping for frontend
                }
                affected_skus.append(transformed_sku)

            # Return data in frontend-expected structure
            return {
                "success": True,
                "data": {
                    "affected_skus": affected_skus,
                    "total_estimated_loss": round(total_loss, 2),
                    "period_months": months_back
                }
            }

        except Exception as e:
            logger.error(f"Error getting stockout impact: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")  # Updated for V6.3 fix

    @app.get("/api/sales/abc-xyz-matrix")
    async def get_abc_xyz_matrix() -> Dict[str, Any]:
        """
        Get ABC-XYZ classification matrix data.

        Returns:
            Matrix with SKU counts and revenue by classification
        """
        try:
            analytics = SalesAnalytics()
            matrix = analytics.get_abc_xyz_distribution()
            return {
                "success": True,
                "data": matrix
            }
        except Exception as e:
            logger.error(f"Error getting ABC-XYZ matrix: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sales/all-skus")
    async def get_all_skus(
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of SKUs to return"),
        offset: int = Query(0, ge=0, description="Number of SKUs to skip for pagination"),
        sort_by: str = Query("total_revenue_12m", description="Field to sort by"),
        sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
        abc_filter: Optional[str] = Query(None, regex="^[ABC]$", description="Filter by ABC classification"),
        xyz_filter: Optional[str] = Query(None, regex="^[XYZ]$", description="Filter by XYZ classification"),
        min_revenue: Optional[float] = Query(None, ge=0, description="Minimum revenue filter"),
        status_filter: Optional[str] = Query(None, regex="^(Active|Death Row|Discontinued|All)$", description="Filter by SKU status"),
        status: Optional[str] = Query(None, regex="^(active|death row|discontinued|all)$", description="Alternative status filter parameter")
    ) -> Dict[str, Any]:
        """
        Get all SKUs with comprehensive performance metrics and filtering.

        This endpoint returns a paginated list of SKUs with their performance metrics,
        supporting various filters and sorting options for the All SKUs section of the dashboard.

        Enhanced to support all SKU statuses (Active, Death Row, Discontinued) using the new
        v_all_skus_performance view which includes all statuses without filtering.

        Args:
            limit: Maximum number of SKUs to return (1-1000)
            offset: Number of SKUs to skip for pagination
            sort_by: Field to sort by (revenue, units, growth_rate, etc.)
            sort_order: Sort order (asc or desc)
            abc_filter: Filter by ABC classification (A, B, or C)
            xyz_filter: Filter by XYZ classification (X, Y, or Z)
            min_revenue: Minimum revenue threshold
            status_filter: Filter by SKU status (Active, Death Row, Discontinued, All)

        Returns:
            Paginated list of SKUs with performance metrics and pagination info
        """
        print(f"FUNCTION CALLED: get_all_skus with status_filter={status_filter}")
        try:
            # Build WHERE clause based on filters
            where_conditions = []

            # Handle status filtering - support both status_filter and status parameters
            effective_status = status_filter or status  # Use status_filter first, then fall back to status

            if effective_status and effective_status.lower() not in ["all", "none"]:
                # Normalize status value (handle case variations)
                status_map = {
                    "active": "Active",
                    "death row": "Death Row",
                    "discontinued": "Discontinued"
                }
                normalized_status = status_map.get(effective_status.lower(), effective_status)
                where_conditions.append(f"status = '{normalized_status}'")

            logger.info(f"DEBUG: status_filter='{status_filter}', where_conditions={where_conditions}")

            # Apply other filters
            if abc_filter:
                where_conditions.append(f"abc_code = '{abc_filter}'")
            if xyz_filter:
                where_conditions.append(f"xyz_code = '{xyz_filter}'")
            if min_revenue:
                where_conditions.append(f"COALESCE(total_revenue_12m, 0) >= {min_revenue}")

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            logger.info(f"DEBUG SQL: WHERE {where_clause}")

            # Use the new all-SKUs view that includes all statuses
            query = f"""
            SELECT * FROM v_all_skus_performance
            WHERE {where_clause}
            ORDER BY {sort_by} {sort_order.upper()}
            LIMIT %s OFFSET %s
            """

            # Get total count for pagination
            count_query = f"""
            SELECT COUNT(*) as total FROM v_all_skus_performance
            WHERE {where_clause}
            """

            # Debug: Get SKU counts by status for comparison
            debug_count_query = """
            SELECT
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_skus,
                COUNT(CASE WHEN status = 'Death Row' THEN 1 END) as death_row_skus,
                COUNT(CASE WHEN status = 'Discontinued' THEN 1 END) as discontinued_skus,
                COUNT(*) as total_skus
            FROM skus
            """

            skus = execute_query(query, (limit, offset))
            count_result = execute_query(count_query, fetch_one=True)
            debug_result = execute_query(debug_count_query, fetch_one=True)
            total_count = count_result['total'] if count_result else 0

            # Log debug information for SKU count tracking
            if debug_result:
                logger.info(f"SKU Count Debug - View Results: {total_count}, Active: {debug_result['active_skus']}, Death Row: {debug_result['death_row_skus']}, Discontinued: {debug_result['discontinued_skus']}, Total: {debug_result['total_skus']}, Effective Filter: {effective_status or 'All'}, Where: {where_clause}")

            return {
                "success": True,
                "data": skus or [],
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                },
                "filters_applied": {
                    "abc_filter": abc_filter,
                    "xyz_filter": xyz_filter,
                    "min_revenue": min_revenue,
                    "sort_by": sort_by,
                    "sort_order": sort_order
                }
            }

        except Exception as e:
            logger.error(f"Error getting all SKUs: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sku/search")
    async def search_sku(
        q: str = Query(..., min_length=1, description="Search query"),
        limit: int = Query(10, ge=1, le=50)
    ) -> Dict[str, Any]:
        """
        Search for SKUs by ID or description.

        Args:
            q: Search query string
            limit: Maximum number of results

        Returns:
            List of matching SKUs with basic metrics
        """
        try:
            results = search_skus(q, limit)
            return {
                "success": True,
                "data": results,
                "count": len(results)
            }
        except Exception as e:
            logger.error(f"Error searching SKUs: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sku/quick-lists")
    async def get_sku_quick_lists() -> Dict[str, Any]:
        """
        Get quick access lists for common SKU selections.

        Returns:
            Dictionary with different quick access lists
        """
        try:
            lists = get_quick_lists()
            return {
                "success": True,
                "data": lists
            }
        except Exception as e:
            logger.error(f"Error getting quick lists: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sku/{sku_id}/analysis")
    async def get_sku_analysis(
        sku_id: str,
        months_back: int = Query(24, ge=6, le=60)
    ) -> Dict[str, Any]:
        """
        Get comprehensive analysis for a specific SKU.

        Args:
            sku_id: SKU identifier to analyze
            months_back: Number of months of history to analyze

        Returns:
            Complete SKU performance analysis
        """
        try:
            analytics = SKUAnalytics()
            analysis = analytics.get_sku_performance_metrics(sku_id, months_back)

            if 'error' in analysis:
                raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found or no sales data")

            # Generate insights
            insights = analytics.generate_sku_insights(sku_id, analysis)
            analysis['insights'] = insights

            return {
                "success": True,
                "data": analysis
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error getting SKU analysis for {sku_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sku/{sku_id}/trends")
    async def get_sku_trends(
        sku_id: str,
        months_back: int = Query(24, ge=6, le=60)
    ) -> Dict[str, Any]:
        """
        Get detailed trend data for a specific SKU.

        Args:
            sku_id: SKU identifier
            months_back: Number of months to analyze

        Returns:
            Monthly sales trends and metrics
        """
        try:
            analytics = SKUAnalytics()
            analysis = analytics.get_sku_performance_metrics(sku_id, months_back)

            if 'error' in analysis:
                raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")

            # Extract trend-specific data
            trends_data = {
                'sku_info': analysis.get('sku_info'),
                'sales_history': analysis.get('sales_history'),
                'performance_metrics': analysis.get('performance_metrics'),
                'seasonal_patterns': analysis.get('seasonal_patterns')
            }

            return {
                "success": True,
                "data": trends_data
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error getting SKU trends for {sku_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sku/{sku_id}/seasonality")
    async def get_sku_seasonality(sku_id: str) -> Dict[str, Any]:
        """
        Get seasonal pattern analysis for a specific SKU.

        Args:
            sku_id: SKU identifier

        Returns:
            Seasonal patterns and indices
        """
        try:
            analytics = SKUAnalytics()
            seasonal = analytics._get_seasonal_patterns(sku_id)

            return {
                "success": True,
                "data": seasonal
            }
        except Exception as e:
            logger.error(f"Error getting seasonality for {sku_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sales/export/summary")
    async def export_sales_summary(
        months_back: int = Query(12, ge=1, le=60),
        format: str = Query("json", regex="^(json|csv)$")
    ) -> Dict[str, Any]:
        """
        Export sales summary data for download.

        Args:
            months_back: Number of months to analyze
            format: Export format (json or csv)

        Returns:
            Formatted export data
        """
        try:
            # Get comprehensive sales data
            analytics = SalesAnalytics()

            summary = get_sales_summary(months_back)
            trends = analytics.get_revenue_trends(months_back)
            top_performers = analytics.get_top_performers(50, "revenue", months_back)
            warehouse_comparison = analytics.analyze_warehouse_split(months_back)

            export_data = {
                "summary": summary,
                "trends": trends,
                "top_performers": top_performers,
                "warehouse_comparison": warehouse_comparison,
                "export_timestamp": "2025-01-15T10:30:00Z",  # Current timestamp
                "parameters": {
                    "months_analyzed": months_back,
                    "format": format
                }
            }

            return {
                "success": True,
                "data": export_data,
                "format": format
            }
        except Exception as e:
            logger.error(f"Error exporting sales summary: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/sales/seasonal-analysis")
    async def get_seasonal_analysis(
        sku_id: Optional[str] = Query(None, description="Specific SKU to analyze"),
        warehouse: str = Query("kentucky", regex="^(kentucky|burnaby)$", description="Warehouse to analyze"),
        years_back: int = Query(3, ge=1, le=5, description="Years of historical data"),
        min_confidence: float = Query(0.6, ge=0.0, le=1.0, description="Minimum confidence threshold"),
        limit: int = Query(50, ge=1, le=500, description="Maximum SKUs to analyze if no specific SKU")
    ) -> Dict[str, Any]:
        """
        Get seasonal pattern analysis for SKUs.

        This endpoint leverages the existing comprehensive seasonal analysis module
        to provide monthly seasonal factors, confidence levels, and pattern classification.

        Args:
            sku_id: Optional specific SKU to analyze (if None, analyzes top seasonal SKUs)
            warehouse: Warehouse to analyze ('kentucky' or 'burnaby')
            years_back: Number of years of historical data to analyze
            min_confidence: Minimum confidence threshold for reliable patterns
            limit: Maximum number of SKUs to return if analyzing multiple

        Returns:
            Seasonal analysis results with monthly factors and statistical significance
        """
        try:
            analyzer = SeasonalAnalyzer(
                min_months_required=18,
                significance_threshold=0.15,
                min_confidence_level=min_confidence
            )

            if sku_id:
                # Analyze specific SKU
                logger.info(f"Analyzing seasonal patterns for {sku_id} ({warehouse})")

                analysis = analyzer.analyze_sku_seasonality(sku_id, years_back, warehouse)

                # Add business-friendly fields for frontend
                is_significant = analysis.get('statistical_significance', {}).get('is_significant', False)
                pattern_strength = analysis.get('pattern_strength', 0)

                # More practical business logic: consider patterns with strength > 0.4 or statistically significant
                has_business_pattern = is_significant or pattern_strength > 0.4

                analysis.update({
                    'has_seasonal_pattern': has_business_pattern,
                    'business_significance': 'Strong' if pattern_strength > 0.7 else 'Moderate' if pattern_strength > 0.4 else 'Weak'
                })

                return {
                    "success": True,
                    "data": [analysis],  # Return as array for consistency
                    "parameters": {
                        "sku_id": sku_id,
                        "warehouse": warehouse,
                        "years_back": years_back,
                        "min_confidence": min_confidence
                    }
                }
            else:
                # Analyze multiple seasonal SKUs
                logger.info(f"Bulk seasonal analysis for {warehouse} warehouse (confidence >= {min_confidence})")

                # Get SKUs with existing seasonal patterns first
                query = """
                SELECT s.sku_id, s.description, s.seasonal_pattern, s.abc_code
                FROM skus s
                WHERE s.seasonal_pattern != 'unknown'
                    AND s.seasonal_pattern IS NOT NULL
                    AND s.status = 'Active'
                ORDER BY
                    CASE s.abc_code
                        WHEN 'A' THEN 1
                        WHEN 'B' THEN 2
                        WHEN 'C' THEN 3
                        ELSE 4
                    END,
                    s.sku_id
                LIMIT %s
                """

                seasonal_skus = execute_query(query, (limit,))

                if not seasonal_skus:
                    return {
                        "success": True,
                        "data": [],
                        "message": "No SKUs with seasonal patterns found",
                        "parameters": {
                            "warehouse": warehouse,
                            "years_back": years_back,
                            "min_confidence": min_confidence,
                            "limit": limit
                        }
                    }

                # Analyze each SKU
                results = []
                successful = 0
                errors = 0

                for sku_record in seasonal_skus:
                    try:
                        sku_analysis = analyzer.analyze_sku_seasonality(
                            sku_record['sku_id'], years_back, warehouse
                        )

                        # Add metadata from SKU record
                        sku_analysis.update({
                            'description': sku_record['description'],
                            'abc_code': sku_record['abc_code'],
                            'original_seasonal_pattern': sku_record['seasonal_pattern']
                        })

                        # Add business-friendly fields for frontend
                        is_significant = sku_analysis.get('statistical_significance', {}).get('is_significant', False)
                        pattern_strength = sku_analysis.get('pattern_strength', 0)

                        # More practical business logic: consider patterns with strength > 0.4 or statistically significant
                        has_business_pattern = is_significant or pattern_strength > 0.4

                        sku_analysis.update({
                            'has_seasonal_pattern': has_business_pattern,
                            'business_significance': 'Strong' if pattern_strength > 0.7 else 'Moderate' if pattern_strength > 0.4 else 'Weak'
                        })

                        # Filter by confidence if specified
                        confidence_level = sku_analysis.get('statistical_significance', {}).get('confidence_level', 0.0)
                        if confidence_level >= min_confidence:
                            results.append(sku_analysis)
                            successful += 1

                    except Exception as e:
                        errors += 1
                        logger.error(f"Failed to analyze {sku_record.get('sku_id', 'unknown')}: {e}")

                # Sort by pattern strength (strongest patterns first)
                results.sort(key=lambda x: x.get('pattern_strength', 0), reverse=True)

                return {
                    "success": True,
                    "data": results,
                    "summary": {
                        "total_analyzed": len(seasonal_skus),
                        "reliable_patterns": successful,
                        "errors": errors,
                        "confidence_threshold": min_confidence
                    },
                    "parameters": {
                        "warehouse": warehouse,
                        "years_back": years_back,
                        "min_confidence": min_confidence,
                        "limit": limit
                    }
                }

        except Exception as e:
            logger.error(f"Error in seasonal analysis: {e}")
            raise HTTPException(status_code=500, detail=f"Seasonal analysis failed: {str(e)}")

    @app.get("/api/sales/growth-analysis")
    async def get_growth_analysis(
        periods: str = Query("3,6,12", description="Comma-separated list of months periods to analyze"),
        warehouse: Optional[str] = Query(None, regex="^(kentucky|burnaby)$", description="Warehouse filter"),
        include_trends: bool = Query(True, description="Include trend acceleration/deceleration analysis")
    ) -> Dict[str, Any]:
        """
        Get comprehensive growth rate analysis for multiple time periods.

        Provides YoY, QoQ, MoM growth calculations with trend analysis and
        acceleration/deceleration indicators for strategic planning.

        Args:
            periods: Comma-separated list of month periods (e.g., "3,6,12")
            warehouse: Optional warehouse filter ('kentucky', 'burnaby', or None for both)
            include_trends: Whether to include trend acceleration/deceleration analysis

        Returns:
            Growth analysis with period comparisons, trend indicators, and strategic insights
        """
        try:
            # Parse periods parameter
            try:
                period_list = [int(p.strip()) for p in periods.split(",") if p.strip().isdigit()]
                if not period_list:
                    raise ValueError("No valid periods provided")

                # Validate periods (reasonable limits)
                period_list = [p for p in period_list if 1 <= p <= 36]
                if not period_list:
                    raise ValueError("No periods within valid range (1-36 months)")

            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid periods parameter: {str(e)}")

            logger.info(f"Calculating growth analysis for periods: {period_list}, warehouse: {warehouse}")

            # Calculate growth rates using the new function
            growth_analysis = calculate_growth_rates(periods=period_list, warehouse=warehouse)

            if 'error' in growth_analysis:
                raise HTTPException(status_code=500, detail=f"Growth calculation error: {growth_analysis['error']}")

            # Add strategic insights based on growth patterns
            strategic_insights = []

            if growth_analysis.get('periods'):
                for period_key, period_data in growth_analysis['periods'].items():
                    period_months = period_data.get('period_months')
                    pop_growth = period_data.get('pop_growth_rate', 0)
                    yoy_growth = period_data.get('yoy_growth_rate', 0)
                    classification = period_data.get('trend_classification', 'stable')

                    # Generate strategic insights
                    if pop_growth > 15:
                        strategic_insights.append({
                            'period': period_months,
                            'type': 'opportunity',
                            'message': f"Strong {period_months}-month growth ({pop_growth:.1f}%) - consider expanding inventory"
                        })
                    elif pop_growth < -10:
                        strategic_insights.append({
                            'period': period_months,
                            'type': 'concern',
                            'message': f"Declining {period_months}-month performance ({pop_growth:.1f}%) - review strategy"
                        })

                    # YoY vs recent performance comparison
                    if abs(yoy_growth - pop_growth) > 10:
                        if yoy_growth > pop_growth:
                            strategic_insights.append({
                                'period': period_months,
                                'type': 'warning',
                                'message': f"Recent {period_months}-month performance below annual trend"
                            })
                        else:
                            strategic_insights.append({
                                'period': period_months,
                                'type': 'positive',
                                'message': f"Recent {period_months}-month performance exceeds annual trend"
                            })

            # Add trend insights if requested
            if include_trends and growth_analysis.get('trend_analysis'):
                trend_analysis = growth_analysis['trend_analysis']
                direction = trend_analysis.get('direction', 'stable')
                strength = trend_analysis.get('strength', 'weak')

                if direction == 'accelerating' and strength in ['strong_positive', 'consistent_positive']:
                    strategic_insights.append({
                        'type': 'strategic',
                        'message': 'Business momentum is accelerating - consider aggressive growth strategies'
                    })
                elif direction == 'decelerating' and strength in ['strong_negative', 'consistent_negative']:
                    strategic_insights.append({
                        'type': 'strategic',
                        'message': 'Business momentum is declining - implement corrective measures'
                    })

            # Prepare response
            response = {
                "success": True,
                "data": growth_analysis,
                "strategic_insights": strategic_insights,
                "parameters": {
                    "periods": period_list,
                    "warehouse": warehouse or "both",
                    "include_trends": include_trends
                }
            }

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in growth analysis: {e}")
            raise HTTPException(status_code=500, detail=f"Growth analysis failed: {str(e)}")

    @app.get("/api/sales/stockout-details")
    async def get_stockout_details(
        months_back: int = Query(12, ge=1, le=36, description="Number of months to analyze"),
        warehouse: Optional[str] = Query(None, regex="^(kentucky|burnaby)$", description="Warehouse filter"),
        min_impact: float = Query(100.0, ge=0, description="Minimum revenue loss threshold"),
        priority_filter: Optional[str] = Query(None, regex="^(critical|high|medium|low)$", description="Priority filter")
    ) -> Dict[str, Any]:
        """
        Get detailed stockout impact analysis with SKU-level breakdown and recovery projections.

        This endpoint provides comprehensive stockout analysis including revenue loss projections,
        recovery time estimates, severity scoring, and actionable recommendations for inventory
        investment decisions.

        Args:
            months_back: Number of months to analyze for impact calculation (1-36)
            warehouse: Optional warehouse filter ('kentucky', 'burnaby', or None for both)
            min_impact: Minimum estimated revenue loss threshold for inclusion
            priority_filter: Optional priority filter (critical, high, medium, low)

        Returns:
            Detailed stockout impact analysis with recovery projections and recommendations
        """
        try:
            logger.info(f"Calculating stockout details for {months_back} months, warehouse: {warehouse}")

            # Calculate detailed stockout impact
            stockout_analysis = calculate_detailed_stockout_impact(
                months_back=months_back,
                warehouse=warehouse,
                min_impact=min_impact
            )

            if 'error' in stockout_analysis:
                raise HTTPException(status_code=500, detail=f"Stockout analysis error: {stockout_analysis['error']}")

            # Apply priority filter if specified
            if priority_filter and stockout_analysis.get('skus'):
                filtered_skus = [sku for sku in stockout_analysis['skus']
                               if sku.get('priority') == priority_filter]
                stockout_analysis['skus'] = filtered_skus

                # Recalculate summary for filtered results
                if filtered_skus:
                    filtered_revenue = sum(sku.get('estimated_lost_revenue', 0) for sku in filtered_skus)
                    filtered_units = sum(sku.get('estimated_lost_units', 0) for sku in filtered_skus)
                    filtered_recovery_times = [sku.get('estimated_recovery_days', 0) for sku in filtered_skus]
                    avg_recovery = sum(filtered_recovery_times) / len(filtered_recovery_times) if filtered_recovery_times else 0

                    stockout_analysis['summary'].update({
                        'filtered_skus_count': len(filtered_skus),
                        'filtered_lost_revenue': round(filtered_revenue, 2),
                        'filtered_lost_units': round(filtered_units, 2),
                        'filtered_avg_recovery_days': round(avg_recovery, 1)
                    })

            # Add operational insights based on analysis
            operational_insights = []

            summary = stockout_analysis.get('summary', {})
            total_lost_revenue = summary.get('total_estimated_lost_revenue', 0)
            priority_breakdown = summary.get('priority_breakdown', {})

            # Generate insights
            if total_lost_revenue > 50000:
                operational_insights.append({
                    'type': 'financial_impact',
                    'severity': 'high',
                    'message': f"High financial impact: ${total_lost_revenue:,.2f} in estimated lost revenue"
                })

            critical_count = priority_breakdown.get('critical', 0)
            if critical_count > 0:
                operational_insights.append({
                    'type': 'urgent_action',
                    'severity': 'critical',
                    'message': f"{critical_count} SKUs require immediate attention to prevent further losses"
                })

            # Recovery time insights
            avg_recovery = summary.get('avg_recovery_time_days', 0)
            if avg_recovery > 30:
                operational_insights.append({
                    'type': 'process_improvement',
                    'severity': 'medium',
                    'message': f"Average recovery time of {avg_recovery:.1f} days suggests need for faster replenishment processes"
                })

            # ROI insights
            recommendations = stockout_analysis.get('recommendations', {})
            roi_improvement = recommendations.get('estimated_roi_improvement', 0)
            if roi_improvement > 5:
                operational_insights.append({
                    'type': 'investment_opportunity',
                    'severity': 'positive',
                    'message': f"High ROI potential: {roi_improvement:.1f}x return on inventory investment improvements"
                })

            # Prepare response
            response = {
                "success": True,
                "data": stockout_analysis,
                "operational_insights": operational_insights,
                "parameters": {
                    "months_back": months_back,
                    "warehouse": warehouse or "both",
                    "min_impact": min_impact,
                    "priority_filter": priority_filter
                },
                "metadata": {
                    "analysis_scope": "detailed_stockout_impact",
                    "includes_recovery_estimates": True,
                    "includes_priority_scoring": True,
                    "includes_trend_analysis": True
                }
            }

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in stockout details analysis: {e}")
            raise HTTPException(status_code=500, detail=f"Stockout details analysis failed: {str(e)}")

    @app.get("/api/sales/bottom-performers")
    async def get_bottom_performers(
        months_back: int = Query(12, ge=3, le=36, description="Number of months to analyze"),
        warehouse: Optional[str] = Query(None, regex="^(kentucky|burnaby)$", description="Warehouse filter"),
        velocity_threshold: float = Query(2.0, ge=0.1, le=10.0, description="Monthly velocity threshold for slow-moving"),
        turnover_threshold: float = Query(1.0, ge=0.1, le=5.0, description="Annual turnover threshold"),
        margin_threshold: float = Query(0.15, ge=0.0, le=1.0, description="Gross margin threshold"),
        urgency_filter: Optional[str] = Query(None, regex="^(critical|high|medium)$", description="Urgency level filter")
    ) -> Dict[str, Any]:
        """
        Identify SKUs that are candidates for liquidation or discontinuation.

        This endpoint analyzes slow-moving inventory across multiple dimensions including
        sales velocity, turnover rates, profitability, and sales frequency to identify
        items that tie up cash and storage space.

        Args:
            months_back: Number of months of sales history to analyze (3-36)
            warehouse: Optional warehouse filter ('kentucky', 'burnaby', or None for both)
            velocity_threshold: Monthly sales velocity threshold - SKUs below this are flagged
            turnover_threshold: Annual inventory turnover threshold - low turnover indicates poor performance
            margin_threshold: Gross margin threshold - items below this may be unprofitable
            urgency_filter: Optional filter by urgency level (critical, high, medium)

        Returns:
            Comprehensive bottom performer analysis with liquidation recommendations
        """
        try:
            logger.info(f"Identifying bottom performers: {months_back} months, warehouse: {warehouse}")

            # Call the analysis function
            bottom_analysis = identify_bottom_performers(
                months_back=months_back,
                warehouse=warehouse,
                velocity_threshold=velocity_threshold,
                turnover_threshold=turnover_threshold,
                margin_threshold=margin_threshold
            )

            if 'error' in bottom_analysis:
                raise HTTPException(status_code=500, detail=f"Bottom performers analysis error: {bottom_analysis['error']}")

            # Apply urgency filter if specified
            filtered_data = bottom_analysis
            if urgency_filter and bottom_analysis.get('all_bottom_performers'):
                filtered_performers = [
                    performer for performer in bottom_analysis['all_bottom_performers']
                    if performer.get('liquidation_analysis', {}).get('urgency_level') == urgency_filter
                ]

                # Update the filtered results
                filtered_data = bottom_analysis.copy()
                filtered_data['all_bottom_performers'] = filtered_performers
                filtered_data['liquidation_candidates'] = [
                    candidate for candidate in bottom_analysis.get('liquidation_candidates', [])
                    if candidate.get('liquidation_analysis', {}).get('urgency_level') == urgency_filter
                ]

                # Update summary for filtered results
                total_filtered_value = sum(
                    performer.get('financial_impact', {}).get('inventory_value', 0)
                    for performer in filtered_performers
                )
                filtered_data['summary']['filtered_results'] = {
                    'count': len(filtered_performers),
                    'total_inventory_value': round(total_filtered_value, 2),
                    'urgency_filter': urgency_filter
                }

            # Generate business insights
            business_insights = []
            summary = filtered_data.get('summary', {})

            total_value_tied_up = summary.get('total_inventory_value_tied_up', 0)
            critical_count = summary.get('critical_liquidation_candidates', 0)
            death_row_count = summary.get('death_row_items', 0)

            # Cash flow insights
            if total_value_tied_up > 500000:
                business_insights.append({
                    'type': 'cash_flow',
                    'severity': 'high',
                    'message': f"${total_value_tied_up:,.0f} tied up in slow-moving inventory - significant cash flow opportunity"
                })

            # Operational efficiency insights
            if critical_count > 10:
                business_insights.append({
                    'type': 'operational',
                    'severity': 'critical',
                    'message': f"{critical_count} critical liquidation candidates require immediate action"
                })

            # Death row insights
            if death_row_count > 0:
                business_insights.append({
                    'type': 'discontinuation',
                    'severity': 'urgent',
                    'message': f"{death_row_count} death row items need immediate liquidation to free up space"
                })

            # Strategic recommendations based on analysis
            strategic_recommendations = []

            avg_liquidation_score = summary.get('average_liquidation_score', 0)
            if avg_liquidation_score > 0.6:
                strategic_recommendations.append({
                    'priority': 'high',
                    'category': 'procurement_review',
                    'action': 'Review procurement practices to reduce future slow-moving inventory',
                    'expected_impact': 'Reduce future inventory carrying costs by 15-25%'
                })

            if total_value_tied_up > 250000:
                strategic_recommendations.append({
                    'priority': 'medium',
                    'category': 'liquidation_strategy',
                    'action': 'Implement systematic liquidation program with tiered discounting',
                    'expected_impact': f'Recover ${total_value_tied_up * 0.6:,.0f} in working capital'
                })

            # Prepare comprehensive response
            response = {
                "success": True,
                "data": filtered_data,
                "business_insights": business_insights,
                "strategic_recommendations": strategic_recommendations,
                "parameters": {
                    "months_back": months_back,
                    "warehouse": warehouse or "both",
                    "velocity_threshold": velocity_threshold,
                    "turnover_threshold": turnover_threshold,
                    "margin_threshold": margin_threshold,
                    "urgency_filter": urgency_filter
                },
                "metadata": {
                    "analysis_scope": "bottom_performers_liquidation",
                    "includes_financial_impact": True,
                    "includes_death_row_status": True,
                    "includes_trend_analysis": True,
                    "scoring_methodology": "composite_score_velocity_turnover_margin_frequency_recency"
                }
            }

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in bottom performers analysis: {e}")
            raise HTTPException(status_code=500, detail=f"Bottom performers analysis failed: {str(e)}")

    @app.get("/api/health/sales")
    async def sales_health_check() -> Dict[str, Any]:
        """
        Health check endpoint for sales analytics system.

        Returns:
            System health status and basic metrics
        """
        try:
            # Test database connectivity and basic queries
            analytics = SalesAnalytics()
            test_summary = get_sales_summary(1)  # Test with minimal data

            return {
                "status": "healthy",
                "timestamp": "2025-01-15T10:30:00Z",
                "services": {
                    "database": "connected",
                    "sales_analytics": "operational",
                    "sku_analytics": "operational"
                },
                "last_data_update": test_summary.get('last_updated', 'unknown')
            }
        except Exception as e:
            logger.error(f"Sales health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": "Service unavailable",
                "timestamp": "2025-01-15T10:30:00Z"
            }

    @app.get("/api/sales/active-skus")
    async def get_active_skus() -> Dict[str, Any]:
        """
        Get all active SKUs for dropdown lists, particularly for seasonal analysis.

        Returns simplified SKU list with ID and description only, optimized for dropdowns.
        Unlike the paginated all-skus endpoint, this returns all active SKUs at once.

        Returns:
            List of all active SKUs with sku_id and description
        """
        try:
            query = """
                SELECT sku_id, description
                FROM skus
                WHERE status = 'Active'
                ORDER BY sku_id
            """

            skus = execute_query(query)

            return {
                "success": True,
                "data": [
                    {
                        "sku_id": sku['sku_id'],
                        "description": sku['description'] or "No Description"
                    }
                    for sku in (skus or [])
                ],
                "total_count": len(skus or [])
            }

        except Exception as e:
            logger.error(f"Error getting active SKUs: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")