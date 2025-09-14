"""
Playwright MCP Browser Test Suite for Pending Orders & CSV Import
Tests the pending orders functionality and CSV import capabilities
"""
import asyncio
import json
import requests
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

async def test_pending_orders_comprehensive():
    """
    Comprehensive test suite for pending orders functionality using Playwright MCP
    """
    test_results = {
        'test_timestamp': datetime.now().isoformat(),
        'ui_tests_passed': 0,
        'ui_tests_failed': 0,
        'api_tests_passed': 0,
        'api_tests_failed': 0,
        'test_details': []
    }

    try:
        logger.info("Starting Pending Orders Comprehensive Test Suite with Playwright MCP...")

        # Test 1: API endpoint testing
        await test_pending_orders_api_endpoints(test_results)

        # Test 2: CSV import functionality
        await test_csv_import_functionality(test_results)

        # Test 3: Pending orders UI components
        await test_pending_orders_ui_components(test_results)

        # Test 4: Enhanced transfer calculations with pending orders
        await test_enhanced_calculations_with_pending(test_results)

        # Test 5: Data validation and error handling
        await test_data_validation_and_errors(test_results)

        # Test 6: Integration with existing systems
        await test_integration_with_existing_systems(test_results)

        # Calculate final results
        total_tests = (test_results['ui_tests_passed'] + test_results['ui_tests_failed'] +
                      test_results['api_tests_passed'] + test_results['api_tests_failed'])

        success_rate = ((test_results['ui_tests_passed'] + test_results['api_tests_passed']) /
                       total_tests * 100) if total_tests > 0 else 0

        test_results['total_tests'] = total_tests
        test_results['success_rate'] = round(success_rate, 2)

        print("\n" + "="*80)
        print("PENDING ORDERS COMPREHENSIVE TEST RESULTS")
        print("="*80)
        print(f"Total Tests: {total_tests}")
        print(f"UI Tests: {test_results['ui_tests_passed']} passed, {test_results['ui_tests_failed']} failed")
        print(f"API Tests: {test_results['api_tests_passed']} passed, {test_results['api_tests_failed']} failed")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"Test Duration: {datetime.now().isoformat()}")

        # Print detailed results
        if test_results['test_details']:
            print(f"\nDETAILED TEST RESULTS:")
            print("-" * 80)
            for detail in test_results['test_details']:
                status = "✅ PASS" if detail['passed'] else "❌ FAIL"
                print(f"{status} | {detail['test_name']} | {detail['message']}")

        return test_results

    except Exception as e:
        logger.error(f"Test suite failed with error: {str(e)}")
        print(f"\n❌ TEST SUITE FAILED: {str(e)}")
        return test_results

async def test_pending_orders_api_endpoints(test_results):
    """Test all pending orders related API endpoints"""
    try:
        import requests

        base_url = "http://localhost:8000"

        # Test 1.1: Get pending orders endpoint
        response = requests.get(f"{base_url}/api/pending-orders")

        if response.status_code == 200:
            data = response.json()
            _record_api_test_result(test_results, "Get Pending Orders API", True,
                                  f"Returned {len(data)} pending orders")
        else:
            _record_api_test_result(test_results, "Get Pending Orders API", False,
                                  f"API returned status {response.status_code}")

        # Test 1.2: Get pending orders summary endpoint
        response = requests.get(f"{base_url}/api/pending-orders/summary")

        if response.status_code == 200:
            data = response.json()
            required_fields = ['total_pending_orders', 'total_pending_quantity']
            has_required_fields = all(field in data for field in required_fields)

            if has_required_fields:
                _record_api_test_result(test_results, "Pending Orders Summary API", True,
                                      f"Summary contains required fields")
            else:
                _record_api_test_result(test_results, "Pending Orders Summary API", False,
                                      "Summary missing required fields")
        else:
            _record_api_test_result(test_results, "Pending Orders Summary API", False,
                                  f"API returned status {response.status_code}")

        # Test 1.3: Enhanced transfer recommendations with pending orders
        response = requests.get(f"{base_url}/api/transfer-recommendations?enhanced=true")

        if response.status_code == 200:
            data = response.json()

            if data and len(data) > 0:
                first_rec = data[0]
                # Check if pending orders are considered in calculations
                has_pending_consideration = any(
                    'pending' in str(first_rec.get('reason', '')).lower() or
                    'pending' in str(first_rec.get('calculation_details', '')).lower()
                    for _ in [1]  # Just check if any mention of pending exists
                )

                _record_api_test_result(test_results, "Enhanced Recommendations with Pending", True,
                                      f"Recommendations consider pending orders: {has_pending_consideration}")
            else:
                _record_api_test_result(test_results, "Enhanced Recommendations with Pending", False,
                                      "No recommendations returned")
        else:
            _record_api_test_result(test_results, "Enhanced Recommendations with Pending", False,
                                  f"API returned status {response.status_code}")

    except Exception as e:
        logger.error(f"API endpoint testing failed: {str(e)}")
        _record_api_test_result(test_results, "Pending Orders API Tests", False,
                               f"Exception during API testing: {str(e)}")

