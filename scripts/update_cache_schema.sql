-- Update sku_demand_stats table to support caching functionality
-- This script adds cache management columns to support the new CacheManager system

-- Add cache management columns if they don't exist
ALTER TABLE sku_demand_stats
ADD COLUMN IF NOT EXISTS cache_valid BOOLEAN DEFAULT FALSE AFTER standard_deviation,
ADD COLUMN IF NOT EXISTS invalidated_at TIMESTAMP NULL AFTER cache_valid,
ADD COLUMN IF NOT EXISTS invalidation_reason VARCHAR(255) NULL AFTER invalidated_at,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP AFTER invalidation_reason,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

-- Add warehouse column if it doesn't exist (needed for warehouse-specific caching)
ALTER TABLE sku_demand_stats
ADD COLUMN IF NOT EXISTS warehouse VARCHAR(20) DEFAULT 'kentucky' AFTER sku_id;

-- Create composite unique key for efficient cache lookups
ALTER TABLE sku_demand_stats
DROP INDEX IF EXISTS idx_sku_warehouse_cache,
ADD UNIQUE KEY idx_sku_warehouse_cache (sku_id, warehouse);

-- Create index for cache validity queries
ALTER TABLE sku_demand_stats
ADD INDEX IF NOT EXISTS idx_cache_valid (cache_valid, last_calculated);

-- Create index for warehouse-specific queries
ALTER TABLE sku_demand_stats
ADD INDEX IF NOT EXISTS idx_warehouse (warehouse);

-- Show the updated table structure
DESCRIBE sku_demand_stats;