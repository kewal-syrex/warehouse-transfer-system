-- Warehouse Transfer Planning Tool - Database Schema
-- Version: 1.0
-- Date: September 2025

-- Create database
CREATE DATABASE IF NOT EXISTS warehouse_transfer;
USE warehouse_transfer;

-- Drop tables if they exist (for clean reinstall)
DROP TABLE IF EXISTS transfer_history;
DROP TABLE IF EXISTS pending_inventory;
DROP TABLE IF EXISTS stockout_dates;
DROP TABLE IF EXISTS monthly_sales;
DROP TABLE IF EXISTS inventory_current;
DROP TABLE IF EXISTS skus;

-- ===================================================================
-- SKU Master Data Table
-- ===================================================================
CREATE TABLE skus (
    sku_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    supplier VARCHAR(100),
    status ENUM('Active', 'Death Row', 'Discontinued') DEFAULT 'Active',
    cost_per_unit DECIMAL(10,2),
    transfer_multiple INT DEFAULT 50,
    abc_code CHAR(1) DEFAULT 'C',
    xyz_code CHAR(1) DEFAULT 'Z',
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_abc_xyz (abc_code, xyz_code),
    INDEX idx_supplier (supplier)
);

-- ===================================================================
-- Current Inventory Levels Table
-- ===================================================================
CREATE TABLE inventory_current (
    sku_id VARCHAR(50) PRIMARY KEY,
    burnaby_qty INT DEFAULT 0,
    kentucky_qty INT DEFAULT 0,
    burnaby_value DECIMAL(12,2) GENERATED ALWAYS AS (burnaby_qty * (SELECT cost_per_unit FROM skus WHERE skus.sku_id = inventory_current.sku_id)) STORED,
    kentucky_value DECIMAL(12,2) GENERATED ALWAYS AS (kentucky_qty * (SELECT cost_per_unit FROM skus WHERE skus.sku_id = inventory_current.sku_id)) STORED,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_burnaby_qty (burnaby_qty),
    INDEX idx_kentucky_qty (kentucky_qty),
    INDEX idx_last_updated (last_updated)
);

-- ===================================================================
-- Monthly Sales History with Stockout Tracking
-- ===================================================================
CREATE TABLE monthly_sales (
    year_month VARCHAR(7) NOT NULL, -- Format: '2024-01'
    sku_id VARCHAR(50) NOT NULL,
    burnaby_sales INT DEFAULT 0,
    kentucky_sales INT DEFAULT 0,
    burnaby_stockout_days INT DEFAULT 0,
    kentucky_stockout_days INT DEFAULT 0,
    total_sales INT GENERATED ALWAYS AS (burnaby_sales + kentucky_sales) STORED,
    corrected_demand_burnaby DECIMAL(10,2) DEFAULT 0,
    corrected_demand_kentucky DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (year_month, sku_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_year_month (year_month),
    INDEX idx_total_sales (total_sales),
    INDEX idx_stockout_days (burnaby_stockout_days, kentucky_stockout_days)
);

-- ===================================================================
-- Individual Stockout Dates (Optional detailed tracking)
-- ===================================================================
CREATE TABLE stockout_dates (
    sku_id VARCHAR(50) NOT NULL,
    warehouse ENUM('burnaby', 'kentucky') NOT NULL,
    stockout_date DATE NOT NULL,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sku_id, warehouse, stockout_date),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_warehouse (warehouse),
    INDEX idx_stockout_date (stockout_date),
    INDEX idx_unresolved (is_resolved, stockout_date)
);

-- ===================================================================
-- Pending Inventory (In-transit and on-order)
-- ===================================================================
CREATE TABLE pending_inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    destination ENUM('burnaby', 'kentucky') NOT NULL,
    order_date DATE NOT NULL,
    expected_arrival DATE NOT NULL,
    actual_arrival DATE NULL,
    order_type ENUM('supplier', 'transfer') DEFAULT 'supplier',
    status ENUM('ordered', 'shipped', 'received', 'cancelled') DEFAULT 'ordered',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_destination (destination),
    INDEX idx_expected_arrival (expected_arrival),
    INDEX idx_status (status),
    INDEX idx_order_type (order_type)
);

-- ===================================================================
-- Transfer History (Track transfer recommendations and actuals)
-- ===================================================================
CREATE TABLE transfer_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50) NOT NULL,
    recommended_qty INT NOT NULL,
    actual_qty INT DEFAULT 0,
    recommendation_date DATE NOT NULL,
    transfer_date DATE NULL,
    burnaby_qty_before INT,
    kentucky_qty_before INT,
    reason VARCHAR(255),
    corrected_demand DECIMAL(10,2),
    coverage_days INT,
    abc_class CHAR(1),
    xyz_class CHAR(1),
    created_by VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE,
    INDEX idx_recommendation_date (recommendation_date),
    INDEX idx_transfer_date (transfer_date),
    INDEX idx_abc_xyz (abc_class, xyz_class)
);

