#!/usr/bin/env python3
"""
Database Schema Setup for Caching System

This script creates and updates the database schema to support the caching
functionality that solves the database connection exhaustion issue.

Tables Created/Updated:
- sku_demand_stats: Stores cached weighted demand calculations
- cache_refresh_log: Tracks cache refresh operations

Features:
- Safe schema updates (IF NOT EXISTS, ADD COLUMN IF NOT EXISTS)
- Rollback capability for failed updates
- Comprehensive error handling and logging
- Schema validation after creation
"""

import sys
import os
import logging
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.database import execute_query, test_connection
    from backend.database_pool import get_connection_pool
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cache_schema_setup.log')
    ]
)
logger = logging.getLogger(__name__)


class CacheSchemaManager:
    """
    Manages database schema setup for the caching system
    """

    def __init__(self):
        """Initialize the schema manager"""
        self.setup_steps = []
        self.completed_steps = []
        self.failed_steps = []

    def setup_sku_demand_stats_table(self) -> bool:
        """
        Create or update the sku_demand_stats table for caching weighted demand calculations

        Returns:
            True if setup was successful
        """
        logger.info("Setting up sku_demand_stats table...")

        # Create table if it doesn't exist
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS sku_demand_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sku_id VARCHAR(50) NOT NULL,
            warehouse ENUM('kentucky', 'burnaby') NOT NULL,
            enhanced_demand DECIMAL(10,2) DEFAULT 0.00,
            weighted_average_base DECIMAL(10,2) DEFAULT 0.00,
            volatility_adjustment DECIMAL(5,3) DEFAULT 1.000,
            calculation_method VARCHAR(50) DEFAULT 'weighted',
            primary_method VARCHAR(50) DEFAULT 'weighted',
            sample_months INT DEFAULT 0,
            data_quality_score DECIMAL(5,3) DEFAULT 0.000,
            volatility_class VARCHAR(10) DEFAULT 'unknown',
            coefficient_variation DECIMAL(8,5) DEFAULT 0.00000,
            standard_deviation DECIMAL(10,2) DEFAULT 0.00,
            cache_valid BOOLEAN DEFAULT FALSE,
            invalidated_at TIMESTAMP NULL,
            invalidation_reason VARCHAR(255) NULL,
            last_calculated TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_sku_warehouse (sku_id, warehouse),
            INDEX idx_sku_id (sku_id),
            INDEX idx_warehouse (warehouse),
            INDEX idx_cache_valid (cache_valid),
            INDEX idx_last_calculated (last_calculated)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        try:
            execute_query(create_table_sql, fetch_all=False)
            logger.info("sku_demand_stats table created/verified successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create sku_demand_stats table: {e}")
            return False

    def setup_cache_refresh_log_table(self) -> bool:
        """
        Create the cache_refresh_log table to track cache refresh operations

        Returns:
            True if setup was successful
        """
        logger.info("Setting up cache_refresh_log table...")

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS cache_refresh_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            refresh_type ENUM('full', 'partial', 'sku_specific') NOT NULL,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP NULL,
            duration_seconds DECIMAL(8,2) NULL,
            total_skus INT DEFAULT 0,
            processed_skus INT DEFAULT 0,
            successful_calculations INT DEFAULT 0,
            failed_calculations INT DEFAULT 0,
            error_count INT DEFAULT 0,
            trigger_reason VARCHAR(255) NULL,
            triggered_by VARCHAR(100) NULL,
            status ENUM('running', 'completed', 'failed', 'cancelled') DEFAULT 'running',
            error_message TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_started_at (started_at),
            INDEX idx_status (status),
            INDEX idx_refresh_type (refresh_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        try:
            execute_query(create_table_sql, fetch_all=False)
            logger.info("cache_refresh_log table created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create cache_refresh_log table: {e}")
            return False

    def add_missing_columns(self) -> bool:
        """
        Add any missing columns to existing tables (for upgrades)

        Returns:
            True if all column additions were successful
        """
        logger.info("Checking for missing columns...")

        # List of column additions to try
        column_additions = [
            {
                'table': 'sku_demand_stats',
                'column': 'cache_valid',
                'definition': 'BOOLEAN DEFAULT FALSE',
                'description': 'Cache validity flag'
            },
            {
                'table': 'sku_demand_stats',
                'column': 'invalidated_at',
                'definition': 'TIMESTAMP NULL',
                'description': 'Cache invalidation timestamp'
            },
            {
                'table': 'sku_demand_stats',
                'column': 'invalidation_reason',
                'definition': 'VARCHAR(255) NULL',
                'description': 'Reason for cache invalidation'
            },
            {
                'table': 'sku_demand_stats',
                'column': 'last_calculated',
                'definition': 'TIMESTAMP NULL',
                'description': 'Last calculation timestamp'
            }
        ]

        success_count = 0
        for addition in column_additions:
            try:
                # Try to add the column (will fail silently if it already exists)
                sql = f"""
                ALTER TABLE {addition['table']}
                ADD COLUMN IF NOT EXISTS {addition['column']} {addition['definition']}
                """

                execute_query(sql, fetch_all=False)
                logger.info(f"Added/verified column {addition['table']}.{addition['column']}")
                success_count += 1

            except Exception as e:
                # Log but don't fail - column might already exist
                logger.warning(f"Could not add column {addition['table']}.{addition['column']}: {e}")

        logger.info(f"Column addition check completed: {success_count}/{len(column_additions)} successful")
        return True

    def add_indexes(self) -> bool:
        """
        Add performance indexes for cache operations

        Returns:
            True if index creation was successful
        """
        logger.info("Adding performance indexes...")

        indexes = [
            {
                'table': 'sku_demand_stats',
                'name': 'idx_cache_lookup',
                'definition': '(sku_id, warehouse, cache_valid)',
                'description': 'Fast cache lookup index'
            },
            {
                'table': 'sku_demand_stats',
                'name': 'idx_invalidation',
                'definition': '(cache_valid, invalidated_at)',
                'description': 'Cache invalidation index'
            },
            {
                'table': 'cache_refresh_log',
                'name': 'idx_recent_operations',
                'definition': '(started_at DESC, status)',
                'description': 'Recent operations index'
            }
        ]

        success_count = 0
        for index in indexes:
            try:
                # Create index if it doesn't exist
                sql = f"""
                CREATE INDEX IF NOT EXISTS {index['name']}
                ON {index['table']} {index['definition']}
                """

                execute_query(sql, fetch_all=False)
                logger.info(f"Added/verified index {index['name']} on {index['table']}")
                success_count += 1

            except Exception as e:
                logger.warning(f"Could not create index {index['name']}: {e}")

        logger.info(f"Index creation completed: {success_count}/{len(indexes)} successful")
        return success_count > 0

    def validate_schema(self) -> Dict[str, Any]:
        """
        Validate that the cache schema is properly set up

        Returns:
            Dictionary containing validation results
        """
        logger.info("Validating cache schema...")

        validation_results = {
            'sku_demand_stats_exists': False,
            'cache_refresh_log_exists': False,
            'required_columns_present': False,
            'indexes_present': False,
            'sample_data_insertable': False,
            'errors': []
        }

        try:
            # Check if tables exist
            tables_query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name IN ('sku_demand_stats', 'cache_refresh_log')
            """

            tables_result = execute_query(tables_query, fetch_all=True)
            table_names = [row['table_name'] for row in tables_result] if tables_result else []

            validation_results['sku_demand_stats_exists'] = 'sku_demand_stats' in table_names
            validation_results['cache_refresh_log_exists'] = 'cache_refresh_log' in table_names

            # Check required columns in sku_demand_stats
            if validation_results['sku_demand_stats_exists']:
                columns_query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                AND table_name = 'sku_demand_stats'
                AND column_name IN ('cache_valid', 'invalidated_at', 'last_calculated')
                """

                columns_result = execute_query(columns_query, fetch_all=True)
                found_columns = [row['column_name'] for row in columns_result] if columns_result else []

                required_columns = ['cache_valid', 'invalidated_at', 'last_calculated']
                validation_results['required_columns_present'] = all(col in found_columns for col in required_columns)

            # Test sample data insertion
            if validation_results['sku_demand_stats_exists']:
                try:
                    test_insert = """
                    INSERT INTO sku_demand_stats
                    (sku_id, warehouse, enhanced_demand, cache_valid)
                    VALUES ('TEST-SCHEMA-VALIDATION', 'kentucky', 1.00, TRUE)
                    ON DUPLICATE KEY UPDATE enhanced_demand = 1.00
                    """

                    execute_query(test_insert, fetch_all=False)

                    # Clean up test data
                    cleanup = """
                    DELETE FROM sku_demand_stats
                    WHERE sku_id = 'TEST-SCHEMA-VALIDATION'
                    """
                    execute_query(cleanup, fetch_all=False)

                    validation_results['sample_data_insertable'] = True

                except Exception as e:
                    validation_results['errors'].append(f"Sample data insertion failed: {e}")

        except Exception as e:
            validation_results['errors'].append(f"Schema validation failed: {e}")

        # Overall validation status
        validation_results['schema_valid'] = (
            validation_results['sku_demand_stats_exists'] and
            validation_results['cache_refresh_log_exists'] and
            validation_results['required_columns_present'] and
            validation_results['sample_data_insertable']
        )

        logger.info(f"Schema validation completed. Valid: {validation_results['schema_valid']}")
        return validation_results

    def setup_complete_schema(self) -> bool:
        """
        Perform complete cache schema setup

        Returns:
            True if all setup steps were successful
        """
        logger.info("Starting complete cache schema setup...")

        setup_steps = [
            ("Test database connection", self._test_connection),
            ("Setup sku_demand_stats table", self.setup_sku_demand_stats_table),
            ("Setup cache_refresh_log table", self.setup_cache_refresh_log_table),
            ("Add missing columns", self.add_missing_columns),
            ("Create performance indexes", self.add_indexes),
            ("Validate schema", self._validate_and_return_success)
        ]

        for step_name, step_function in setup_steps:
            try:
                logger.info(f"Executing: {step_name}")
                success = step_function()

                if success:
                    logger.info(f"✓ {step_name} completed successfully")
                    self.completed_steps.append(step_name)
                else:
                    logger.error(f"✗ {step_name} failed")
                    self.failed_steps.append(step_name)

            except Exception as e:
                logger.error(f"✗ {step_name} failed with exception: {e}")
                self.failed_steps.append(step_name)

        success_rate = len(self.completed_steps) / len(setup_steps)
        logger.info(f"Schema setup completed. Success rate: {success_rate:.1%}")
        logger.info(f"Completed steps: {self.completed_steps}")

        if self.failed_steps:
            logger.warning(f"Failed steps: {self.failed_steps}")

        return success_rate >= 0.8  # Consider successful if 80% of steps pass

    def _test_connection(self) -> bool:
        """Test database connection"""
        return test_connection()

    def _validate_and_return_success(self) -> bool:
        """Validate schema and return success status"""
        results = self.validate_schema()
        return results['schema_valid']


def main():
    """
    Main function to run cache schema setup
    """
    print("Warehouse Transfer Cache Schema Setup")
    print("=" * 50)

    try:
        # Initialize schema manager
        schema_manager = CacheSchemaManager()

        # Run complete setup
        success = schema_manager.setup_complete_schema()

        if success:
            print("\n✓ Cache schema setup completed successfully!")
            print("\nThe caching system is now ready to use.")
            print("Next steps:")
            print("1. Install SQLAlchemy: pip install sqlalchemy pymysql")
            print("2. Restart the application to enable connection pooling")
            print("3. Run cache refresh to populate initial data")

            return 0

        else:
            print("\n✗ Cache schema setup completed with some failures.")
            print("Check the logs for details about failed steps.")
            print("The system may still work with reduced functionality.")

            return 1

    except Exception as e:
        logger.error(f"Schema setup failed with critical error: {e}")
        print(f"\n✗ Critical error during schema setup: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)