-- Enhanced Calculation Engine Database Migration
-- Version: 2.0
-- Date: September 2025
-- Description: Adds fields for seasonal pattern detection and viral growth tracking

USE warehouse_transfer;

-- ===================================================================
-- Add new fields to skus table for enhanced calculations
-- ===================================================================

ALTER TABLE skus
ADD COLUMN IF NOT EXISTS seasonal_pattern VARCHAR(20) DEFAULT NULL COMMENT 'Auto-detected seasonal pattern: spring_summer, fall_winter, holiday, year_round',
ADD COLUMN IF NOT EXISTS growth_status ENUM('normal', 'viral', 'declining') DEFAULT 'normal' COMMENT 'Growth status based on recent demand trends',
ADD COLUMN IF NOT EXISTS last_stockout_date DATE DEFAULT NULL COMMENT 'Most recent stockout date for the SKU',
ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT NULL COMMENT 'Product category for average calculations' AFTER supplier;

-- Create index for seasonal pattern queries
CREATE INDEX IF NOT EXISTS idx_seasonal_pattern ON skus(seasonal_pattern);
CREATE INDEX IF NOT EXISTS idx_growth_status ON skus(growth_status);
CREATE INDEX IF NOT EXISTS idx_last_stockout ON skus(last_stockout_date);
CREATE INDEX IF NOT EXISTS idx_category ON skus(category);

-- ===================================================================
-- Optimize stockout_dates table for performance
-- ===================================================================

-- Add composite index for faster stockout history queries
CREATE INDEX IF NOT EXISTS idx_stockout_composite ON stockout_dates(sku_id, warehouse, stockout_date DESC);
CREATE INDEX IF NOT EXISTS idx_stockout_year ON stockout_dates(YEAR(stockout_date), MONTH(stockout_date));

-- ===================================================================
-- Add triggers for automatic last_stockout_date updates
-- ===================================================================

DELIMITER //

DROP TRIGGER IF EXISTS update_last_stockout_on_insert//
CREATE TRIGGER update_last_stockout_on_insert
AFTER INSERT ON stockout_dates
FOR EACH ROW
BEGIN
    IF NEW.is_resolved = FALSE THEN
        UPDATE skus
        SET last_stockout_date = NEW.stockout_date
        WHERE sku_id = NEW.sku_id
        AND (last_stockout_date IS NULL OR last_stockout_date < NEW.stockout_date);
    END IF;
END//

DROP TRIGGER IF EXISTS update_last_stockout_on_update//
CREATE TRIGGER update_last_stockout_on_update
AFTER UPDATE ON stockout_dates
FOR EACH ROW
BEGIN
    IF NEW.is_resolved = FALSE AND OLD.is_resolved = TRUE THEN
        UPDATE skus
        SET last_stockout_date = NEW.stockout_date
        WHERE sku_id = NEW.sku_id
        AND (last_stockout_date IS NULL OR last_stockout_date < NEW.stockout_date);
    END IF;
END//

DELIMITER ;

-- ===================================================================
-- Create view for year-over-year comparison
-- ===================================================================

CREATE OR REPLACE VIEW v_year_over_year_sales AS
SELECT
    current.sku_id,
    current.year_month AS current_period,
    current.kentucky_sales AS current_sales,
    current.kentucky_stockout_days AS current_stockout_days,
    previous.year_month AS previous_year_period,
    previous.kentucky_sales AS previous_year_sales,
    previous.kentucky_stockout_days AS previous_year_stockout_days,
    CASE
        WHEN previous.kentucky_sales > 0
        THEN ROUND((current.kentucky_sales - previous.kentucky_sales) / previous.kentucky_sales * 100, 2)
        ELSE NULL
    END AS year_over_year_growth_percent
FROM monthly_sales current
LEFT JOIN monthly_sales previous ON
    current.sku_id = previous.sku_id
    AND previous.year_month = DATE_FORMAT(DATE_SUB(STR_TO_DATE(CONCAT(current.year_month, '-01'), '%Y-%m-%d'), INTERVAL 1 YEAR), '%Y-%m')
ORDER BY current.sku_id, current.year_month DESC;

-- ===================================================================
-- Create view for category averages
-- ===================================================================

CREATE OR REPLACE VIEW v_category_averages AS
SELECT
    s.category,
    COUNT(DISTINCT ms.sku_id) AS sku_count,
    AVG(ms.kentucky_sales) AS avg_monthly_sales,
    AVG(ms.corrected_demand_kentucky) AS avg_corrected_demand,
    MAX(ms.year_month) AS latest_period
FROM skus s
INNER JOIN monthly_sales ms ON s.sku_id = ms.sku_id
WHERE s.status = 'Active'
    AND s.category IS NOT NULL
    AND ms.year_month = (
        SELECT MAX(year_month)
        FROM monthly_sales ms2
        WHERE ms2.sku_id = ms.sku_id
    )
GROUP BY s.category;

-- ===================================================================
-- Update existing data with categories (sample categories)
-- ===================================================================

UPDATE skus SET category = 'Chargers' WHERE sku_id LIKE 'CHG-%' AND category IS NULL;
UPDATE skus SET category = 'Cables' WHERE sku_id LIKE 'CBL-%' AND category IS NULL;
UPDATE skus SET category = 'Electronics' WHERE (sku_id LIKE 'WDG-%' OR sku_id LIKE 'GAD-%') AND category IS NULL;
UPDATE skus SET category = 'Accessories' WHERE sku_id LIKE 'ACC-%' AND category IS NULL;

COMMIT;