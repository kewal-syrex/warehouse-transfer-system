-- ===================================================================
-- Stockout Management Enhancement - Database Schema Updates
-- Version: 1.1
-- Date: September 2025
-- Purpose: Add enhanced stockout tracking and seasonal pattern detection
-- ===================================================================

USE warehouse_transfer;

-- ===================================================================
-- Add New Fields to SKUs Table for Enhanced Tracking
-- ===================================================================

-- Add seasonal pattern detection field
ALTER TABLE skus ADD COLUMN seasonal_pattern VARCHAR(20) DEFAULT 'unknown' 
COMMENT 'Auto-detected seasonal pattern: spring_summer, fall_winter, holiday, year_round, unknown';

-- Add growth status tracking field  
ALTER TABLE skus ADD COLUMN growth_status ENUM('normal', 'viral', 'declining', 'unknown') DEFAULT 'unknown'
COMMENT 'Growth pattern: viral (2x+ growth), declining (<50% of previous), normal, unknown';

-- Add last stockout date for quick reference
ALTER TABLE skus ADD COLUMN last_stockout_date DATE NULL
COMMENT 'Most recent stockout date for quick dashboard display';

-- Add seasonal peak months field
ALTER TABLE skus ADD COLUMN peak_months VARCHAR(50) NULL
COMMENT 'Comma-separated list of peak sales months (1-12)';

-- Update the updated_at timestamp when these fields change
ALTER TABLE skus MODIFY COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- ===================================================================
-- Enhance Stockout Dates Table with Better Indexing
-- ===================================================================

-- Add composite index for better performance on common queries
CREATE INDEX idx_stockout_sku_warehouse_date ON stockout_dates(sku_id, warehouse, stockout_date DESC);

-- Add index for unresolved stockouts (dashboard queries)
CREATE INDEX idx_unresolved_stockouts ON stockout_dates(is_resolved, stockout_date DESC) 
WHERE is_resolved = FALSE;

-- Add index for date range queries
CREATE INDEX idx_stockout_date_range ON stockout_dates(stockout_date, warehouse);

-- ===================================================================
-- Add New Table for Stockout Pattern Analysis
-- ===================================================================

CREATE TABLE stockout_patterns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50) NOT NULL,
    pattern_type ENUM('seasonal', 'day_of_week', 'monthly', 'chronic') NOT NULL,
    pattern_value VARCHAR(100) NOT NULL COMMENT 'Pattern details (e.g., "april,may,june" or "monday,friday")',
    frequency_score DECIMAL(5,2) DEFAULT 0 COMMENT 'How often this pattern occurs (0-100)',
    last_detected DATE NOT NULL,
    confidence_level ENUM('low', 'medium', 'high') DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_pattern_sku (sku_id),
    INDEX idx_pattern_type (pattern_type),
    INDEX idx_pattern_confidence (confidence_level, frequency_score DESC),
    UNIQUE KEY unique_sku_pattern (sku_id, pattern_type, pattern_value)
);

-- ===================================================================
-- Add Table for Demand Correction History
-- ===================================================================

CREATE TABLE demand_corrections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50) NOT NULL,
    year_month VARCHAR(7) NOT NULL,
    original_sales INT DEFAULT 0,
    stockout_days INT DEFAULT 0,
    correction_method ENUM('availability_rate', 'historical_average', 'category_average', 'year_over_year') NOT NULL,
    corrected_demand DECIMAL(10,2) NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.5 COMMENT 'Confidence in correction (0.0-1.0)',
    correction_notes TEXT COMMENT 'Explanation of correction methodology',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_demand_sku_month (sku_id, year_month),
    INDEX idx_demand_method (correction_method),
    INDEX idx_demand_confidence (confidence_score DESC),
    UNIQUE KEY unique_sku_month_correction (sku_id, year_month)
);

-- ===================================================================
-- Add Table for Quick Stockout Updates Audit
-- ===================================================================

CREATE TABLE stockout_updates_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    update_batch_id VARCHAR(36) NOT NULL COMMENT 'UUID for grouping bulk updates',
    sku_id VARCHAR(50) NOT NULL,
    warehouse ENUM('burnaby', 'kentucky') NOT NULL,
    action ENUM('mark_out', 'mark_in') NOT NULL,
    previous_status ENUM('in_stock', 'out_of_stock', 'unknown') DEFAULT 'unknown',
    new_status ENUM('in_stock', 'out_of_stock') NOT NULL,
    stockout_date DATE NOT NULL,
    resolution_date DATE NULL,
    update_source ENUM('quick_ui', 'csv_import', 'api_direct', 'system_auto') DEFAULT 'quick_ui',
    user_notes TEXT,
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_update_batch (update_batch_id),
    INDEX idx_update_sku (sku_id, created_at DESC),
    INDEX idx_update_source (update_source, created_at DESC),
    INDEX idx_update_date (created_at DESC)
);

