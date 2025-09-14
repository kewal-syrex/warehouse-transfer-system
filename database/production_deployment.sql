-- Production Deployment Script for Pending Orders & Configuration System
-- Version: 2.0
-- Date: September 2025
-- Purpose: Complete database setup for production deployment

USE warehouse_transfer;

-- ===================================================================
-- STEP 1: BACKUP EXISTING DATA (MANUAL STEP)
-- ===================================================================
-- IMPORTANT: Before running this script, backup your database:
-- mysqldump -u [username] -p warehouse_transfer > warehouse_transfer_backup_$(date +%Y%m%d).sql

-- ===================================================================
-- STEP 2: ADD NEW COLUMNS TO EXISTING TABLES
-- ===================================================================

-- Add enhanced fields to pending_inventory table (if not already present)
ALTER TABLE pending_inventory
ADD COLUMN IF NOT EXISTS lead_time_days INT DEFAULT 120 COMMENT 'Lead time in days (default 4 months)',
ADD COLUMN IF NOT EXISTS is_estimated BOOLEAN DEFAULT TRUE COMMENT 'Whether the arrival date is estimated',
ADD COLUMN IF NOT EXISTS notes TEXT COMMENT 'Additional notes for tracking shipment details';

-- Add enhanced fields to skus table (if not already present)
ALTER TABLE skus
ADD COLUMN IF NOT EXISTS seasonal_pattern VARCHAR(20) COMMENT 'Auto-detected seasonal pattern',
ADD COLUMN IF NOT EXISTS growth_status ENUM('normal', 'viral', 'declining') DEFAULT 'normal' COMMENT 'Growth classification',
ADD COLUMN IF NOT EXISTS last_stockout_date DATE COMMENT 'Most recent stockout tracking',
ADD COLUMN IF NOT EXISTS category VARCHAR(50) COMMENT 'SKU category for enhanced reporting';

-- ===================================================================
-- STEP 3: CREATE NEW CONFIGURATION TABLES
-- ===================================================================

-- System configuration table
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    data_type ENUM('string', 'int', 'float', 'bool', 'json') DEFAULT 'string',
    category VARCHAR(50) DEFAULT 'general',
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_config_category (category),
    INDEX idx_config_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Supplier-specific lead time overrides
