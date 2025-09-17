-- Fix pending_inventory table to allow NULL expected_arrival dates
-- This enables the 120-day estimated lead time feature for orders without explicit dates

USE warehouse_transfer;

-- Modify the expected_arrival column to allow NULL values
ALTER TABLE pending_inventory
MODIFY COLUMN expected_arrival DATE NULL COMMENT 'Expected arrival date (NULL = calculate from order_date + lead_time_days)';

-- Update any existing records that might have empty expected_arrival
-- (This is just a safety measure, shouldn't be needed if data is clean)

COMMIT;