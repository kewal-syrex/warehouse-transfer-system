-- Configuration Management Tables
-- Version: 1.0
-- Date: September 2025
-- Purpose: System configuration and supplier-specific overrides

USE warehouse_transfer;

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

-- Insert default configuration values
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

-- Insert some example supplier lead time overrides
INSERT INTO supplier_lead_times (supplier, lead_time_days, destination, notes) VALUES
('Acme Corp', 90, NULL, 'Standard supplier with 3-month lead time'),
('FastShip LLC', 30, 'burnaby', 'Express shipping to Burnaby only'),
('Global Widgets', 150, NULL, 'International supplier with longer lead times'),
('Local Supply Co', 14, 'kentucky', 'Local supplier for Kentucky warehouse')

ON DUPLICATE KEY UPDATE
    lead_time_days = VALUES(lead_time_days),
    notes = VALUES(notes),
    updated_at = CURRENT_TIMESTAMP;

-- Create view for configuration management
CREATE OR REPLACE VIEW v_configuration_summary AS
SELECT
    category,
    COUNT(*) as setting_count,
    MAX(updated_at) as last_updated
FROM system_config
GROUP BY category
ORDER BY category;

-- Create view for supplier lead time summary
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

COMMIT;