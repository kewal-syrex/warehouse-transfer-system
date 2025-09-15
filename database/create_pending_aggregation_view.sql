-- ===================================================================
-- Pending Orders Aggregation View for Time-Weighted Calculations
-- ===================================================================
-- This view aggregates pending orders by SKU, destination, and time windows
-- for efficient transfer planning calculations
--
-- Time windows:
-- - immediate: 0-30 days (weight=1.0)
-- - near_term: 31-60 days (weight=0.8)
-- - medium_term: 61-90 days (weight=0.6)
-- - long_term: >90 days (weight=0.4)

USE warehouse_transfer;

-- Drop existing view if it exists
DROP VIEW IF EXISTS v_pending_orders_aggregated;

-- Create the aggregation view
CREATE VIEW v_pending_orders_aggregated AS
SELECT
    sku_id,
    destination,

    -- Time window aggregations with confidence weighting
    SUM(CASE
        WHEN days_until_arrival <= 30 THEN
            quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END)
        ELSE 0
    END) as immediate_qty,

    SUM(CASE
        WHEN days_until_arrival BETWEEN 31 AND 60 THEN
            quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END)
        ELSE 0
    END) as near_term_qty,

    SUM(CASE
        WHEN days_until_arrival BETWEEN 61 AND 90 THEN
            quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END)
        ELSE 0
    END) as medium_term_qty,

    SUM(CASE
        WHEN days_until_arrival > 90 THEN
            quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END)
        ELSE 0
    END) as long_term_qty,

    -- Time-weighted total for transfer calculations
    -- immediate=1.0, near=0.8, medium=0.6, long=0.4
    (
        SUM(CASE
            WHEN days_until_arrival <= 30 THEN
                quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END) * 1.0
            ELSE 0
        END) +
        SUM(CASE
            WHEN days_until_arrival BETWEEN 31 AND 60 THEN
                quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END) * 0.8
            ELSE 0
        END) +
        SUM(CASE
            WHEN days_until_arrival BETWEEN 61 AND 90 THEN
                quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END) * 0.6
            ELSE 0
        END) +
        SUM(CASE
            WHEN days_until_arrival > 90 THEN
                quantity * (CASE WHEN is_estimated THEN 0.8 ELSE 1.0 END) * 0.4
            ELSE 0
        END)
    ) AS total_weighted,

    -- Timeline information
    MIN(expected_arrival) as earliest_arrival,
    MAX(expected_arrival) as latest_arrival,

    -- Shipment details
    COUNT(*) as shipment_count,
    SUM(quantity) as total_raw_quantity,

    -- Confidence indicators
    SUM(CASE WHEN is_estimated THEN 1 ELSE 0 END) as estimated_shipments,
    SUM(CASE WHEN is_estimated THEN 0 ELSE 1 END) as confirmed_shipments,

    -- Status breakdown
    GROUP_CONCAT(DISTINCT status ORDER BY status) as statuses,
    GROUP_CONCAT(DISTINCT order_type ORDER BY order_type) as order_types

FROM (
    SELECT
        sku_id,
        destination,
        quantity,
        expected_arrival,
        is_estimated,
        status,
        order_type,
        DATEDIFF(expected_arrival, CURDATE()) as days_until_arrival
    FROM pending_inventory
    WHERE status IN ('ordered', 'shipped', 'pending')
        AND expected_arrival >= CURDATE()
) AS pending_with_days

GROUP BY sku_id, destination

-- Order by earliest arrival for consistent results
ORDER BY earliest_arrival ASC, sku_id, destination;

-- Create index on the underlying table to optimize the view
CREATE INDEX IF NOT EXISTS idx_pending_aggregation
ON pending_inventory(sku_id, destination, status, expected_arrival);

-- Display sample results for verification
SELECT 'Sample aggregated pending orders:' as info;
SELECT
    sku_id,
    destination,
    immediate_qty,
    near_term_qty,
    medium_term_qty,
    long_term_qty,
    total_weighted,
    earliest_arrival,
    shipment_count
FROM v_pending_orders_aggregated
LIMIT 10;

-- Display summary statistics
SELECT 'Aggregation summary:' as info;
SELECT
    destination,
    COUNT(*) as unique_skus_with_pending,
    SUM(shipment_count) as total_shipments,
    SUM(total_weighted) as total_weighted_quantity,
    MIN(earliest_arrival) as earliest_pending_arrival,
    MAX(latest_arrival) as latest_pending_arrival
FROM v_pending_orders_aggregated
GROUP BY destination
UNION ALL
SELECT
    'TOTAL' as destination,
    COUNT(*) as unique_skus_with_pending,
    SUM(shipment_count) as total_shipments,
    SUM(total_weighted) as total_weighted_quantity,
    MIN(earliest_arrival) as earliest_pending_arrival,
    MAX(latest_arrival) as latest_pending_arrival
FROM v_pending_orders_aggregated;