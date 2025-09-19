-- Create seasonal_factors table for storing data-driven seasonal factors
-- This replaces hard-coded multipliers with historical sales analysis

CREATE TABLE IF NOT EXISTS seasonal_factors (
    sku_id VARCHAR(50) NOT NULL,
    warehouse ENUM('kentucky', 'burnaby') NOT NULL DEFAULT 'kentucky',
    month_number TINYINT NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    seasonal_factor DECIMAL(6,4) NOT NULL DEFAULT 1.0000,
    confidence_level DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    data_points_used INT NOT NULL DEFAULT 0,
    pattern_type VARCHAR(20) DEFAULT 'unknown',
    pattern_strength DECIMAL(5,4) DEFAULT 0.0000,
    last_calculated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (sku_id, warehouse, month_number),
    INDEX idx_sku_warehouse (sku_id, warehouse),
    INDEX idx_pattern_type (pattern_type),
    INDEX idx_confidence (confidence_level),
    INDEX idx_last_calculated (last_calculated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Data-driven seasonal factors calculated from historical sales patterns';

-- Create seasonal_patterns_summary table for SKU-level pattern metadata
CREATE TABLE IF NOT EXISTS seasonal_patterns_summary (
    sku_id VARCHAR(50) NOT NULL,
    warehouse ENUM('kentucky', 'burnaby') NOT NULL DEFAULT 'kentucky',
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'unknown',
    pattern_strength DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    overall_confidence DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    statistical_significance BOOLEAN NOT NULL DEFAULT FALSE,
    f_statistic DECIMAL(10,4) DEFAULT NULL,
    p_value DECIMAL(10,8) DEFAULT NULL,
    years_analyzed TINYINT NOT NULL DEFAULT 0,
    months_of_data INT NOT NULL DEFAULT 0,
    date_range_start VARCHAR(7) DEFAULT NULL,
    date_range_end VARCHAR(7) DEFAULT NULL,
    yearly_average DECIMAL(10,2) DEFAULT 0.00,
    peak_months VARCHAR(50) DEFAULT NULL,
    low_months VARCHAR(50) DEFAULT NULL,
    last_analyzed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (sku_id, warehouse),
    INDEX idx_pattern_type (pattern_type),
    INDEX idx_pattern_strength (pattern_strength),
    INDEX idx_confidence (overall_confidence),
    INDEX idx_significance (statistical_significance),
    INDEX idx_last_analyzed (last_analyzed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Summary of seasonal pattern analysis for each SKU and warehouse';

-- Add seasonal configuration to demand_calculation_config if not exists
INSERT IGNORE INTO demand_calculation_config
    (config_key, config_value, data_type, description, default_value, min_value, max_value, updated_by)
VALUES
    ('seasonal_adjustment_enabled', 'true', 'boolean',
     'Enable data-driven seasonal adjustments based on historical patterns',
     'true', NULL, NULL, 'system'),

    ('seasonal_min_confidence', '0.6', 'decimal',
     'Minimum confidence level required to apply seasonal adjustments',
     '0.6', '0.0', '1.0', 'system'),

    ('seasonal_pattern_strength_threshold', '0.3', 'decimal',
     'Minimum pattern strength required for seasonal adjustment',
     '0.3', '0.0', '1.0', 'system'),

    ('seasonal_fallback_to_category', 'true', 'boolean',
     'Use category-level seasonal patterns when SKU-specific patterns are unreliable',
     'true', NULL, NULL, 'system'),

    ('seasonal_analysis_years', '3', 'integer',
     'Number of years of historical data to use for seasonal analysis',
     '3', '1', '5', 'system');

-- Create view for easy access to current month seasonal factors
CREATE OR REPLACE VIEW v_current_seasonal_factors AS
SELECT
    sf.sku_id,
    sf.warehouse,
    sf.seasonal_factor as current_month_factor,
    sf.confidence_level as current_month_confidence,
    sps.pattern_type,
    sps.pattern_strength,
    sps.overall_confidence,
    sps.statistical_significance,
    MONTH(NOW()) as current_month,
    MONTHNAME(NOW()) as current_month_name,
    sf.last_calculated,
    CASE
        WHEN sf.confidence_level >= 0.7 AND sps.pattern_strength >= 0.3 THEN 'reliable'
        WHEN sf.confidence_level >= 0.5 AND sps.pattern_strength >= 0.2 THEN 'moderate'
        ELSE 'unreliable'
    END as reliability_rating
FROM seasonal_factors sf
JOIN seasonal_patterns_summary sps ON sf.sku_id = sps.sku_id AND sf.warehouse = sps.warehouse
WHERE sf.month_number = MONTH(NOW())
ORDER BY sf.sku_id, sf.warehouse;

-- Create index on monthly_sales for seasonal analysis performance (if not exists)
-- ALTER TABLE monthly_sales ADD INDEX idx_monthly_sales_seasonal (sku_id, `year_month`);

-- Update skus table seasonal_pattern to reflect data-driven patterns
-- This will be updated by the seasonal analysis script

COMMIT;