-- ===================================================================
-- Views for Common Queries
-- ===================================================================

-- Current stock status with SKU details
CREATE VIEW v_current_stock_status AS
SELECT 
    s.sku_id,
    s.description,
    s.supplier,
    s.status,
    s.abc_code,
    s.xyz_code,
    s.transfer_multiple,
    ic.burnaby_qty,
    ic.kentucky_qty,
    ic.burnaby_qty + ic.kentucky_qty as total_qty,
    ic.last_updated,
    CASE 
        WHEN ic.kentucky_qty = 0 THEN 'OUT_OF_STOCK'
        WHEN ic.kentucky_qty < 50 THEN 'LOW_STOCK'
        ELSE 'IN_STOCK'
    END as stock_status
FROM skus s
LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
WHERE s.status = 'Active';

-- Latest monthly sales with corrections
CREATE VIEW v_latest_sales AS
SELECT 
    ms.*,
    s.description,
    s.abc_code,
    s.xyz_code,
    CASE 
        WHEN ms.kentucky_stockout_days > 0 THEN 'STOCKOUT_AFFECTED'
        ELSE 'NORMAL'
    END as sales_status
FROM monthly_sales ms
INNER JOIN skus s ON ms.sku_id = s.sku_id
WHERE ms.year_month = (
    SELECT MAX(year_month) 
    FROM monthly_sales ms2 
    WHERE ms2.sku_id = ms.sku_id
);

-- Current stockouts
CREATE VIEW v_current_stockouts AS
SELECT 
    sd.sku_id,
    s.description,
    sd.warehouse,
    sd.stockout_date,
    DATEDIFF(CURDATE(), sd.stockout_date) as days_out,
    ic.burnaby_qty,
    ic.kentucky_qty
FROM stockout_dates sd
INNER JOIN skus s ON sd.sku_id = s.sku_id
LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
WHERE sd.is_resolved = FALSE
ORDER BY sd.stockout_date ASC;

-- ===================================================================
-- Sample Data for Testing
-- ===================================================================

-- Insert sample SKUs
INSERT INTO skus (sku_id, description, supplier, status, cost_per_unit, transfer_multiple, abc_code, xyz_code, category) VALUES
('CHG-001', 'USB-C Fast Charger 65W', 'Supplier A', 'Active', 25.50, 25, 'A', 'X', 'Chargers'),
('CBL-002', 'Lightning Cable 6ft', 'Supplier B', 'Active', 8.75, 25, 'B', 'X', 'Cables'),
('WDG-003', 'Bluetooth Widget Pro', 'Supplier C', 'Active', 45.00, 50, 'A', 'Y', 'Electronics'),
('GAD-004', 'Smart Gadget Mini', 'Supplier A', 'Active', 15.25, 100, 'C', 'Z', 'Electronics'),
('ACC-005', 'Phone Stand Deluxe', 'Supplier D', 'Death Row', 12.00, 50, 'C', 'Y', 'Accessories');

-- Insert current inventory
INSERT INTO inventory_current (sku_id, burnaby_qty, kentucky_qty) VALUES
('CHG-001', 500, 0),     -- Out of stock in Kentucky
('CBL-002', 1200, 150),  -- Low stock in Kentucky
('WDG-003', 800, 300),   -- Good stock both
('GAD-004', 2000, 750),  -- High stock both
('ACC-005', 100, 25);    -- Death row item

-- Insert sample monthly sales data
INSERT INTO monthly_sales (year_month, sku_id, burnaby_sales, kentucky_sales, burnaby_stockout_days, kentucky_stockout_days) VALUES
-- January 2024
('2024-01', 'CHG-001', 50, 120, 0, 0),
('2024-01', 'CBL-002', 80, 200, 0, 0),
('2024-01', 'WDG-003', 30, 75, 0, 0),
('2024-01', 'GAD-004', 100, 250, 0, 0),
('2024-01', 'ACC-005', 15, 35, 0, 0),
-- February 2024 (with some stockouts)
('2024-02', 'CHG-001', 45, 80, 0, 10),  -- Kentucky had 10 days stockout
('2024-02', 'CBL-002', 75, 180, 0, 0),
('2024-02', 'WDG-003', 25, 60, 0, 0),
('2024-02', 'GAD-004', 90, 220, 0, 0),
('2024-02', 'ACC-005', 10, 20, 0, 5),   -- Kentucky had 5 days stockout
-- March 2024 (current month with ongoing stockout)
('2024-03', 'CHG-001', 40, 0, 0, 25),   -- Kentucky out for 25 days
('2024-03', 'CBL-002', 70, 160, 0, 0),
('2024-03', 'WDG-003', 35, 85, 0, 0),
('2024-03', 'GAD-004', 110, 280, 0, 0),
('2024-03', 'ACC-005', 5, 15, 0, 0);