CREATE TABLE IF NOT EXISTS supplier_lead_times (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier VARCHAR(100) NOT NULL,
    lead_time_days INT NOT NULL,
    destination ENUM('burnaby', 'kentucky') NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY unique_supplier_destination (supplier, destination),
    INDEX idx_supplier (supplier),
    INDEX idx_destination (destination),

    CONSTRAINT chk_lead_time_positive CHECK (lead_time_days > 0 AND lead_time_days <= 365)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================================================================
-- STEP 4: CREATE PERFORMANCE INDEXES
-- ===================================================================

-- Pending inventory indexes
CREATE INDEX IF NOT EXISTS idx_pending_lead_time ON pending_inventory(lead_time_days);
CREATE INDEX IF NOT EXISTS idx_pending_estimated ON pending_inventory(is_estimated);
CREATE INDEX IF NOT EXISTS idx_pending_expected_arrival ON pending_inventory(expected_arrival);
CREATE INDEX IF NOT EXISTS idx_pending_status_destination ON pending_inventory(status, destination);

-- SKU table indexes for enhanced calculations
CREATE INDEX IF NOT EXISTS idx_skus_seasonal_pattern ON skus(seasonal_pattern);
CREATE INDEX IF NOT EXISTS idx_skus_growth_status ON skus(growth_status);
CREATE INDEX IF NOT EXISTS idx_skus_last_stockout ON skus(last_stockout_date);
CREATE INDEX IF NOT EXISTS idx_skus_category ON skus(category);

-- ===================================================================
-- STEP 5: CREATE DATABASE VIEWS
-- ===================================================================

-- Enhanced pending orders analysis view
CREATE OR REPLACE VIEW v_pending_orders_analysis AS
SELECT
    pi.id,
    pi.sku_id,
    s.description,
    s.supplier,
    pi.quantity,
    pi.destination,
    pi.order_date,
    pi.expected_arrival,
    pi.lead_time_days,
    pi.is_estimated,
    pi.order_type,
    pi.status,
    pi.notes,
    -- Calculate days until arrival
    CASE
        WHEN pi.expected_arrival IS NOT NULL THEN
            DATEDIFF(pi.expected_arrival, CURDATE())
        ELSE
            DATEDIFF(DATE_ADD(pi.order_date, INTERVAL pi.lead_time_days DAY), CURDATE())
    END as days_until_arrival,
    -- Determine if order is overdue
    CASE
        WHEN pi.expected_arrival IS NOT NULL AND pi.expected_arrival < CURDATE()
             AND pi.status NOT IN ('received', 'cancelled') THEN TRUE
        ELSE FALSE
    END as is_overdue,
    -- Calculate urgency level
    CASE
        WHEN DATEDIFF(pi.expected_arrival, CURDATE()) <= 7 THEN 'URGENT'
        WHEN DATEDIFF(pi.expected_arrival, CURDATE()) <= 30 THEN 'SOON'
        WHEN DATEDIFF(pi.expected_arrival, CURDATE()) <= 90 THEN 'NORMAL'
        ELSE 'DISTANT'
    END as urgency_level
FROM pending_inventory pi
LEFT JOIN skus s ON pi.sku_id = s.sku_id
WHERE pi.status IN ('ordered', 'shipped', 'pending');

-- Pending quantities summary by SKU and destination
CREATE OR REPLACE VIEW v_pending_quantities AS
SELECT
    sku_id,
    destination,
    SUM(quantity) as total_pending_quantity,
    COUNT(*) as order_count,
    MIN(expected_arrival) as earliest_arrival,
    MAX(expected_arrival) as latest_arrival,
    AVG(DATEDIFF(expected_arrival, CURDATE())) as avg_days_until_arrival,
    SUM(CASE WHEN is_estimated = TRUE THEN quantity ELSE 0 END) as estimated_quantity,
    SUM(CASE WHEN is_estimated = FALSE THEN quantity ELSE 0 END) as confirmed_quantity
FROM pending_inventory
WHERE status IN ('ordered', 'shipped', 'pending')
GROUP BY sku_id, destination;

-- Configuration summary view
CREATE OR REPLACE VIEW v_configuration_summary AS
SELECT
    category,
    COUNT(*) as setting_count,
    MAX(updated_at) as last_updated
FROM system_config
GROUP BY category
ORDER BY category;

-- Supplier lead time summary view
CREATE OR REPLACE VIEW v_supplier_lead_time_summary AS
SELECT
    supplier,
    COUNT(*) as override_count,
    AVG(lead_time_days) as avg_lead_time,
    MIN(lead_time_days) as min_lead_time,
    MAX(lead_time_days) as max_lead_time,
    GROUP_CONCAT(
        CASE
            WHEN destination IS NULL THEN 'All Warehouses'
            ELSE UPPER(destination)
        END
        ORDER BY destination
        SEPARATOR ', '
    ) as destinations
FROM supplier_lead_times
GROUP BY supplier
ORDER BY supplier;

-- ===================================================================
-- STEP 6: INSERT DEFAULT CONFIGURATION
-- ===================================================================

INSERT INTO system_config (config_key, config_value, data_type, category, description) VALUES
-- Lead time settings
('default_lead_time_days', '120', 'int', 'lead_times', 'Default lead time in days for pending orders'),
('min_lead_time_days', '1', 'int', 'lead_times', 'Minimum allowed lead time'),
('max_lead_time_days', '365', 'int', 'lead_times', 'Maximum allowed lead time'),

-- Burnaby retention settings
('burnaby_min_coverage_months', '2.0', 'float', 'coverage', 'Never transfer below this coverage threshold'),
('burnaby_target_coverage_months', '6.0', 'float', 'coverage', 'Target coverage retention for Burnaby'),
('burnaby_coverage_with_pending', '1.5', 'float', 'coverage', 'Coverage with imminent pending orders'),

-- Import/Export settings
('auto_create_estimated_dates', 'true', 'bool', 'import_export', 'Automatically create estimated dates for missing values'),
('require_sku_validation', 'true', 'bool', 'import_export', 'Validate SKUs exist before import'),

-- Business rules
('min_transfer_quantity', '1', 'int', 'business_rules', 'Minimum transfer quantity'),
('enable_stockout_override', 'true', 'bool', 'business_rules', 'Enable stockout quantity overrides')

ON DUPLICATE KEY UPDATE
    config_value = VALUES(config_value),
    data_type = VALUES(data_type),
    category = VALUES(category),
    description = VALUES(description),
    updated_at = CURRENT_TIMESTAMP;

-- ===================================================================
-- STEP 7: INSERT EXAMPLE SUPPLIER LEAD TIME OVERRIDES
-- ===================================================================

INSERT INTO supplier_lead_times (supplier, lead_time_days, destination, notes) VALUES
('Acme Corp', 90, NULL, 'Standard supplier with 3-month lead time'),
('FastShip LLC', 30, 'burnaby', 'Express shipping to Burnaby only'),
('Global Widgets', 150, NULL, 'International supplier with longer lead times'),
('Local Supply Co', 14, 'kentucky', 'Local supplier for Kentucky warehouse')

ON DUPLICATE KEY UPDATE
    lead_time_days = VALUES(lead_time_days),
    notes = VALUES(notes),
    updated_at = CURRENT_TIMESTAMP;

-- ===================================================================
-- STEP 8: UPDATE EXISTING DATA
-- ===================================================================

-- Update existing pending_inventory records with proper lead time values
UPDATE pending_inventory
SET
    lead_time_days = GREATEST(DATEDIFF(expected_arrival, order_date), 1),
    is_estimated = FALSE
WHERE expected_arrival IS NOT NULL
  AND order_date IS NOT NULL
  AND lead_time_days IS NULL;

-- Set default lead time for records without dates
UPDATE pending_inventory
SET lead_time_days = 120
WHERE lead_time_days IS NULL;

-- Mark records without expected_arrival as estimated
UPDATE pending_inventory
SET is_estimated = TRUE
WHERE expected_arrival IS NULL;

-- ===================================================================
-- STEP 9: CREATE DATABASE TRIGGERS (OPTIONAL)
-- ===================================================================

-- Trigger to automatically update last_stockout_date when stockout_dates is updated
DELIMITER //

CREATE TRIGGER IF NOT EXISTS update_last_stockout_date
AFTER INSERT ON stockout_dates
FOR EACH ROW
BEGIN
    UPDATE skus
    SET last_stockout_date = NEW.stockout_date
    WHERE sku_id = NEW.sku_id
      AND (last_stockout_date IS NULL OR NEW.stockout_date > last_stockout_date);
END//

DELIMITER ;

-- ===================================================================
-- STEP 10: VERIFY DEPLOYMENT
-- ===================================================================

-- Check table structures
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'warehouse_transfer'
  AND TABLE_NAME IN ('pending_inventory', 'system_config', 'supplier_lead_times', 'skus')
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- Check indexes
SELECT
    TABLE_NAME,
    INDEX_NAME,
    COLUMN_NAME,
    NON_UNIQUE
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = 'warehouse_transfer'
  AND TABLE_NAME IN ('pending_inventory', 'system_config', 'supplier_lead_times', 'skus')
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- Check views
SELECT TABLE_NAME as VIEW_NAME
FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = 'warehouse_transfer'
  AND TABLE_NAME LIKE 'v_%';

-- Sample data verification
SELECT 'Configuration Settings' as CHECK_TYPE, COUNT(*) as COUNT FROM system_config
UNION ALL
SELECT 'Supplier Lead Times' as CHECK_TYPE, COUNT(*) as COUNT FROM supplier_lead_times
UNION ALL
SELECT 'Pending Orders' as CHECK_TYPE, COUNT(*) as COUNT FROM pending_inventory
UNION ALL
SELECT 'Enhanced SKUs' as CHECK_TYPE, COUNT(*) as COUNT FROM skus WHERE seasonal_pattern IS NOT NULL OR category IS NOT NULL;

-- Performance check - verify indexes are being used
EXPLAIN SELECT * FROM v_pending_orders_analysis WHERE sku_id = 'CHG-001';
EXPLAIN SELECT * FROM v_pending_quantities WHERE destination = 'kentucky';

-- ===================================================================
-- DEPLOYMENT COMPLETED
-- ===================================================================

SELECT 'DEPLOYMENT COMPLETED SUCCESSFULLY' as STATUS,
       NOW() as COMPLETION_TIME,
       'Pending Orders & Configuration System v2.0' as VERSION;

COMMIT;