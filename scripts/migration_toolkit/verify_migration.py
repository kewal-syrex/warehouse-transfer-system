#!/usr/bin/env python3
"""
Warehouse Transfer System - Migration Verification Script
Version: 1.0
Purpose: Comprehensive verification of database migration success
Usage: python verify_migration.py [database_name] [username]
"""

import sys
import os
import pymysql
import json
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

# Color codes for console output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_success(message: str):
    print(f"{Colors.GREEN}✓{Colors.END} {message}")

def print_error(message: str):
    print(f"{Colors.RED}✗{Colors.END} {message}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠{Colors.END} {message}")

def print_info(message: str):
    print(f"{Colors.BLUE}ℹ{Colors.END} {message}")

def print_header(message: str):
    print(f"\n{Colors.BOLD}{message}{Colors.END}")
    print("=" * len(message))

class MigrationVerifier:
    """
    Comprehensive migration verification tool

    Verifies:
    - Database connectivity
    - Table structure and existence
    - Data integrity and counts
    - Views and triggers
    - Indexes and constraints
    - Configuration completeness
    """

    def __init__(self, database_name: str = 'warehouse_transfer', username: str = 'warehouse_user'):
        """Initialize the verifier with database connection details"""
        self.database_name = database_name
        self.username = username
        self.connection = None
        self.verification_results = {
            'connection': False,
            'tables': {},
            'views': {},
            'triggers': {},
            'data_counts': {},
            'indexes': {},
            'constraints': {},
            'configuration': {},
            'errors': [],
            'warnings': []
        }

    def connect_database(self) -> bool:
        """Establish database connection"""
        try:
            # Get password from user
            import getpass
            password = getpass.getpass(f"Enter MySQL password for '{self.username}': ")

            self.connection = pymysql.connect(
                host='localhost',
                user=self.username,
                password=password,
                database=self.database_name,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            # Test connection
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT VERSION() as version, DATABASE() as current_db")
                result = cursor.fetchone()
                print_info(f"Connected to MySQL {result['version']}")
                print_info(f"Current database: {result['current_db']}")

            self.verification_results['connection'] = True
            return True

        except Exception as e:
            print_error(f"Database connection failed: {str(e)}")
            self.verification_results['errors'].append(f"Connection failed: {str(e)}")
            return False

    def verify_tables(self) -> bool:
        """Verify all expected tables exist with correct structure"""
        print_header("VERIFYING TABLES")

        # Define expected tables and their key columns
        expected_tables = {
            'skus': ['sku_id', 'description', 'status', 'abc_code', 'xyz_code'],
            'inventory_current': ['sku_id', 'burnaby_qty', 'kentucky_qty'],
            'monthly_sales': ['year_month', 'sku_id', 'kentucky_sales', 'kentucky_stockout_days'],
            'pending_inventory': ['sku_id', 'quantity', 'destination', 'expected_arrival'],
            'stockout_dates': ['sku_id', 'warehouse', 'stockout_date'],
            'transfer_history': ['sku_id', 'quantity', 'transfer_date'],
            'system_config': ['config_key', 'config_value', 'category'],
            'supplier_lead_times': ['supplier', 'lead_time_days', 'destination']
        }

        all_tables_ok = True

        try:
            with self.connection.cursor() as cursor:
                # Get all existing tables
                cursor.execute("SHOW TABLES")
                existing_tables = [row[f'Tables_in_{self.database_name}'] for row in cursor.fetchall()]

                print_info(f"Found {len(existing_tables)} tables in database")

                for table_name, required_columns in expected_tables.items():
                    if table_name in existing_tables:
                        # Check table structure
                        cursor.execute(f"DESCRIBE {table_name}")
                        columns = cursor.fetchall()
                        column_names = [col['Field'] for col in columns]

                        missing_columns = [col for col in required_columns if col not in column_names]

                        if missing_columns:
                            print_warning(f"Table '{table_name}' missing columns: {missing_columns}")
                            self.verification_results['warnings'].append(
                                f"Table {table_name} missing columns: {missing_columns}"
                            )
                        else:
                            print_success(f"Table '{table_name}' structure OK")

                        self.verification_results['tables'][table_name] = {
                            'exists': True,
                            'columns': column_names,
                            'missing_columns': missing_columns
                        }
                    else:
                        print_error(f"Table '{table_name}' not found")
                        self.verification_results['tables'][table_name] = {'exists': False}
                        self.verification_results['errors'].append(f"Missing table: {table_name}")
                        all_tables_ok = False

                # Report any extra tables
                extra_tables = [t for t in existing_tables if t not in expected_tables]
                if extra_tables:
                    print_info(f"Additional tables found: {extra_tables}")
                    self.verification_results['tables']['extra_tables'] = extra_tables

        except Exception as e:
            print_error(f"Table verification failed: {str(e)}")
            self.verification_results['errors'].append(f"Table verification error: {str(e)}")
            return False

        return all_tables_ok

    def verify_views(self) -> bool:
        """Verify database views exist and are functional"""
        print_header("VERIFYING VIEWS")

        expected_views = [
            'v_pending_summary',
            'v_enhanced_transfer_recommendations',
            'v_inventory_summary',
            'v_year_over_year_sales',
            'v_category_averages'
        ]

        try:
            with self.connection.cursor() as cursor:
                # Get all views
                cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
                existing_views = [row[f'Tables_in_{self.database_name}'] for row in cursor.fetchall()]

                print_info(f"Found {len(existing_views)} views in database")

                for view_name in expected_views:
                    if view_name in existing_views:
                        try:
                            # Test view by selecting from it
                            cursor.execute(f"SELECT * FROM {view_name} LIMIT 1")
                            print_success(f"View '{view_name}' exists and functional")
                            self.verification_results['views'][view_name] = {'exists': True, 'functional': True}
                        except Exception as e:
                            print_warning(f"View '{view_name}' exists but has issues: {str(e)}")
                            self.verification_results['views'][view_name] = {'exists': True, 'functional': False}
                            self.verification_results['warnings'].append(f"View {view_name} not functional: {str(e)}")
                    else:
                        print_info(f"View '{view_name}' not found (may be optional)")
                        self.verification_results['views'][view_name] = {'exists': False}

                if existing_views:
                    print_info(f"All views: {existing_views}")

        except Exception as e:
            print_error(f"View verification failed: {str(e)}")
            self.verification_results['errors'].append(f"View verification error: {str(e)}")
            return False

        return True

    def verify_data_counts(self) -> bool:
        """Verify data exists in key tables"""
        print_header("VERIFYING DATA COUNTS")

        key_tables = ['skus', 'inventory_current', 'monthly_sales', 'pending_inventory', 'system_config']

        try:
            with self.connection.cursor() as cursor:
                for table in key_tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                        result = cursor.fetchone()
                        count = result['count']

                        if count > 0:
                            print_success(f"Table '{table}': {count:,} records")
                        else:
                            print_warning(f"Table '{table}': No data (this may be normal for new installations)")

                        self.verification_results['data_counts'][table] = count

                    except Exception as e:
                        print_error(f"Could not count records in '{table}': {str(e)}")
                        self.verification_results['errors'].append(f"Count error for {table}: {str(e)}")

        except Exception as e:
            print_error(f"Data count verification failed: {str(e)}")
            return False

        return True

    def verify_indexes(self) -> bool:
        """Verify important indexes exist"""
        print_header("VERIFYING INDEXES")

        # Key indexes that should exist for performance
        important_indexes = {
            'skus': ['PRIMARY', 'idx_status', 'idx_abc_xyz'],
            'monthly_sales': ['PRIMARY', 'idx_year_month'],
            'inventory_current': ['PRIMARY'],
            'pending_inventory': ['PRIMARY', 'idx_destination']
        }

        try:
            with self.connection.cursor() as cursor:
                for table, expected_indexes in important_indexes.items():
                    try:
                        cursor.execute(f"SHOW INDEX FROM {table}")
                        indexes = cursor.fetchall()
                        index_names = [idx['Key_name'] for idx in indexes]

                        missing_indexes = [idx for idx in expected_indexes if idx not in index_names]

                        if missing_indexes:
                            print_warning(f"Table '{table}' missing indexes: {missing_indexes}")
                            self.verification_results['warnings'].append(f"Missing indexes on {table}: {missing_indexes}")
                        else:
                            print_success(f"Table '{table}' has all expected indexes")

                        self.verification_results['indexes'][table] = {
                            'existing': index_names,
                            'missing': missing_indexes
                        }

                    except Exception as e:
                        print_warning(f"Could not check indexes for '{table}': {str(e)}")

        except Exception as e:
            print_error(f"Index verification failed: {str(e)}")
            return False

        return True

    def verify_configuration(self) -> bool:
        """Verify system configuration is complete"""
        print_header("VERIFYING CONFIGURATION")

        try:
            with self.connection.cursor() as cursor:
                # Check if system_config table has data
                cursor.execute("SELECT COUNT(*) as count FROM system_config")
                config_count = cursor.fetchone()['count']

                if config_count > 0:
                    print_success(f"Found {config_count} configuration settings")

                    # Get configuration by category
                    cursor.execute("SELECT category, COUNT(*) as count FROM system_config GROUP BY category")
                    categories = cursor.fetchall()

                    for cat in categories:
                        print_info(f"  {cat['category']}: {cat['count']} settings")

                    self.verification_results['configuration']['total_settings'] = config_count
                    self.verification_results['configuration']['categories'] = categories
                else:
                    print_warning("No configuration settings found")
                    print_info("This is normal for basic installations")
                    self.verification_results['configuration']['total_settings'] = 0

                # Check supplier lead times
                cursor.execute("SELECT COUNT(*) as count FROM supplier_lead_times")
                supplier_count = cursor.fetchone()['count']

                if supplier_count > 0:
                    print_success(f"Found {supplier_count} supplier lead time configurations")
                else:
                    print_info("No supplier-specific lead times configured")

                self.verification_results['configuration']['supplier_lead_times'] = supplier_count

        except Exception as e:
            print_error(f"Configuration verification failed: {str(e)}")
            return False

        return True

    def verify_foreign_keys(self) -> bool:
        """Verify foreign key constraints are in place"""
        print_header("VERIFYING FOREIGN KEY CONSTRAINTS")

        try:
            with self.connection.cursor() as cursor:
                # Check foreign key constraints
                cursor.execute("""
                    SELECT
                        TABLE_NAME,
                        COLUMN_NAME,
                        CONSTRAINT_NAME,
                        REFERENCED_TABLE_NAME,
                        REFERENCED_COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE REFERENCED_TABLE_SCHEMA = %s
                    AND REFERENCED_TABLE_NAME IS NOT NULL
                """, (self.database_name,))

                foreign_keys = cursor.fetchall()

                if foreign_keys:
                    print_success(f"Found {len(foreign_keys)} foreign key constraints")
                    for fk in foreign_keys:
                        print_info(f"  {fk['TABLE_NAME']}.{fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}")
                else:
                    print_warning("No foreign key constraints found")
                    print_info("This may be normal depending on your schema")

                self.verification_results['constraints']['foreign_keys'] = len(foreign_keys)

        except Exception as e:
            print_error(f"Foreign key verification failed: {str(e)}")
            return False

        return True

    def run_functional_tests(self) -> bool:
        """Run basic functional tests on the database"""
        print_header("RUNNING FUNCTIONAL TESTS")

        tests_passed = 0
        total_tests = 0

        try:
            with self.connection.cursor() as cursor:
                # Test 1: Basic SKU operations
                total_tests += 1
                try:
                    cursor.execute("SELECT COUNT(*) as count FROM skus WHERE status = 'Active'")
                    result = cursor.fetchone()
                    print_success(f"SKU query test passed - {result['count']} active SKUs")
                    tests_passed += 1
                except Exception as e:
                    print_error(f"SKU query test failed: {str(e)}")

                # Test 2: Sales data aggregation
                total_tests += 1
                try:
                    cursor.execute("""
                        SELECT year_month, COUNT(*) as sku_count, SUM(kentucky_sales) as total_sales
                        FROM monthly_sales
                        GROUP BY year_month
                        ORDER BY year_month DESC
                        LIMIT 3
                    """)
                    results = cursor.fetchall()
                    if results:
                        print_success(f"Sales aggregation test passed - {len(results)} periods found")
                        for row in results:
                            print_info(f"  {row['year_month']}: {row['sku_count']} SKUs, {row['total_sales']} total sales")
                    else:
                        print_warning("Sales aggregation test: No sales data found")
                    tests_passed += 1
                except Exception as e:
                    print_error(f"Sales aggregation test failed: {str(e)}")

                # Test 3: Inventory totals
                total_tests += 1
                try:
                    cursor.execute("""
                        SELECT
                            SUM(burnaby_qty) as total_burnaby,
                            SUM(kentucky_qty) as total_kentucky,
                            COUNT(*) as total_skus
                        FROM inventory_current
                    """)
                    result = cursor.fetchone()
                    print_success(f"Inventory test passed - {result['total_skus']} SKUs in inventory")
                    print_info(f"  Burnaby: {result['total_burnaby'] or 0:,} units")
                    print_info(f"  Kentucky: {result['total_kentucky'] or 0:,} units")
                    tests_passed += 1
                except Exception as e:
                    print_error(f"Inventory test failed: {str(e)}")

                # Test 4: Configuration access
                total_tests += 1
                try:
                    cursor.execute("SELECT config_key, config_value FROM system_config LIMIT 3")
                    configs = cursor.fetchall()
                    if configs:
                        print_success(f"Configuration test passed - {len(configs)} sample configs retrieved")
                    else:
                        print_info("Configuration test: No configurations found (normal for basic setup)")
                    tests_passed += 1
                except Exception as e:
                    print_error(f"Configuration test failed: {str(e)}")

            print_info(f"Functional tests: {tests_passed}/{total_tests} passed")

        except Exception as e:
            print_error(f"Functional testing failed: {str(e)}")
            return False

        return tests_passed >= (total_tests * 0.75)  # 75% pass rate required

    def generate_report(self) -> str:
        """Generate a comprehensive verification report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = {
            'verification_timestamp': timestamp,
            'database_name': self.database_name,
            'username': self.username,
            'results': self.verification_results,
            'summary': {
                'connection_successful': self.verification_results['connection'],
                'tables_verified': len([t for t in self.verification_results['tables'].values() if isinstance(t, dict) and t.get('exists', False)]),
                'total_records': sum(self.verification_results['data_counts'].values()),
                'errors_count': len(self.verification_results['errors']),
                'warnings_count': len(self.verification_results['warnings'])
            }
        }

        return json.dumps(report, indent=2)

    def run_full_verification(self) -> bool:
        """Run complete verification suite"""
        print_header("WAREHOUSE TRANSFER DATABASE MIGRATION VERIFICATION")
        print_info(f"Database: {self.database_name}")
        print_info(f"User: {self.username}")
        print_info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Track overall success
        verification_success = True

        # 1. Database connection
        if not self.connect_database():
            return False
        print_success("Database connection established")

        # 2. Table verification
        if not self.verify_tables():
            verification_success = False

        # 3. View verification
        if not self.verify_views():
            verification_success = False

        # 4. Data count verification
        if not self.verify_data_counts():
            verification_success = False

        # 5. Index verification
        if not self.verify_indexes():
            verification_success = False

        # 6. Configuration verification
        if not self.verify_configuration():
            verification_success = False

        # 7. Foreign key verification
        if not self.verify_foreign_keys():
            verification_success = False

        # 8. Functional tests
        if not self.run_functional_tests():
            verification_success = False

        # Generate and save report
        report = self.generate_report()
        report_file = f"migration_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(report_file, 'w') as f:
                f.write(report)
            print_info(f"Detailed report saved: {report_file}")
        except Exception as e:
            print_warning(f"Could not save report: {str(e)}")

        # Final summary
        print_header("VERIFICATION SUMMARY")

        if verification_success:
            print_success("✓ MIGRATION VERIFICATION PASSED")
            print_info("Your database migration was successful!")
        else:
            print_error("✗ MIGRATION VERIFICATION FAILED")
            print_info("Please review the errors above and fix any issues")

        # Error and warning summary
        if self.verification_results['errors']:
            print_error(f"Errors found ({len(self.verification_results['errors'])}):")
            for error in self.verification_results['errors']:
                print(f"  - {error}")

        if self.verification_results['warnings']:
            print_warning(f"Warnings found ({len(self.verification_results['warnings'])}):")
            for warning in self.verification_results['warnings']:
                print(f"  - {warning}")

        if not self.verification_results['errors'] and not self.verification_results['warnings']:
            print_success("No errors or warnings found!")

        # Database summary
        total_records = sum(self.verification_results['data_counts'].values())
        if total_records > 0:
            print_info(f"Total records across all tables: {total_records:,}")

        print_info("\nNext steps:")
        if verification_success:
            print("1. Start the application: uvicorn backend.main:app --host 0.0.0.0 --port 8000")
            print("2. Access the web interface: http://your-server-ip:8000/static/index.html")
            print("3. Test key functionality: transfer planning, data import/export")
        else:
            print("1. Review and fix the errors listed above")
            print("2. Re-run this verification script")
            print("3. Check the migration guide for troubleshooting")

        return verification_success

def main():
    """Main entry point"""
    # Parse command line arguments
    database_name = sys.argv[1] if len(sys.argv) > 1 else 'warehouse_transfer'
    username = sys.argv[2] if len(sys.argv) > 2 else 'warehouse_user'

    # Create and run verifier
    verifier = MigrationVerifier(database_name, username)
    success = verifier.run_full_verification()

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()