-- Performance Index for Transfer Planning Query Optimization
-- This index optimizes the latest sales data lookup in calculate_all_transfer_recommendations()
--
-- Purpose: Accelerate the window function query that finds the latest month with sales data
-- Target Query: Uses ROW_NUMBER() OVER (PARTITION BY sku_id ORDER BY year_month DESC)
-- Expected Impact: 30-40% improvement in database query performance
--
-- Created: September 18, 2025
-- Related: TASK-313.2 - Database Index Optimization

-- Create composite index for monthly_sales table
-- Covers: sku_id (partition), year_month (order), kentucky_sales, burnaby_sales (filter)
-- Note: MariaDB doesn't support DESC in index definition, but optimizer can still use descending order
CREATE INDEX IF NOT EXISTS idx_monthly_sales_latest_data
ON monthly_sales (sku_id, year_month, kentucky_sales, burnaby_sales);

-- Verify index creation
SHOW INDEX FROM monthly_sales WHERE Key_name = 'idx_monthly_sales_latest_data';

-- Optional: Analyze table to update statistics after index creation
ANALYZE TABLE monthly_sales;

-- Performance Notes:
-- 1. This index supports the optimized window function query in calculations.py
-- 2. The DESC order on year_month matches the ORDER BY in the window function
-- 3. Including kentucky_sales and burnaby_sales covers the WHERE clause filter
-- 4. This replaces the need for per-SKU correlated subqueries
--
-- Query Pattern Optimized:
-- SELECT sku_id, year_month, kentucky_sales, burnaby_sales,
--        ROW_NUMBER() OVER (PARTITION BY sku_id ORDER BY year_month DESC) as rn
-- FROM monthly_sales
-- WHERE kentucky_sales > 0 OR burnaby_sales > 0