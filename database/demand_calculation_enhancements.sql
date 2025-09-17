-- ===================================================================
-- Demand Calculation Enhancement - Database Schema Updates
-- Version: 1.0
-- Date: September 2025
-- Purpose: Add weighted moving averages, volatility calculations, and forecast accuracy tracking
-- ===================================================================

USE warehouse_transfer;

-- ===================================================================
-- Create SKU Demand Statistics Table
-- ===================================================================

CREATE TABLE IF NOT EXISTS sku_demand_stats (
    sku_id VARCHAR(50) NOT NULL PRIMARY KEY,

    -- Weighted Moving Averages
    demand_3mo_weighted DECIMAL(10,2) DEFAULT 0 COMMENT '3-month weighted average demand (weights: 0.5, 0.3, 0.2)',
    demand_6mo_weighted DECIMAL(10,2) DEFAULT 0 COMMENT '6-month weighted average demand with exponential decay',
    demand_3mo_simple DECIMAL(10,2) DEFAULT 0 COMMENT '3-month simple moving average',
    demand_6mo_simple DECIMAL(10,2) DEFAULT 0 COMMENT '6-month simple moving average',

    -- Volatility Metrics
    demand_std_dev DECIMAL(10,2) DEFAULT 0 COMMENT 'Standard deviation of monthly demand',
    coefficient_variation DECIMAL(5,2) DEFAULT 0 COMMENT 'CV = std_dev / mean_demand',
    volatility_class ENUM('low', 'medium', 'high') DEFAULT 'medium' COMMENT 'Volatility classification based on CV',

    -- Data Quality Metrics
    sample_size_months INT DEFAULT 0 COMMENT 'Number of months used in calculations',
    data_quality_score DECIMAL(3,2) DEFAULT 0 COMMENT 'Quality score 0-1 based on data completeness',
    has_seasonal_pattern BOOLEAN DEFAULT FALSE COMMENT 'Whether seasonal pattern is detected',

    -- Calculation Metadata
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    calculation_method VARCHAR(50) DEFAULT 'weighted_average' COMMENT 'Method used for demand calculation',

    -- Foreign Key
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,

    -- Indexes for performance
    INDEX idx_volatility_class (volatility_class),
    INDEX idx_last_calculated (last_calculated),
    INDEX idx_data_quality (data_quality_score),
    INDEX idx_cv_score (coefficient_variation)
) COMMENT 'Store calculated demand statistics for enhanced transfer recommendations';

-- ===================================================================
-- Create Forecast Accuracy Tracking Table
-- ===================================================================

CREATE TABLE IF NOT EXISTS forecast_accuracy (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50) NOT NULL,

    -- Forecast Data
    forecast_date DATE NOT NULL COMMENT 'Date when forecast was made',
    forecast_period_start DATE NOT NULL COMMENT 'Start of forecasted period',
    forecast_period_end DATE NOT NULL COMMENT 'End of forecasted period',

    -- Predictions vs Actuals
    predicted_demand DECIMAL(10,2) NOT NULL COMMENT 'Predicted demand for the period',
    actual_demand DECIMAL(10,2) DEFAULT NULL COMMENT 'Actual demand observed (filled later)',

    -- Accuracy Metrics
    absolute_error DECIMAL(10,2) DEFAULT NULL COMMENT 'ABS(actual - predicted)',
    percentage_error DECIMAL(5,2) DEFAULT NULL COMMENT '(actual - predicted) / actual * 100',
    absolute_percentage_error DECIMAL(5,2) DEFAULT NULL COMMENT 'ABS(percentage_error)',

    -- Context Information
    forecast_method VARCHAR(50) NOT NULL COMMENT 'Method used: weighted_avg, seasonal_adj, etc.',
    abc_class CHAR(1) COMMENT 'ABC class at time of forecast',
    xyz_class CHAR(1) COMMENT 'XYZ class at time of forecast',
    seasonal_pattern VARCHAR(20) COMMENT 'Seasonal pattern at time of forecast',

    -- Status
    is_actual_recorded BOOLEAN DEFAULT FALSE COMMENT 'Whether actual demand has been recorded',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Key
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,

    -- Indexes
    INDEX idx_forecast_date (forecast_date),
    INDEX idx_sku_period (sku_id, forecast_period_start),
    INDEX idx_accuracy_metrics (is_actual_recorded, absolute_percentage_error),
    INDEX idx_abc_xyz_accuracy (abc_class, xyz_class, absolute_percentage_error),

    -- Unique constraint to prevent duplicate forecasts
    UNIQUE KEY unique_forecast (sku_id, forecast_date, forecast_period_start)
) COMMENT 'Track forecast accuracy over time for continuous improvement';