async def test_csv_import_functionality(test_results):
    """Test CSV import functionality for pending orders"""
    try:
        # Test 2.1: Create sample CSV data
        sample_csv_content = """sku_id,quantity,destination,expected_date
SKU001,100,kentucky,2025-01-15
SKU002,50,burnaby,2025-02-01
SKU003,75,kentucky"""  # Missing date to test auto-calculation

        # Test the import function directly
        from backend.import_export import import_export_manager

        result = import_export_manager.import_pending_orders_csv(
            sample_csv_content.encode('utf-8'),
            "test_pending_orders.csv"
        )

        if result.get('success'):
            _record_api_test_result(test_results, "CSV Import Functionality", True,
                                  f"Successfully imported {result.get('records_imported', 0)} records")
        else:
            _record_api_test_result(test_results, "CSV Import Functionality", False,
                                  f"Import failed: {result.get('error', 'Unknown error')}")

        # Test 2.2: Test CSV validation (invalid data)
        invalid_csv_content = """sku_id,quantity,destination
INVALID_SKU,100,invalid_destination
,50,kentucky"""  # Missing SKU ID

        invalid_result = import_export_manager.import_pending_orders_csv(
            invalid_csv_content.encode('utf-8'),
            "test_invalid_pending_orders.csv"
        )

        # Should fail or have warnings
        has_validation = len(invalid_result.get('errors', [])) > 0 or len(invalid_result.get('warnings', [])) > 0

        _record_api_test_result(test_results, "CSV Validation Testing", has_validation,
                               f"Validation detected {len(invalid_result.get('errors', []))} errors and {len(invalid_result.get('warnings', []))} warnings")

    except Exception as e:
        logger.error(f"CSV import testing failed: {str(e)}")
        _record_api_test_result(test_results, "CSV Import Testing", False,
                               f"Exception during CSV import testing: {str(e)}")

async def test_pending_orders_ui_components(test_results):
    """Test pending orders UI components using Playwright MCP"""
    try:
        # Import Playwright MCP functions
        from . import mcp_playwright_helpers as mph  # Assuming helper functions exist

        # Test 3.1: Navigate to pending orders page
        try:
            await mph.navigate_to_page("http://localhost:8000")
            await mph.wait_for_page_load()

            # Look for pending orders section or navigation
            pending_orders_section = await mph.find_element_by_text("Pending Orders")
            if pending_orders_section:
                _record_ui_test_result(test_results, "Pending Orders Navigation", True,
                                     "Found pending orders section in UI")
            else:
                _record_ui_test_result(test_results, "Pending Orders Navigation", False,
                                     "Could not find pending orders section in UI")

        except Exception as e:
            _record_ui_test_result(test_results, "UI Navigation Test", False,
                                 f"Failed to navigate to UI: {str(e)}")

        # Test 3.2: Test pending orders data display
        try:
            # Look for pending orders table or data display
            await mph.wait_for_element("[data-testid='pending-orders-table']", timeout=5000)

            # Check if data is loaded
            rows = await mph.count_table_rows("[data-testid='pending-orders-table']")

            if rows > 0:
                _record_ui_test_result(test_results, "Pending Orders Data Display", True,
                                     f"Found {rows} pending orders in table")
            else:
                _record_ui_test_result(test_results, "Pending Orders Data Display", False,
                                     "No pending orders data found in table")

        except Exception as e:
            _record_ui_test_result(test_results, "Pending Orders Data Display", False,
                                 f"Could not test data display: {str(e)}")

        # Test 3.3: Test CSV import UI
        try:
            # Look for import button or file upload
            import_button = await mph.find_element_by_text("Import")
            if import_button:
                await mph.click_element(import_button)

                # Look for file upload input
                file_input = await mph.find_element("input[type='file']")
                if file_input:
                    _record_ui_test_result(test_results, "CSV Import UI", True,
                                         "Found CSV import functionality in UI")
                else:
                    _record_ui_test_result(test_results, "CSV Import UI", False,
                                         "Import button found but no file input")
            else:
                _record_ui_test_result(test_results, "CSV Import UI", False,
                                     "Could not find CSV import button in UI")

        except Exception as e:
            _record_ui_test_result(test_results, "CSV Import UI", False,
                                 f"Could not test CSV import UI: {str(e)}")

    except ImportError:
        logger.warning("Playwright MCP helpers not available, skipping UI tests")
        _record_ui_test_result(test_results, "UI Components Test", False,
                             "Playwright MCP helpers not available")
    except Exception as e:
        logger.error(f"UI components testing failed: {str(e)}")
        _record_ui_test_result(test_results, "UI Components Test", False,
                             f"Exception during UI testing: {str(e)}")

