#!/usr/bin/env python3
"""
Update database schema to support caching functionality
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_cache_schema():
    """Update sku_demand_stats table to support caching"""

    schema_updates = [
        # Add cache management columns
        """
        ALTER TABLE sku_demand_stats
        ADD COLUMN cache_valid BOOLEAN DEFAULT FALSE AFTER standard_deviation
        """,

        """
        ALTER TABLE sku_demand_stats
        ADD COLUMN invalidated_at TIMESTAMP NULL AFTER cache_valid
        """,

        """
        ALTER TABLE sku_demand_stats
        ADD COLUMN invalidation_reason VARCHAR(255) NULL AFTER invalidated_at
        """,

        """
        ALTER TABLE sku_demand_stats
        ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP AFTER invalidation_reason
        """,

        """
        ALTER TABLE sku_demand_stats
        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at
        """,

        # Add warehouse column for warehouse-specific caching
        """
        ALTER TABLE sku_demand_stats
        ADD COLUMN warehouse VARCHAR(20) DEFAULT 'kentucky' AFTER sku_id
        """,

        # Create indexes for efficient cache lookups
        """
        ALTER TABLE sku_demand_stats
        ADD UNIQUE KEY idx_sku_warehouse_cache (sku_id, warehouse)
        """,

        """
        ALTER TABLE sku_demand_stats
        ADD INDEX idx_cache_valid (cache_valid, last_calculated)
        """,

        """
        ALTER TABLE sku_demand_stats
        ADD INDEX idx_warehouse (warehouse)
        """
    ]

    successful_updates = 0
    failed_updates = 0

    logger.info("Starting database schema update for caching system...")

    for i, query in enumerate(schema_updates, 1):
        try:
            logger.info(f"Executing update {i}/{len(schema_updates)}")
            database.execute_query(query.strip(), fetch_all=False)
            successful_updates += 1
            logger.info(f"✓ Update {i} completed successfully")

        except Exception as e:
            # Check if it's just a "column already exists" error
            if "Duplicate column name" in str(e) or "Duplicate key name" in str(e):
                logger.info(f"✓ Update {i} skipped (already exists)")
                successful_updates += 1
            else:
                logger.error(f"✗ Update {i} failed: {e}")
                failed_updates += 1

    # Verify the final table structure
    try:
        logger.info("Verifying table structure...")
        result = database.execute_query("DESCRIBE sku_demand_stats", fetch_all=True)

        logger.info("Current sku_demand_stats table structure:")
        for row in result:
            logger.info(f"  {row[0]} - {row[1]} - {row[2]} - {row[3]} - {row[4]}")

    except Exception as e:
        logger.error(f"Failed to verify table structure: {e}")

    logger.info(f"Schema update completed: {successful_updates} successful, {failed_updates} failed")

    return successful_updates, failed_updates

if __name__ == "__main__":
    try:
        successful, failed = update_cache_schema()
        if failed == 0:
            print("✅ Database schema update completed successfully!")
            sys.exit(0)
        else:
            print(f"⚠️ Schema update completed with {failed} failures")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Schema update failed: {e}")
        sys.exit(1)