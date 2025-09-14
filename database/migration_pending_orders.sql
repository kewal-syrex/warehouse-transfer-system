-- Migration Script: Enhanced Pending Orders Support
-- Version: 1.1
-- Date: September 2025
-- Purpose: Add flexible lead time handling and better tracking for pending orders

USE warehouse_transfer;

-- Add new columns to pending_inventory table
ALTER TABLE pending_inventory
ADD COLUMN lead_time_days INT DEFAULT 120 COMMENT 'Lead time in days (default 4 months)',
ADD COLUMN is_estimated BOOLEAN DEFAULT TRUE COMMENT 'Whether the arrival date is estimated';

-- Create performance indexes for the new columns
CREATE INDEX idx_pending_lead_time ON pending_inventory(lead_time_days);
CREATE INDEX idx_pending_estimated ON pending_inventory(is_estimated);

-- Update existing records to have proper lead time values
-- Calculate lead time based on existing expected_arrival dates where available
UPDATE pending_inventory
SET lead_time_days = GREATEST(DATEDIFF(expected_arrival, order_date), 1),
    is_estimated = FALSE
WHERE expected_arrival IS NOT NULL AND order_date IS NOT NULL;

-- Create view for pending orders analysis
CREATE VIEW v_pending_orders_analysis AS
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
        WHEN pi.expected_arrival IS NULL
             AND DATE_ADD(pi.order_date, INTERVAL pi.lead_time_days DAY) < CURDATE()
             AND pi.status NOT IN ('received', 'cancelled') THEN TRUE
        ELSE FALSE
    END as is_overdue,
    -- Calculate priority score (higher = more urgent)
    CASE
        WHEN pi.status = 'received' THEN 0
        WHEN pi.status = 'cancelled' THEN 0
        ELSE (120 - LEAST(120, GREATEST(0,
            CASE
                WHEN pi.expected_arrival IS NOT NULL THEN
                    DATEDIFF(pi.expected_arrival, CURDATE())
                ELSE
                    DATEDIFF(DATE_ADD(pi.order_date, INTERVAL pi.lead_time_days DAY), CURDATE())
            END
        )))
    END as priority_score
FROM pending_inventory pi
INNER JOIN skus s ON pi.sku_id = s.sku_id
ORDER BY priority_score DESC, pi.order_date ASC;

-- Create view for current pending quantities by warehouse
CREATE VIEW v_pending_quantities AS
SELECT
    sku_id,
    SUM(CASE WHEN destination = 'burnaby' THEN quantity ELSE 0 END) as burnaby_pending,
    SUM(CASE WHEN destination = 'kentucky' THEN quantity ELSE 0 END) as kentucky_pending,
    SUM(quantity) as total_pending,
    -- Count orders by type
    COUNT(CASE WHEN order_type = 'supplier' THEN 1 END) as supplier_orders,
    COUNT(CASE WHEN order_type = 'transfer' THEN 1 END) as transfer_orders,
    -- Earliest expected arrival
    MIN(CASE
        WHEN expected_arrival IS NOT NULL THEN expected_arrival
        ELSE DATE_ADD(order_date, INTERVAL lead_time_days DAY)
    END) as earliest_arrival
FROM pending_inventory
WHERE status NOT IN ('received', 'cancelled')
GROUP BY sku_id;

-- Sample data updates for testing
-- Update some existing records with more realistic lead times
UPDATE pending_inventory
SET lead_time_days = 90,
    is_estimated = TRUE,
    notes = 'Standard supplier lead time - estimated'
WHERE order_type = 'supplier' AND lead_time_days = 120;

UPDATE pending_inventory
SET lead_time_days = 7,
    is_estimated = FALSE,
    notes = 'Internal transfer - confirmed'
WHERE order_type = 'transfer';

-- Test data will be added separately to avoid foreign key conflicts

COMMIT;