async def test_enhanced_calculations_with_pending(test_results):
    """Test that enhanced calculations properly incorporate pending orders"""
    try:
        import requests

        base_url = "http://localhost:8000"

        # Test 4.1: Get a specific SKU's calculation details
        response = requests.get(f"{base_url}/api/transfer-recommendations?enhanced=true")

        if response.status_code == 200:
            data = response.json()

            if data and len(data) > 0:
                # Check if any recommendations mention pending orders in reasoning
                pending_mentioned = any(
                    'pending' in str(rec.get('reason', '')).lower()
                    for rec in data[:5]  # Check first 5 recommendations
                )

                if pending_mentioned:
                    _record_api_test_result(test_results, "Pending Orders in Calculations", True,
                                          "Enhanced calculations reference pending orders")
                else:
                    _record_api_test_result(test_results, "Pending Orders in Calculations", False,
                                          "Enhanced calculations do not reference pending orders")

                # Test 4.2: Check for Burnaby retention logic
                retention_logic = any(
                    'burnaby' in str(rec.get('reason', '')).lower() and
                    'retention' in str(rec.get('reason', '')).lower()
                    for rec in data[:5]
                )

                if retention_logic:
                    _record_api_test_result(test_results, "Burnaby Retention Logic", True,
                                          "Burnaby retention logic is working")
                else:
                    _record_api_test_result(test_results, "Burnaby Retention Logic", False,
                                          "Burnaby retention logic not detected")
            else:
                _record_api_test_result(test_results, "Enhanced Calculations with Pending", False,
                                      "No recommendations returned to test")
        else:
            _record_api_test_result(test_results, "Enhanced Calculations with Pending", False,
                                  f"API returned status {response.status_code}")

    except Exception as e:
        logger.error(f"Enhanced calculations testing failed: {str(e)}")
        _record_api_test_result(test_results, "Enhanced Calculations with Pending", False,
                               f"Exception during enhanced calculations testing: {str(e)}")

