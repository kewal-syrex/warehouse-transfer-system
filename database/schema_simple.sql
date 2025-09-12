-- Warehouse Transfer Planning Tool - Simplified Database Schema
-- Version: 1.0 (Simplified for MySQL/MariaDB compatibility)

-- Create database
CREATE DATABASE IF NOT EXISTS warehouse_transfer;
USE warehouse_transfer;

-- Drop tables if they exist
DROP TABLE IF EXISTS transfer_history;
DROP TABLE IF EXISTS pending_inventory;
DROP TABLE IF EXISTS stockout_dates;
DROP TABLE IF EXISTS monthly_sales;
DROP TABLE IF EXISTS inventory_current;
DROP TABLE IF EXISTS skus;

-- SKU Master Data Table
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Current Inventory Levels Table
CREATE TABLE inventory_current (
    sku_id VARCHAR(50) PRIMARY KEY,
    burnaby_qty INT DEFAULT 0,
    kentucky_qty INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE
);

-- Monthly Sales History with Stockout Tracking
CREATE TABLE monthly_sales (
    year_month VARCHAR(7) NOT NULL,
    sku_id VARCHAR(50) NOT NULL,
    burnaby_sales INT DEFAULT 0,
    kentucky_sales INT DEFAULT 0,
    burnaby_stockout_days INT DEFAULT 0,
    kentucky_stockout_days INT DEFAULT 0,
    corrected_demand_burnaby DECIMAL(10,2) DEFAULT 0,
    corrected_demand_kentucky DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (year_month, sku_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE
);

-- Individual Stockout Dates
CREATE TABLE stockout_dates (
    sku_id VARCHAR(50) NOT NULL,
    warehouse ENUM('burnaby', 'kentucky') NOT NULL,
    stockout_date DATE NOT NULL,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sku_id, warehouse, stockout_date),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE
);

-- Pending Inventory
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
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE
);

-- Transfer History
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
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id) ON DELETE CASCADE
);

-- Insert sample SKUs
INSERT INTO skus (sku_id, description, supplier, status, cost_per_unit, transfer_multiple, abc_code, xyz_code, category) VALUES
('CHG-001', 'USB-C Fast Charger 65W', 'Supplier A', 'Active', 25.50, 25, 'A', 'X', 'Chargers'),
('CBL-002', 'Lightning Cable 6ft', 'Supplier B', 'Active', 8.75, 25, 'B', 'X', 'Cables'),
('WDG-003', 'Bluetooth Widget Pro', 'Supplier C', 'Active', 45.00, 50, 'A', 'Y', 'Electronics'),
('GAD-004', 'Smart Gadget Mini', 'Supplier A', 'Active', 15.25, 100, 'C', 'Z', 'Electronics'),
('ACC-005', 'Phone Stand Deluxe', 'Supplier D', 'Death Row', 12.00, 50, 'C', 'Y', 'Accessories');

-- Insert current inventory
INSERT INTO inventory_current (sku_id, burnaby_qty, kentucky_qty) VALUES
('CHG-001', 500, 0),
('CBL-002', 1200, 150),
('WDG-003', 800, 300),
('GAD-004', 2000, 750),
('ACC-005', 100, 25);

-- Insert sample monthly sales data
INSERT INTO monthly_sales (year_month, sku_id, burnaby_sales, kentucky_sales, burnaby_stockout_days, kentucky_stockout_days) VALUES
('2024-01', 'CHG-001', 50, 120, 0, 0),
('2024-01', 'CBL-002', 80, 200, 0, 0),
('2024-01', 'WDG-003', 30, 75, 0, 0),
('2024-01', 'GAD-004', 100, 250, 0, 0),
('2024-01', 'ACC-005', 15, 35, 0, 0),
('2024-02', 'CHG-001', 45, 80, 0, 10),
('2024-02', 'CBL-002', 75, 180, 0, 0),
('2024-02', 'WDG-003', 25, 60, 0, 0),
('2024-02', 'GAD-004', 90, 220, 0, 0),
('2024-02', 'ACC-005', 10, 20, 0, 5),
('2024-03', 'CHG-001', 40, 0, 0, 25),
('2024-03', 'CBL-002', 70, 160, 0, 0),
('2024-03', 'WDG-003', 35, 85, 0, 0),
('2024-03', 'GAD-004', 110, 280, 0, 0),
('2024-03', 'ACC-005', 5, 15, 0, 0);

-- Insert some stockout dates
INSERT INTO stockout_dates (sku_id, warehouse, stockout_date, is_resolved) VALUES
('CHG-001', 'kentucky', '2024-03-05', FALSE),
('ACC-005', 'kentucky', '2024-02-10', TRUE);

-- Insert pending inventory
INSERT INTO pending_inventory (sku_id, quantity, destination, order_date, expected_arrival, order_type, status) VALUES
('CHG-001', 300, 'burnaby', '2024-03-01', '2024-03-15', 'supplier', 'ordered'),
('CBL-002', 500, 'burnaby', '2024-02-28', '2024-03-10', 'supplier', 'shipped'),
('WDG-003', 200, 'kentucky', '2024-03-05', '2024-03-12', 'transfer', 'shipped');