-- ===================================================================
-- Create Demand Calculation Configuration Table
-- ===================================================================

CREATE TABLE IF NOT EXISTS demand_calculation_config (
    config_key VARCHAR(50) PRIMARY KEY,
    config_value VARCHAR(200) NOT NULL,
    data_type ENUM('string', 'integer', 'decimal', 'boolean') NOT NULL,
    description TEXT NOT NULL,
    default_value VARCHAR(200) NOT NULL,
    min_value VARCHAR(50) DEFAULT NULL,
    max_value VARCHAR(50) DEFAULT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(50) DEFAULT 'system'
) COMMENT 'Configuration settings for demand calculation algorithms';

-- Insert default configuration values
INSERT INTO demand_calculation_config (config_key, config_value, data_type, description, default_value, min_value, max_value) VALUES
-- Weighted Average Settings
('weighted_3mo_weights', '0.5,0.3,0.2', 'string', 'Weights for 3-month weighted average (recent to oldest)', '0.5,0.3,0.2', NULL, NULL),
('weighted_6mo_enabled', 'true', 'boolean', 'Enable 6-month weighted averages for stable SKUs', 'true', NULL, NULL),
('min_months_for_weighted', '3', 'integer', 'Minimum months of data required for weighted average', '3', '2', '12'),

-- Volatility Classification Thresholds
('cv_low_threshold', '0.25', 'decimal', 'CV threshold for low volatility classification', '0.25', '0.1', '0.5'),
('cv_high_threshold', '0.75', 'decimal', 'CV threshold for high volatility classification', '0.75', '0.5', '2.0'),

-- Safety Stock Parameters
('service_level_a', '0.99', 'decimal', 'Service level for Class A items (99%)', '0.99', '0.90', '0.999'),
('service_level_b', '0.95', 'decimal', 'Service level for Class B items (95%)', '0.95', '0.85', '0.99'),
('service_level_c', '0.90', 'decimal', 'Service level for Class C items (90%)', '0.90', '0.80', '0.95'),
('default_lead_time_days', '120', 'integer', 'Default lead time in days when not specified', '120', '30', '365'),

-- Forecast Accuracy Settings
('mape_alert_threshold', '50.0', 'decimal', 'MAPE threshold for accuracy alerts (percentage)', '50.0', '20.0', '100.0'),
('accuracy_tracking_enabled', 'true', 'boolean', 'Enable forecast accuracy tracking', 'true', NULL, NULL),
('min_accuracy_samples', '6', 'integer', 'Minimum samples needed for accuracy calculation', '6', '3', '24'),

-- ABC-XYZ Specific Settings
('ax_use_6mo_average', 'true', 'boolean', 'Use 6-month average for AX classified SKUs', 'true', NULL, NULL),
('cz_use_single_month', 'false', 'boolean', 'Use single month for CZ classified SKUs', 'false', NULL, NULL),
('volatility_adjustment_factor', '1.2', 'decimal', 'Multiplier for high volatility SKU coverage', '1.2', '1.0', '2.0')

ON DUPLICATE KEY UPDATE
    description = VALUES(description),
    default_value = VALUES(default_value),
    min_value = VALUES(min_value),
    max_value = VALUES(max_value);

-- ===================================================================
-- Create Views for Common Queries
-- ===================================================================

