-- Sales Analytics Enhancement Migration Script
-- Version: V6.0
-- Date: January 2025
-- Purpose: Add database optimizations and new structures for enhanced sales analytics dashboard
--
-- This migration adds performance optimizations and analytical views needed
-- for the comprehensive sales analytics dashboard without affecting
-- existing transfer planning functionality.

USE warehouse_transfer;

-- ==============================================================================
-- Performance Optimization Indexes (Skip existing indexes)
-- ==============================================================================

-- Note: Many needed indexes already exist (idx_monthly_sales_year_month,
-- idx_monthly_sales_sku_year_month, etc.) so we only add missing ones

-- Optimize stockout analysis queries (if not exists)
CREATE INDEX IF NOT EXISTS idx_monthly_sales_stockout_analysis
ON monthly_sales (kentucky_stockout_days, burnaby_stockout_days);

-- Optimize corrected demand queries for stockout impact calculations
CREATE INDEX IF NOT EXISTS idx_monthly_sales_corrected_demand_analysis
ON monthly_sales (corrected_demand_kentucky, corrected_demand_burnaby);

-- Optimize SKU classification queries for ABC-XYZ matrix
CREATE INDEX IF NOT EXISTS idx_skus_abc_xyz_classification
ON skus (abc_code, xyz_code, status);

-- ==============================================================================
-- Sales Analytics Summary View
-- ==============================================================================

-- Create materialized view for sales summary calculations
-- This improves performance for dashboard KPI queries
CREATE OR REPLACE VIEW v_sales_summary_12m AS
SELECT
    COUNT(DISTINCT ms.sku_id) as total_skus,
    SUM(COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) as total_units,
    SUM(COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) as total_revenue,
    AVG(COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) as avg_monthly_revenue,
    AVG(COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) as avg_monthly_sales,
    SUM(COALESCE(ms.kentucky_stockout_days, 0)) as total_stockout_days_ky,
    SUM(COALESCE(ms.burnaby_stockout_days, 0)) as total_stockout_days_ca,
    SUM(COALESCE(ms.corrected_demand_kentucky, ms.kentucky_sales, 0) - COALESCE(ms.kentucky_sales, 0)) as estimated_lost_sales_ky,
    SUM(COALESCE(ms.corrected_demand_burnaby, ms.burnaby_sales, 0) - COALESCE(ms.burnaby_sales, 0)) as estimated_lost_sales_ca
FROM monthly_sales ms
WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 12 MONTH), '%Y-%m');

-- ==============================================================================
-- ABC-XYZ Distribution View
-- ==============================================================================

-- Create view for ABC-XYZ classification matrix data
CREATE OR REPLACE VIEW v_abc_xyz_matrix AS
SELECT
    s.abc_code,
    s.xyz_code,
    CONCAT(s.abc_code, s.xyz_code) as classification,
    COUNT(DISTINCT s.sku_id) as sku_count,
    SUM(revenue_data.total_revenue) as total_revenue,
    AVG(revenue_data.total_revenue) as avg_revenue_per_sku,
    SUM(revenue_data.total_units) as total_units
