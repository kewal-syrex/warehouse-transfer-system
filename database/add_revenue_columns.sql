-- Add revenue tracking columns to monthly_sales table
-- This migration adds revenue columns while preserving existing data

USE warehouse_transfer;

-- Add revenue columns to monthly_sales table
ALTER TABLE monthly_sales
ADD COLUMN burnaby_revenue DECIMAL(12,2) DEFAULT 0.00 COMMENT 'Actual revenue from Burnaby warehouse sales',
ADD COLUMN kentucky_revenue DECIMAL(12,2) DEFAULT 0.00 COMMENT 'Actual revenue from Kentucky warehouse sales',
ADD COLUMN total_revenue DECIMAL(12,2) GENERATED ALWAYS AS (burnaby_revenue + kentucky_revenue) STORED COMMENT 'Total revenue across both warehouses',
ADD COLUMN burnaby_avg_revenue DECIMAL(10,2) GENERATED ALWAYS AS (
    CASE
        WHEN burnaby_sales > 0 THEN ROUND(burnaby_revenue / burnaby_sales, 2)
        ELSE 0.00
    END
) STORED COMMENT 'Average revenue per unit for Burnaby sales',
ADD COLUMN kentucky_avg_revenue DECIMAL(10,2) GENERATED ALWAYS AS (
    CASE
        WHEN kentucky_sales > 0 THEN ROUND(kentucky_revenue / kentucky_sales, 2)
        ELSE 0.00
    END
) STORED COMMENT 'Average revenue per unit for Kentucky sales';

-- Add indexes for performance on new revenue columns
CREATE INDEX idx_burnaby_revenue ON monthly_sales(burnaby_revenue);
CREATE INDEX idx_kentucky_revenue ON monthly_sales(kentucky_revenue);
CREATE INDEX idx_total_revenue ON monthly_sales(total_revenue);

-- Create a view for revenue analysis
CREATE OR REPLACE VIEW v_revenue_analysis AS
SELECT
    ms.year_month,
    ms.sku_id,
    s.description,
    s.cost_per_unit,
    ms.burnaby_sales,
    ms.kentucky_sales,
    ms.burnaby_revenue,
    ms.kentucky_revenue,
    ms.total_revenue,
    ms.burnaby_avg_revenue,
    ms.kentucky_avg_revenue,
    -- Calculate overall average revenue per unit
    CASE
        WHEN (ms.burnaby_sales + ms.kentucky_sales) > 0 THEN
            ROUND(ms.total_revenue / (ms.burnaby_sales + ms.kentucky_sales), 2)
        ELSE 0.00
    END as overall_avg_revenue,
    -- Calculate profit margins
    CASE
        WHEN ms.burnaby_avg_revenue > 0 AND s.cost_per_unit > 0 THEN
            ROUND(((ms.burnaby_avg_revenue - s.cost_per_unit) / ms.burnaby_avg_revenue) * 100, 2)
        ELSE 0.00
    END as burnaby_margin_percent,
    CASE
        WHEN ms.kentucky_avg_revenue > 0 AND s.cost_per_unit > 0 THEN
            ROUND(((ms.kentucky_avg_revenue - s.cost_per_unit) / ms.kentucky_avg_revenue) * 100, 2)
        ELSE 0.00
    END as kentucky_margin_percent
FROM monthly_sales ms
INNER JOIN skus s ON ms.sku_id = s.sku_id
WHERE s.status = 'Active';

-- Create view for revenue dashboard metrics
CREATE OR REPLACE VIEW v_revenue_dashboard AS
SELECT
    YEAR(CURDATE()) as current_year,
    MONTH(CURDATE()) as current_month,
    -- Current month revenue
    SUM(CASE WHEN ms.year_month = DATE_FORMAT(CURDATE(), '%Y-%m') THEN ms.total_revenue ELSE 0 END) as revenue_mtd,
    SUM(CASE WHEN ms.year_month = DATE_FORMAT(CURDATE(), '%Y-%m') THEN ms.burnaby_revenue ELSE 0 END) as burnaby_revenue_mtd,
    SUM(CASE WHEN ms.year_month = DATE_FORMAT(CURDATE(), '%Y-%m') THEN ms.kentucky_revenue ELSE 0 END) as kentucky_revenue_mtd,
    -- Current month average revenue per unit (weighted)
    CASE
        WHEN SUM(CASE WHEN ms.year_month = DATE_FORMAT(CURDATE(), '%Y-%m') THEN (ms.burnaby_sales + ms.kentucky_sales) ELSE 0 END) > 0 THEN
            ROUND(
                SUM(CASE WHEN ms.year_month = DATE_FORMAT(CURDATE(), '%Y-%m') THEN ms.total_revenue ELSE 0 END) /
                SUM(CASE WHEN ms.year_month = DATE_FORMAT(CURDATE(), '%Y-%m') THEN (ms.burnaby_sales + ms.kentucky_sales) ELSE 0 END), 2
            )
        ELSE 0.00
    END as avg_revenue_per_unit_mtd,
    -- Previous month for comparison
    SUM(CASE WHEN ms.year_month = DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m') THEN ms.total_revenue ELSE 0 END) as revenue_prev_month,
    -- Year to date
    SUM(CASE WHEN YEAR(STR_TO_DATE(CONCAT(ms.year_month, '-01'), '%Y-%m-%d')) = YEAR(CURDATE()) THEN ms.total_revenue ELSE 0 END) as revenue_ytd
FROM monthly_sales ms
INNER JOIN skus s ON ms.sku_id = s.sku_id
WHERE s.status = 'Active';

COMMIT;