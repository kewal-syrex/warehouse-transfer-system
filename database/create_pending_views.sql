-- Create Views for Enhanced Pending Orders Support
-- Version: 1.0
-- Date: September 2025

USE warehouse_transfer;

-- Drop existing views if they exist
DROP VIEW IF EXISTS v_pending_orders_analysis;
DROP VIEW IF EXISTS v_pending_quantities;

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
    -- Calculate actual arrival date (expected or estimated)
    CASE
        WHEN pi.expected_arrival IS NOT NULL THEN pi.expected_arrival
        ELSE DATE_ADD(pi.order_date, INTERVAL pi.lead_time_days DAY)
    END as calculated_arrival_date,
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

COMMIT;