-- ===================================================================
-- Enhanced Views for Stockout Analysis
-- ===================================================================

-- View for current stockouts with enhanced details
CREATE OR REPLACE VIEW v_current_stockouts_enhanced AS
SELECT 
    sd.sku_id,
    s.description,
    s.category,
    s.seasonal_pattern,
    s.growth_status,
    sd.warehouse,
    sd.stockout_date,
    DATEDIFF(CURDATE(), sd.stockout_date) as days_out,
    ic.burnaby_qty,
    ic.kentucky_qty,
    CASE 
        WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 30 THEN 'CRITICAL'
        WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 14 THEN 'HIGH'
        WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 7 THEN 'MEDIUM'
        ELSE 'LOW'
    END as urgency_level,
    -- Estimated lost sales (using corrected demand if available)
    CASE 
        WHEN ms.corrected_demand_kentucky > 0 AND sd.warehouse = 'kentucky' THEN
            (ms.corrected_demand_kentucky / 30) * DATEDIFF(CURDATE(), sd.stockout_date)
        WHEN ms.corrected_demand_burnaby > 0 AND sd.warehouse = 'burnaby' THEN
            (ms.corrected_demand_burnaby / 30) * DATEDIFF(CURDATE(), sd.stockout_date)
        ELSE 0
    END as estimated_lost_sales,
    s.cost_per_unit,
    s.abc_code,
    s.xyz_code
FROM stockout_dates sd
INNER JOIN skus s ON sd.sku_id = s.sku_id
LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id 
    AND ms.year_month = DATE_FORMAT(CURDATE(), '%Y-%m')
WHERE sd.is_resolved = FALSE
    AND s.status = 'Active'
ORDER BY 
    CASE urgency_level
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2  
        WHEN 'MEDIUM' THEN 3
        ELSE 4
    END,
    sd.stockout_date ASC;

-- View for stockout patterns and trends
CREATE OR REPLACE VIEW v_stockout_trends AS
SELECT 
    s.sku_id,
    s.description,
    s.category,
    s.seasonal_pattern,
    COUNT(DISTINCT sd.stockout_date) as total_stockout_events,
    AVG(CASE 
        WHEN sd.resolved_date IS NOT NULL 
        THEN DATEDIFF(sd.resolved_date, sd.stockout_date)
        ELSE DATEDIFF(CURDATE(), sd.stockout_date)
    END) as avg_stockout_duration,
    MAX(sd.stockout_date) as last_stockout_date,
    COUNT(CASE WHEN sd.stockout_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH) THEN 1 END) as recent_stockouts,
    -- Pattern detection
    GROUP_CONCAT(DISTINCT MONTH(sd.stockout_date) ORDER BY MONTH(sd.stockout_date)) as stockout_months,
    GROUP_CONCAT(DISTINCT DAYOFWEEK(sd.stockout_date) ORDER BY DAYOFWEEK(sd.stockout_date)) as stockout_days_of_week
FROM skus s
LEFT JOIN stockout_dates sd ON s.sku_id = sd.sku_id
WHERE s.status = 'Active'
    AND sd.stockout_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
GROUP BY s.sku_id, s.description, s.category, s.seasonal_pattern
HAVING total_stockout_events > 0
ORDER BY recent_stockouts DESC, total_stockout_events DESC;

-- ===================================================================
-- Stored Procedures for Enhanced Stockout Management
-- ===================================================================

DELIMITER //