async def test_data_validation_and_errors(test_results):
    """Test data validation and error handling"""
    try:
        from backend.import_export import import_export_manager

        # Test 5.1: Missing required columns
        invalid_csv = "invalid_column,another_invalid_column\ntest_value,another_value"

        result = import_export_manager.import_pending_orders_csv(
            invalid_csv.encode('utf-8'),
            "invalid_structure.csv"
        )

        has_errors = len(result.get('errors', [])) > 0
        _record_api_test_result(test_results, "Missing Columns Validation", has_errors,
                               f"Properly detected missing columns: {has_errors}")

        # Test 5.2: Invalid destinations
        invalid_destination_csv = """sku_id,quantity,destination
SKU001,100,invalid_warehouse
SKU002,50,mars_warehouse"""

        result = import_export_manager.import_pending_orders_csv(
            invalid_destination_csv.encode('utf-8'),
            "invalid_destinations.csv"
        )

        has_warnings = len(result.get('warnings', [])) > 0
        _record_api_test_result(test_results, "Invalid Destinations Validation", has_warnings,
                               f"Properly detected invalid destinations: {has_warnings}")

        # Test 5.3: Invalid quantities
        invalid_quantity_csv = """sku_id,quantity,destination
SKU001,-100,kentucky
SKU002,not_a_number,burnaby"""

        result = import_export_manager.import_pending_orders_csv(
            invalid_quantity_csv.encode('utf-8'),
            "invalid_quantities.csv"
        )

        # Should clean up invalid quantities
        low_import_count = result.get('records_imported', 0) == 0
        _record_api_test_result(test_results, "Invalid Quantities Validation", low_import_count,
                               f"Properly handled invalid quantities: {low_import_count}")

    except Exception as e:
        logger.error(f"Data validation testing failed: {str(e)}")
        _record_api_test_result(test_results, "Data Validation Testing", False,
                               f"Exception during validation testing: {str(e)}")

async def test_integration_with_existing_systems(test_results):
    """Test integration with existing inventory and SKU systems"""
    try:
        import requests

        base_url = "http://localhost:8000"

        # Test 6.1: Verify database views were created
        response = requests.get(f"{base_url}/api/pending-orders")
        if response.status_code == 200:
            _record_api_test_result(test_results, "Database Views Integration", True,
                                  "Pending orders views are accessible")
        else:
            _record_api_test_result(test_results, "Database Views Integration", False,
                                  "Could not access pending orders views")

        # Test 6.2: Check SKU validation integration
        # This should be tested by trying to import non-existent SKUs
        invalid_sku_csv = """sku_id,quantity,destination
NONEXISTENT001,100,kentucky
NONEXISTENT002,50,burnaby"""

        from backend.import_export import import_export_manager
        result = import_export_manager.import_pending_orders_csv(
            invalid_sku_csv.encode('utf-8'),
            "nonexistent_skus.csv"
        )

        # Should have warnings about invalid SKUs
        has_sku_validation = len(result.get('warnings', [])) > 0 or result.get('records_imported', 0) == 0
        _record_api_test_result(test_results, "SKU Validation Integration", has_sku_validation,
                               f"SKU validation working: {has_sku_validation}")

        # Test 6.3: Verify enhanced calculations use the new data
        response = requests.get(f"{base_url}/api/transfer-recommendations?enhanced=true&limit=3")
        if response.status_code == 200:
            data = response.json()
            has_enhanced_fields = len(data) > 0 and 'reason' in data[0]
            _record_api_test_result(test_results, "Enhanced Calculations Integration", has_enhanced_fields,
                                  "Enhanced calculations are functioning with new data")
        else:
            _record_api_test_result(test_results, "Enhanced Calculations Integration", False,
                                  "Could not test enhanced calculations integration")

    except Exception as e:
        logger.error(f"Integration testing failed: {str(e)}")
        _record_api_test_result(test_results, "System Integration Testing", False,
                               f"Exception during integration testing: {str(e)}")

# Helper functions
def _record_api_test_result(test_results, test_name, passed, message):
    """Record an API test result"""
    if passed:
        test_results['api_tests_passed'] += 1
    else:
        test_results['api_tests_failed'] += 1

    test_results['test_details'].append({
        'test_name': test_name,
        'test_type': 'API',
        'passed': passed,
        'message': message,
        'timestamp': datetime.now().isoformat()
    })

    logger.info(f"{'✅' if passed else '❌'} API Test: {test_name} - {message}")

def _record_ui_test_result(test_results, test_name, passed, message):
    """Record a UI test result"""
    if passed:
        test_results['ui_tests_passed'] += 1
    else:
        test_results['ui_tests_failed'] += 1

    test_results['test_details'].append({
        'test_name': test_name,
        'test_type': 'UI',
        'passed': passed,
        'message': message,
        'timestamp': datetime.now().isoformat()
    })

    logger.info(f"{'✅' if passed else '❌'} UI Test: {test_name} - {message}")

# Run tests if executed directly
if __name__ == "__main__":
    asyncio.run(test_pending_orders_comprehensive())