FROM skus s
LEFT JOIN (
    SELECT
        sku_id,
        SUM(COALESCE(burnaby_revenue, 0) + COALESCE(kentucky_revenue, 0)) as total_revenue,
        SUM(COALESCE(burnaby_sales, 0) + COALESCE(kentucky_sales, 0)) as total_units
    FROM monthly_sales
    WHERE `year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 12 MONTH), '%Y-%m')
    GROUP BY sku_id
) as revenue_data ON s.sku_id = revenue_data.sku_id
WHERE s.status = 'Active'
GROUP BY s.abc_code, s.xyz_code
ORDER BY s.abc_code, s.xyz_code;

-- ==============================================================================
-- SKU Performance Summary View
-- ==============================================================================

-- Create comprehensive view for all SKUs with performance metrics
CREATE OR REPLACE VIEW v_sku_performance_summary AS
SELECT
    s.sku_id,
    s.description,
    s.category,
    s.supplier,
    s.abc_code,
    s.xyz_code,
    s.status,
    COALESCE(perf.total_revenue_12m, 0) as total_revenue_12m,
    COALESCE(perf.total_units_12m, 0) as total_units_12m,
    COALESCE(perf.avg_monthly_revenue, 0) as avg_monthly_revenue,
    COALESCE(perf.avg_monthly_units, 0) as avg_monthly_units,
    COALESCE(perf.avg_selling_price, 0) as avg_selling_price,
    COALESCE(perf.months_with_sales, 0) as months_with_sales,
    COALESCE(perf.stockout_days_total, 0) as stockout_days_total,
    COALESCE(perf.estimated_lost_sales, 0) as estimated_lost_sales,
    COALESCE(perf.growth_rate_6m, 0) as growth_rate_6m,
    COALESCE(ic.kentucky_qty, 0) as current_ky_qty,
    COALESCE(ic.burnaby_qty, 0) as current_ca_qty
FROM skus s
LEFT JOIN (
    SELECT
        ms.sku_id,
        SUM(COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) as total_revenue_12m,
        SUM(COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) as total_units_12m,
        AVG(COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) as avg_monthly_revenue,
        AVG(COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) as avg_monthly_units,
        AVG(CASE
            WHEN (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) > 0
            THEN (COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) / (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0))
            ELSE 0
        END) as avg_selling_price,
        COUNT(CASE WHEN (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) > 0 THEN 1 END) as months_with_sales,
        SUM(COALESCE(ms.kentucky_stockout_days, 0) + COALESCE(ms.burnaby_stockout_days, 0)) as stockout_days_total,
        SUM(COALESCE(ms.corrected_demand_kentucky, ms.kentucky_sales, 0) + COALESCE(ms.corrected_demand_burnaby, ms.burnaby_sales, 0) - COALESCE(ms.kentucky_sales, 0) - COALESCE(ms.burnaby_sales, 0)) as estimated_lost_sales,
        -- Calculate 6-month growth rate
        CASE
            WHEN SUM(CASE
                WHEN ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%Y-%m')
                AND ms.`year_month` < DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y-%m')
                THEN COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)
                ELSE 0
            END) > 0
            THEN ((SUM(CASE
                WHEN ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y-%m')
                THEN COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)
                ELSE 0
            END) - SUM(CASE
                WHEN ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%Y-%m')
                AND ms.`year_month` < DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y-%m')
                THEN COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)
                ELSE 0
            END)) / SUM(CASE
                WHEN ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%Y-%m')
                AND ms.`year_month` < DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y-%m')
                THEN COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)
                ELSE 0
            END) * 100)
            ELSE 0
        END as growth_rate_6m
    FROM monthly_sales ms
    WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 12 MONTH), '%Y-%m')
    GROUP BY ms.sku_id
) as perf ON s.sku_id = perf.sku_id
LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
WHERE s.status = 'Active';

-- ==============================================================================
-- Seasonal Analysis Table (Optional - for caching seasonal patterns)
-- ==============================================================================

-- Create table to cache seasonal patterns for performance
CREATE TABLE IF NOT EXISTS seasonal_patterns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50) NOT NULL,
    month_number INT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    seasonal_index DECIMAL(10,4) DEFAULT 0,
    avg_monthly_sales DECIMAL(15,4) DEFAULT 0,
    data_points INT DEFAULT 0,
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_sku_month (sku_id, month_number),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_seasonal_sku (sku_id),
    INDEX idx_seasonal_month (month_number),
    INDEX idx_seasonal_last_calc (last_calculated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==============================================================================
-- Stockout Impact Analysis View
-- ==============================================================================

-- Create view for stockout impact analysis
CREATE OR REPLACE VIEW v_stockout_impact AS
SELECT
    s.sku_id,
    s.description,
    s.abc_code,
    s.xyz_code,
    SUM(COALESCE(ms.kentucky_stockout_days, 0) + COALESCE(ms.burnaby_stockout_days, 0)) as total_stockout_days,
    SUM(COALESCE(ms.kentucky_sales, 0) + COALESCE(ms.burnaby_sales, 0)) as actual_sales,
    SUM(COALESCE(ms.corrected_demand_kentucky, ms.kentucky_sales, 0) + COALESCE(ms.corrected_demand_burnaby, ms.burnaby_sales, 0)) as potential_sales,
    SUM(COALESCE(ms.corrected_demand_kentucky, ms.kentucky_sales, 0) + COALESCE(ms.corrected_demand_burnaby, ms.burnaby_sales, 0) - COALESCE(ms.kentucky_sales, 0) - COALESCE(ms.burnaby_sales, 0)) as estimated_lost_units,
    -- Estimate lost revenue using average selling price
    SUM(COALESCE(ms.corrected_demand_kentucky, ms.kentucky_sales, 0) + COALESCE(ms.corrected_demand_burnaby, ms.burnaby_sales, 0) - COALESCE(ms.kentucky_sales, 0) - COALESCE(ms.burnaby_sales, 0)) *
    AVG(CASE
        WHEN (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0)) > 0
        THEN (COALESCE(ms.burnaby_revenue, 0) + COALESCE(ms.kentucky_revenue, 0)) / (COALESCE(ms.burnaby_sales, 0) + COALESCE(ms.kentucky_sales, 0))
        ELSE 0
    END) as estimated_lost_revenue
FROM skus s
JOIN monthly_sales ms ON s.sku_id = ms.sku_id
WHERE ms.`year_month` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 12 MONTH), '%Y-%m')
    AND (COALESCE(ms.kentucky_stockout_days, 0) > 0 OR COALESCE(ms.burnaby_stockout_days, 0) > 0)
    AND s.status = 'Active'
GROUP BY s.sku_id, s.description, s.abc_code, s.xyz_code
HAVING total_stockout_days > 0 AND estimated_lost_revenue > 0
ORDER BY estimated_lost_revenue DESC;

-- ==============================================================================
-- Completion Message
-- ==============================================================================

-- Log completion
SELECT 'Sales Analytics Migration V6.0 completed successfully' as Migration_Status;

COMMIT;