-- Procedure to detect seasonal patterns for a SKU
CREATE PROCEDURE DetectSeasonalPattern(IN p_sku_id VARCHAR(50))
BEGIN
    DECLARE v_pattern VARCHAR(20) DEFAULT 'unknown';
    DECLARE v_peak_months VARCHAR(50) DEFAULT '';
    DECLARE v_spring_summer_score INT DEFAULT 0;
    DECLARE v_fall_winter_score INT DEFAULT 0;
    DECLARE v_holiday_score INT DEFAULT 0;
    DECLARE v_variance DECIMAL(10,2) DEFAULT 0;
    
    -- Calculate monthly sales averages for pattern detection
    SELECT 
        SUM(CASE WHEN MONTH(CONCAT(year_month, '-01')) IN (4,5,6,7,8) THEN kentucky_sales END) as spring_summer,
        SUM(CASE WHEN MONTH(CONCAT(year_month, '-01')) IN (9,10,1,2,3) THEN kentucky_sales END) as fall_winter,
        SUM(CASE WHEN MONTH(CONCAT(year_month, '-01')) IN (11,12) THEN kentucky_sales END) as holiday,
        VARIANCE(kentucky_sales) as sales_variance
    INTO v_spring_summer_score, v_fall_winter_score, v_holiday_score, v_variance
    FROM monthly_sales 
    WHERE sku_id = p_sku_id 
        AND year_month >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 24 MONTH), '%Y-%m');
    
    -- Determine pattern based on scores
    IF v_variance < 100 THEN
        SET v_pattern = 'year_round';
    ELSEIF v_holiday_score > (v_spring_summer_score + v_fall_winter_score) * 0.4 THEN
        SET v_pattern = 'holiday';
        SET v_peak_months = '11,12';
    ELSEIF v_spring_summer_score > v_fall_winter_score * 1.3 THEN
        SET v_pattern = 'spring_summer';
        SET v_peak_months = '4,5,6,7,8';
    ELSEIF v_fall_winter_score > v_spring_summer_score * 1.3 THEN
        SET v_pattern = 'fall_winter';
        SET v_peak_months = '9,10,1,2,3';
    ELSE
        SET v_pattern = 'year_round';
    END IF;
    
    -- Update the SKU with detected pattern
    UPDATE skus 
    SET seasonal_pattern = v_pattern,
        peak_months = v_peak_months,
        updated_at = NOW()
    WHERE sku_id = p_sku_id;
    
    SELECT v_pattern as detected_pattern, v_peak_months as peak_months;
END //

-- Procedure to detect viral growth
CREATE PROCEDURE DetectViralGrowth(IN p_sku_id VARCHAR(50))
BEGIN
    DECLARE v_recent_avg DECIMAL(10,2) DEFAULT 0;
    DECLARE v_previous_avg DECIMAL(10,2) DEFAULT 0;
    DECLARE v_growth_rate DECIMAL(5,2) DEFAULT 0;
    DECLARE v_growth_status VARCHAR(20) DEFAULT 'normal';
    
    -- Calculate recent 3 months average
    SELECT AVG(kentucky_sales) INTO v_recent_avg
    FROM monthly_sales 
    WHERE sku_id = p_sku_id 
        AND year_month >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y-%m');
    
    -- Calculate previous 3 months average
    SELECT AVG(kentucky_sales) INTO v_previous_avg
    FROM monthly_sales 
    WHERE sku_id = p_sku_id 
        AND year_month BETWEEN DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%Y-%m')
        AND DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 4 MONTH), '%Y-%m');
    
    -- Calculate growth rate
    IF v_previous_avg > 0 THEN
        SET v_growth_rate = v_recent_avg / v_previous_avg;
        
        IF v_growth_rate >= 2.0 THEN
            SET v_growth_status = 'viral';
        ELSEIF v_growth_rate <= 0.5 THEN
            SET v_growth_status = 'declining';
        ELSE
            SET v_growth_status = 'normal';
        END IF;
    END IF;
    
    -- Update SKU with growth status
    UPDATE skus 
    SET growth_status = v_growth_status,
        updated_at = NOW()
    WHERE sku_id = p_sku_id;
    
    SELECT v_growth_status as growth_status, v_growth_rate as growth_rate;
END //

DELIMITER ;

-- ===================================================================
-- Update Existing Data with Defaults
-- ===================================================================

-- Set initial values for existing SKUs
UPDATE skus SET 
    seasonal_pattern = 'unknown',
    growth_status = 'unknown',
    last_stockout_date = (
        SELECT MAX(stockout_date) 
        FROM stockout_dates 
        WHERE stockout_dates.sku_id = skus.sku_id 
            AND is_resolved = FALSE
    )
WHERE seasonal_pattern IS NULL OR growth_status IS NULL;

-- ===================================================================
-- Performance Optimization Indexes
-- ===================================================================

-- Additional indexes for new queries
CREATE INDEX idx_skus_seasonal_pattern ON skus(seasonal_pattern, status);
CREATE INDEX idx_skus_growth_status ON skus(growth_status, seasonal_pattern);
CREATE INDEX idx_skus_last_stockout ON skus(last_stockout_date DESC) WHERE last_stockout_date IS NOT NULL;

-- Optimize monthly_sales for correction queries
CREATE INDEX idx_monthly_sales_year_month ON monthly_sales(year_month DESC, sku_id);
CREATE INDEX idx_monthly_sales_corrected ON monthly_sales(sku_id, corrected_demand_kentucky DESC);

