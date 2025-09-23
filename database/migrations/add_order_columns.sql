-- Order Columns Database Migration
-- Version: 4.0
-- Date: September 2025
-- Description: Adds CA to Order and KY to Order columns to transfer_confirmations table

USE warehouse_transfer;

-- ===================================================================
-- Add CA and KY order columns to transfer_confirmations table
-- ===================================================================

ALTER TABLE transfer_confirmations
ADD COLUMN IF NOT EXISTS ca_order_qty INT DEFAULT NULL COMMENT 'Manual order quantity for CA warehouse',
ADD COLUMN IF NOT EXISTS ky_order_qty INT DEFAULT NULL COMMENT 'Manual order quantity for KY warehouse';

-- ===================================================================
-- Create indexes for performance optimization
-- ===================================================================

CREATE INDEX IF NOT EXISTS idx_ca_order_qty ON transfer_confirmations(ca_order_qty);
CREATE INDEX IF NOT EXISTS idx_ky_order_qty ON transfer_confirmations(ky_order_qty);

-- ===================================================================
-- Update schema validation
-- ===================================================================

-- Verify the columns were added successfully
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'warehouse_transfer'
  AND TABLE_NAME = 'transfer_confirmations'
  AND COLUMN_NAME IN ('ca_order_qty', 'ky_order_qty');

COMMIT;