-- View for SKUs with their demand statistics
CREATE OR REPLACE VIEW v_sku_demand_analysis AS
SELECT
    s.sku_id,
    s.description,
    s.category,
    s.abc_code,
    s.xyz_code,
    s.status,

    -- Current inventory
    ic.kentucky_qty,
    ic.burnaby_qty,

    -- Latest sales data
    ls.last_month_sales,
    ls.kentucky_stockout_days,
    ls.corrected_demand_kentucky,

    -- Calculated demand statistics
    sds.demand_3mo_weighted,
    sds.demand_6mo_weighted,
    sds.demand_std_dev,
    sds.coefficient_variation,
    sds.volatility_class,
    sds.sample_size_months,
    sds.data_quality_score,
    sds.last_calculated as stats_last_calculated,

    -- Calculated metrics
    CASE
        WHEN sds.demand_3mo_weighted > 0 AND ic.kentucky_qty > 0
        THEN ROUND(ic.kentucky_qty / sds.demand_3mo_weighted, 1)
        ELSE 0
    END as months_coverage_3mo_avg,

    CASE
        WHEN sds.coefficient_variation IS NOT NULL AND sds.coefficient_variation > 0.75 THEN 'High Risk'
        WHEN sds.coefficient_variation IS NOT NULL AND sds.coefficient_variation < 0.25 THEN 'Low Risk'
        ELSE 'Medium Risk'
    END as stockout_risk_level

FROM skus s
LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
LEFT JOIN (
    -- Get latest monthly sales data for each SKU
    SELECT
        ms1.sku_id,
        ms1.kentucky_sales as last_month_sales,
        ms1.kentucky_stockout_days,
        ms1.corrected_demand_kentucky
    FROM monthly_sales ms1
    WHERE ms1.`year_month` = (
        SELECT MAX(ms2.`year_month`)
        FROM monthly_sales ms2
        WHERE ms2.sku_id = ms1.sku_id
    )
) ls ON s.sku_id = ls.sku_id
LEFT JOIN sku_demand_stats sds ON s.sku_id = sds.sku_id
WHERE s.status = 'Active';

-- View for forecast accuracy summary by ABC class
CREATE OR REPLACE VIEW v_forecast_accuracy_summary AS
SELECT
    abc_class,
    COUNT(*) as total_forecasts,
    COUNT(CASE WHEN is_actual_recorded THEN 1 END) as completed_forecasts,
    AVG(CASE WHEN is_actual_recorded THEN absolute_percentage_error END) as avg_mape,
    STDDEV(CASE WHEN is_actual_recorded THEN absolute_percentage_error END) as mape_std_dev,

    -- Accuracy grades
    COUNT(CASE WHEN is_actual_recorded AND absolute_percentage_error <= 10 THEN 1 END) as excellent_forecasts,
    COUNT(CASE WHEN is_actual_recorded AND absolute_percentage_error <= 20 THEN 1 END) as good_forecasts,
    COUNT(CASE WHEN is_actual_recorded AND absolute_percentage_error > 50 THEN 1 END) as poor_forecasts,

    MAX(forecast_date) as latest_forecast_date,
    MIN(forecast_date) as earliest_forecast_date

FROM forecast_accuracy
GROUP BY abc_class;

-- ===================================================================
-- Performance Optimization Indexes
-- ===================================================================

-- Additional indexes for the monthly_sales table to support weighted averages
CREATE INDEX IF NOT EXISTS idx_monthly_sales_sku_yearmonth_desc ON monthly_sales(sku_id, `year_month` DESC);
CREATE INDEX IF NOT EXISTS idx_monthly_sales_corrected_demand ON monthly_sales(sku_id, corrected_demand_kentucky);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sku_demand_stats_composite ON sku_demand_stats(volatility_class, coefficient_variation, data_quality_score);

-- ===================================================================
-- Stored Procedures for Batch Operations
-- ===================================================================

DELIMITER //