-- ===================================================================
-- Triggers for Automatic Data Synchronization
-- ===================================================================

DELIMITER //

-- Trigger to update last_stockout_date when new stockout is added
CREATE TRIGGER tr_stockout_dates_insert 
AFTER INSERT ON stockout_dates
FOR EACH ROW
BEGIN
    IF NEW.is_resolved = FALSE THEN
        UPDATE skus 
        SET last_stockout_date = NEW.stockout_date,
            updated_at = NOW()
        WHERE sku_id = NEW.sku_id;
    END IF;
END //

-- Trigger to update monthly_sales stockout_days when stockout_dates change
CREATE TRIGGER tr_sync_monthly_stockout_days
AFTER INSERT ON stockout_dates
FOR EACH ROW
BEGIN
    DECLARE v_year_month VARCHAR(7);
    DECLARE v_stockout_days INT DEFAULT 0;
    
    SET v_year_month = DATE_FORMAT(NEW.stockout_date, '%Y-%m');
    
    -- Calculate total stockout days for the month
    SELECT COUNT(DISTINCT stockout_date) INTO v_stockout_days
    FROM stockout_dates 
    WHERE sku_id = NEW.sku_id 
        AND warehouse = NEW.warehouse
        AND DATE_FORMAT(stockout_date, '%Y-%m') = v_year_month;
    
    -- Update monthly_sales table
    INSERT INTO monthly_sales (year_month, sku_id, kentucky_stockout_days, burnaby_stockout_days)
    VALUES (
        v_year_month, 
        NEW.sku_id,
        CASE WHEN NEW.warehouse = 'kentucky' THEN v_stockout_days ELSE 0 END,
        CASE WHEN NEW.warehouse = 'burnaby' THEN v_stockout_days ELSE 0 END
    )
    ON DUPLICATE KEY UPDATE
        kentucky_stockout_days = CASE WHEN NEW.warehouse = 'kentucky' THEN v_stockout_days ELSE kentucky_stockout_days END,
        burnaby_stockout_days = CASE WHEN NEW.warehouse = 'burnaby' THEN v_stockout_days ELSE burnaby_stockout_days END;
END //

DELIMITER ;

-- ===================================================================
-- Sample Data for Testing New Features
-- ===================================================================

-- Add some sample stockout patterns
INSERT INTO stockout_patterns (sku_id, pattern_type, pattern_value, frequency_score, confidence_level)
VALUES 
    ('CHG-001', 'seasonal', 'march,april,may', 75.5, 'high'),
    ('CBL-002', 'day_of_week', 'monday,friday', 60.0, 'medium'),
    ('WDG-003', 'monthly', 'holiday_season', 80.0, 'high');

-- Add sample demand corrections
INSERT INTO demand_corrections (sku_id, year_month, original_sales, stockout_days, correction_method, corrected_demand, confidence_score, correction_notes)
VALUES 
    ('CHG-001', '2024-03', 0, 25, 'year_over_year', 120.0, 0.85, 'Used March 2023 data (110 units) with 10% growth factor'),
    ('CBL-002', '2024-03', 160, 5, 'availability_rate', 192.0, 0.90, 'Applied availability rate correction: 160 / (25/30) = 192');

COMMIT;

-- ===================================================================
-- Verification Queries
-- ===================================================================

-- Verify new columns were added
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'warehouse_transfer' 
    AND TABLE_NAME = 'skus' 
    AND COLUMN_NAME IN ('seasonal_pattern', 'growth_status', 'last_stockout_date', 'peak_months');

-- Verify new tables were created
SELECT TABLE_NAME, TABLE_COMMENT 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'warehouse_transfer' 
    AND TABLE_NAME IN ('stockout_patterns', 'demand_corrections', 'stockout_updates_log');

-- Verify new indexes were created
SELECT INDEX_NAME, COLUMN_NAME, TABLE_NAME 
FROM INFORMATION_SCHEMA.STATISTICS 
WHERE TABLE_SCHEMA = 'warehouse_transfer' 
    AND INDEX_NAME LIKE '%stockout%' 
ORDER BY TABLE_NAME, INDEX_NAME;

-- Test the new views
SELECT COUNT(*) as current_stockouts FROM v_current_stockouts_enhanced;
SELECT COUNT(*) as sku_with_patterns FROM v_stockout_trends;

-- Test the stored procedures
CALL DetectSeasonalPattern('CHG-001');
CALL DetectViralGrowth('CHG-001');

SELECT 'Database schema enhancement completed successfully!' as status;