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
        Get stockout impact analysis across all SKUs.

        Args:
            months_back: Number of months to analyze

        Returns:
            Stockout impact metrics and affected SKUs
        """
        try:
            analytics = SalesAnalytics()
            impact = analytics.calculate_stockout_impact(months_back)
            return {
                "success": True,
                "data": impact
            }
        except Exception as e:
            logger.error(f"Error getting stockout impact: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

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
        min_revenue: Optional[float] = Query(None, ge=0, description="Minimum revenue filter")
    ) -> Dict[str, Any]:
        """
        Get all SKUs with comprehensive performance metrics and filtering.

        This endpoint returns a paginated list of all active SKUs with their
        performance metrics, supporting various filters and sorting options
        for the All SKUs section of the dashboard.

        Args:
            limit: Maximum number of SKUs to return (1-1000)
            offset: Number of SKUs to skip for pagination
            sort_by: Field to sort by (revenue, units, growth_rate, etc.)
            sort_order: Sort order (asc or desc)
            abc_filter: Filter by ABC classification (A, B, or C)
            xyz_filter: Filter by XYZ classification (X, Y, or Z)
            min_revenue: Minimum revenue threshold

        Returns:
            Paginated list of SKUs with performance metrics and pagination info
        """
        try:
            # Build WHERE clause based on filters
            # Note: Using view column names (not table aliases since we're querying the view)
            where_conditions = ["status = 'Active'"]
            if abc_filter:
                where_conditions.append(f"abc_code = '{abc_filter}'")
            if xyz_filter:
                where_conditions.append(f"xyz_code = '{xyz_filter}'")
            if min_revenue:
                where_conditions.append(f"COALESCE(total_revenue_12m, 0) >= {min_revenue}")

            where_clause = " AND ".join(where_conditions)

            # Use the performance summary view for efficiency
            query = f"""
            SELECT * FROM v_sku_performance_summary
            WHERE {where_clause}
            ORDER BY {sort_by} {sort_order.upper()}
            LIMIT %s OFFSET %s
            """

            # Get total count for pagination
            count_query = f"""
            SELECT COUNT(*) as total FROM v_sku_performance_summary
            WHERE {where_clause}
            """

            skus = execute_query(query, (limit, offset))
            count_result = execute_query(count_query, fetch_one=True)
            total_count = count_result['total'] if count_result else 0

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