-- Procedure to refresh demand statistics for a single SKU
CREATE OR REPLACE PROCEDURE RefreshSKUDemandStats(IN p_sku_id VARCHAR(50))
BEGIN
    DECLARE v_sample_size INT DEFAULT 0;
    DECLARE v_avg_3mo DECIMAL(10,2) DEFAULT 0;
    DECLARE v_avg_6mo DECIMAL(10,2) DEFAULT 0;
    DECLARE v_std_dev DECIMAL(10,2) DEFAULT 0;
    DECLARE v_cv DECIMAL(5,2) DEFAULT 0;
    DECLARE v_volatility_class VARCHAR(10) DEFAULT 'medium';
    DECLARE v_quality_score DECIMAL(3,2) DEFAULT 0;

    -- Get sample size (number of months with data)
    SELECT COUNT(*) INTO v_sample_size
    FROM monthly_sales
    WHERE sku_id = p_sku_id
        AND `year_month` >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 12 MONTH), '%Y-%m');

    -- Calculate 3-month weighted average
    SELECT
        COALESCE(
            (SELECT corrected_demand_kentucky FROM monthly_sales
             WHERE sku_id = p_sku_id ORDER BY `year_month` DESC LIMIT 1) * 0.5 +
            (SELECT corrected_demand_kentucky FROM monthly_sales
             WHERE sku_id = p_sku_id ORDER BY `year_month` DESC LIMIT 1 OFFSET 1) * 0.3 +
            (SELECT corrected_demand_kentucky FROM monthly_sales
             WHERE sku_id = p_sku_id ORDER BY `year_month` DESC LIMIT 1 OFFSET 2) * 0.2,
            0
        ) INTO v_avg_3mo;

    -- Calculate 6-month simple average (for now)
    SELECT COALESCE(AVG(corrected_demand_kentucky), 0) INTO v_avg_6mo
    FROM monthly_sales
    WHERE sku_id = p_sku_id
        AND `year_month` >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 6 MONTH), '%Y-%m');

    -- Calculate standard deviation
    SELECT COALESCE(STDDEV(corrected_demand_kentucky), 0) INTO v_std_dev
    FROM monthly_sales
    WHERE sku_id = p_sku_id
        AND `year_month` >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 12 MONTH), '%Y-%m');

    -- Calculate coefficient of variation
    IF v_avg_6mo > 0 THEN
        SET v_cv = v_std_dev / v_avg_6mo;
    END IF;

    -- Classify volatility
    IF v_cv < 0.25 THEN
        SET v_volatility_class = 'low';
    ELSEIF v_cv > 0.75 THEN
        SET v_volatility_class = 'high';
    ELSE
        SET v_volatility_class = 'medium';
    END IF;

    -- Calculate data quality score
    SET v_quality_score = LEAST(1.0, v_sample_size / 12.0);

    -- Insert or update the statistics
    INSERT INTO sku_demand_stats (
        sku_id, demand_3mo_weighted, demand_6mo_weighted, demand_std_dev,
        coefficient_variation, volatility_class, sample_size_months,
        data_quality_score, last_calculated
    ) VALUES (
        p_sku_id, v_avg_3mo, v_avg_6mo, v_std_dev, v_cv,
        v_volatility_class, v_sample_size, v_quality_score, NOW()
    )
    ON DUPLICATE KEY UPDATE
        demand_3mo_weighted = v_avg_3mo,
        demand_6mo_weighted = v_avg_6mo,
        demand_std_dev = v_std_dev,
        coefficient_variation = v_cv,
        volatility_class = v_volatility_class,
        sample_size_months = v_sample_size,
        data_quality_score = v_quality_score,
        last_calculated = NOW();

END //

DELIMITER ;

-- ===================================================================
-- Data Validation and Cleanup
-- ===================================================================

-- Verify new tables were created successfully
SELECT
    TABLE_NAME,
    TABLE_COMMENT,
    CREATE_TIME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'warehouse_transfer'
    AND TABLE_NAME IN ('sku_demand_stats', 'forecast_accuracy', 'demand_calculation_config')
ORDER BY TABLE_NAME;

-- Check configuration entries
SELECT config_key, config_value, description
FROM demand_calculation_config
ORDER BY config_key;

-- Show summary of enhancement
SELECT
    'Schema Enhancement Complete' as status,
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
     WHERE TABLE_SCHEMA = 'warehouse_transfer'
     AND TABLE_NAME IN ('sku_demand_stats', 'forecast_accuracy', 'demand_calculation_config')) as new_tables_created,
    (SELECT COUNT(*) FROM demand_calculation_config) as config_entries,
    NOW() as completed_at;