-- Insert some stockout dates
INSERT INTO stockout_dates (sku_id, warehouse, stockout_date, is_resolved) VALUES
('CHG-001', 'kentucky', '2024-03-05', FALSE),  -- Ongoing stockout
('ACC-005', 'kentucky', '2024-02-10', TRUE);   -- Resolved stockout

-- Insert pending inventory
INSERT INTO pending_inventory (sku_id, quantity, destination, order_date, expected_arrival, order_type, status) VALUES
('CHG-001', 300, 'burnaby', '2024-03-01', '2024-03-15', 'supplier', 'ordered'),
('CBL-002', 500, 'burnaby', '2024-02-28', '2024-03-10', 'supplier', 'shipped'),
('WDG-003', 200, 'kentucky', '2024-03-05', '2024-03-12', 'transfer', 'shipped');

-- ===================================================================
-- Stored Procedures for Common Operations
-- ===================================================================

DELIMITER //

-- Calculate corrected demand for a SKU
CREATE PROCEDURE CalculateCorrectedDemand(IN p_sku_id VARCHAR(50), IN p_warehouse VARCHAR(10))
BEGIN
    DECLARE v_monthly_sales INT DEFAULT 0;
    DECLARE v_stockout_days INT DEFAULT 0;
    DECLARE v_days_in_month INT DEFAULT 30;
    DECLARE v_availability_rate DECIMAL(5,2);
    DECLARE v_correction_factor DECIMAL(5,2);
    DECLARE v_corrected_demand DECIMAL(10,2);
    DECLARE v_year_month VARCHAR(7);
    
    -- Get latest month
    SELECT MAX(year_month) INTO v_year_month FROM monthly_sales WHERE sku_id = p_sku_id;
    
    -- Get sales and stockout data
    IF p_warehouse = 'kentucky' THEN
        SELECT kentucky_sales, kentucky_stockout_days 
        INTO v_monthly_sales, v_stockout_days
        FROM monthly_sales 
        WHERE sku_id = p_sku_id AND year_month = v_year_month;
    ELSE
        SELECT burnaby_sales, burnaby_stockout_days 
        INTO v_monthly_sales, v_stockout_days
        FROM monthly_sales 
        WHERE sku_id = p_sku_id AND year_month = v_year_month;
    END IF;
    
    -- Calculate availability rate
    SET v_availability_rate = (v_days_in_month - v_stockout_days) / v_days_in_month;
    
    -- Apply correction logic
    IF v_availability_rate < 1.0 AND v_monthly_sales > 0 THEN
        SET v_correction_factor = GREATEST(v_availability_rate, 0.3); -- 30% floor
        SET v_corrected_demand = v_monthly_sales / v_correction_factor;
        
        -- Cap at 50% increase for very low availability
        IF v_availability_rate < 0.3 THEN
            SET v_corrected_demand = LEAST(v_corrected_demand, v_monthly_sales * 1.5);
        END IF;
    ELSE
        SET v_corrected_demand = v_monthly_sales;
    END IF;
    
    -- Update the monthly_sales table with corrected demand
    IF p_warehouse = 'kentucky' THEN
        UPDATE monthly_sales 
        SET corrected_demand_kentucky = v_corrected_demand
        WHERE sku_id = p_sku_id AND year_month = v_year_month;
    ELSE
        UPDATE monthly_sales 
        SET corrected_demand_burnaby = v_corrected_demand
        WHERE sku_id = p_sku_id AND year_month = v_year_month;
    END IF;
    
    SELECT v_corrected_demand as corrected_demand;
END //

DELIMITER ;

-- ===================================================================
-- Indexes for Performance
-- ===================================================================

-- Additional performance indexes
CREATE INDEX idx_monthly_sales_composite ON monthly_sales(sku_id, year_month DESC);
CREATE INDEX idx_inventory_zero_stock ON inventory_current(kentucky_qty) WHERE kentucky_qty = 0;
CREATE INDEX idx_skus_active ON skus(status) WHERE status = 'Active';

-- ===================================================================
-- Database User and Permissions (Optional)
-- ===================================================================

-- Create application user (uncomment if needed)
-- CREATE USER 'warehouse_app'@'localhost' IDENTIFIED BY 'secure_password_here';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON warehouse_transfer.* TO 'warehouse_app'@'localhost';
-- FLUSH PRIVILEGES;

COMMIT;