"""
Comprehensive Playwright tests for Enhanced Calculation Engine
Tests seasonal pattern detection, viral growth analysis, and enhanced transfer logic
"""
import asyncio
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def test_enhanced_calculation_engine():
    """
    Comprehensive test suite for the enhanced calculation engine
    """
    test_results = {
        'test_timestamp': datetime.now().isoformat(),
        'tests_passed': 0,
        'tests_failed': 0,
        'test_details': []
    }

    try:
        # Import the calculation modules
        import sys
        import os
        backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
        sys.path.insert(0, backend_path)

        from calculations import (
            StockoutCorrector, SeasonalPatternDetector, ViralGrowthDetector,
            TransferCalculator, test_enhanced_calculations,
            update_all_seasonal_and_growth_patterns
        )

        logger.info("Starting Enhanced Calculation Engine tests...")

        # Test 1: Database schema validation
        await test_database_schema(test_results)

        # Test 2: Year-over-year demand lookup
        await test_year_over_year_lookup(test_results)

        # Test 3: Category average fallback
        await test_category_average_fallback(test_results)

        # Test 4: Enhanced stockout correction
        await test_enhanced_stockout_correction(test_results)

        # Test 5: Seasonal pattern detection
        await test_seasonal_pattern_detection(test_results)

        # Test 6: Viral growth detection
        await test_viral_growth_detection(test_results)

        # Test 7: Enhanced transfer recommendations
        await test_enhanced_transfer_recommendations(test_results)

        # Test 8: Performance benchmarking
        await test_performance_benchmarks(test_results)

        # Test 9: Discontinued item consolidation
        await test_discontinued_consolidation(test_results)

        # Test 10: Integration testing with full dataset
        await test_integration_full_dataset(test_results)

        # Calculate final results
        total_tests = test_results['tests_passed'] + test_results['tests_failed']
        success_rate = (test_results['tests_passed'] / total_tests * 100) if total_tests > 0 else 0

        test_results['total_tests'] = total_tests
        test_results['success_rate'] = round(success_rate, 2)
        test_results['overall_status'] = 'PASSED' if test_results['tests_failed'] == 0 else 'FAILED'

        logger.info(f"Enhanced Calculation Engine tests completed: {test_results['tests_passed']}/{total_tests} passed ({success_rate:.1f}%)")

        return test_results

    except Exception as e:
        logger.error(f"Test suite failed with exception: {e}")
        test_results['fatal_error'] = str(e)
        test_results['overall_status'] = 'ERROR'
        return test_results


async def test_database_schema(test_results):
    """Test that required database schema changes are in place"""
    try:
        import database

        # Test 1.1: Check for new fields in skus table
        schema_query = """
        DESCRIBE skus
        """

        schema_result = database.execute_query(schema_query)
        schema_fields = [field['Field'] for field in schema_result]

        required_fields = ['seasonal_pattern', 'growth_status', 'last_stockout_date']
        missing_fields = [field for field in required_fields if field not in schema_fields]

        if not missing_fields:
            _record_test_result(test_results, "Database Schema Validation", True,
                              "All required fields present in skus table")
        else:
            _record_test_result(test_results, "Database Schema Validation", False,
                              f"Missing fields: {missing_fields}")

        # Test 1.2: Check for views
        views_query = """
        SHOW TABLES LIKE 'v_%'
        """

        views_result = database.execute_query(views_query)
        view_names = [view[f'Tables_in_warehouse_transfer (v_%)'] for view in views_result]

        required_views = ['v_year_over_year_sales', 'v_category_averages']
        missing_views = [view for view in required_views if view not in view_names]

        if not missing_views:
            _record_test_result(test_results, "Database Views Validation", True,
                              "All required views present")
        else:
            _record_test_result(test_results, "Database Views Validation", False,
                              f"Missing views: {missing_views}")

    except Exception as e:
        _record_test_result(test_results, "Database Schema Validation", False, f"Error: {e}")


async def test_year_over_year_lookup(test_results):
    """Test year-over-year demand lookup functionality"""
    try:
        corrector = StockoutCorrector()

        # Test with CHG-001 (should have historical data)
        yoy_result = corrector.get_same_month_last_year('CHG-001', '2024-03')

        if isinstance(yoy_result, (int, float)) and yoy_result >= 0:
            _record_test_result(test_results, "Year-over-Year Lookup", True,
                              f"Returned valid result: {yoy_result}")
        else:
            _record_test_result(test_results, "Year-over-Year Lookup", False,
                              f"Invalid result: {yoy_result}")

        # Test with non-existent SKU
        yoy_invalid = corrector.get_same_month_last_year('INVALID-SKU', '2024-03')

        if yoy_invalid == 0.0:
            _record_test_result(test_results, "Year-over-Year Invalid SKU", True,
                              "Correctly returned 0 for invalid SKU")
        else:
            _record_test_result(test_results, "Year-over-Year Invalid SKU", False,
                              f"Should return 0 for invalid SKU, got: {yoy_invalid}")

    except Exception as e:
        _record_test_result(test_results, "Year-over-Year Lookup", False, f"Exception: {e}")


async def test_category_average_fallback(test_results):
    """Test category average fallback functionality"""
    try:
        corrector = StockoutCorrector()

        # Test with CHG-001 (should have category 'Chargers')
        category_result = corrector.get_category_average('CHG-001')

        if isinstance(category_result, (int, float)) and category_result >= 0:
            _record_test_result(test_results, "Category Average Lookup", True,
                              f"Returned valid result: {category_result}")
        else:
            _record_test_result(test_results, "Category Average Lookup", False,
                              f"Invalid result: {category_result}")

        # Test with SKU without category
        category_invalid = corrector.get_category_average('INVALID-SKU')

        if category_invalid == 0.0:
            _record_test_result(test_results, "Category Average Invalid SKU", True,
                              "Correctly returned 0 for SKU without category")
        else:
            _record_test_result(test_results, "Category Average Invalid SKU", False,
                              f"Should return 0 for invalid SKU, got: {category_invalid}")

    except Exception as e:
        _record_test_result(test_results, "Category Average Lookup", False, f"Exception: {e}")


async def test_enhanced_stockout_correction(test_results):
    """Test enhanced stockout correction with zero sales"""
    try:
        corrector = StockoutCorrector()

        # Test enhanced correction with zero sales and high stockout days
        enhanced_result = corrector.correct_monthly_demand_enhanced('CHG-001', 0, 25, '2024-03')

        if enhanced_result > 0:
            _record_test_result(test_results, "Enhanced Stockout Correction", True,
                              f"Zero sales with 25 stockout days corrected to: {enhanced_result}")
        else:
            _record_test_result(test_results, "Enhanced Stockout Correction", False,
                              f"Expected positive correction, got: {enhanced_result}")

        # Test with normal sales
        normal_result = corrector.correct_monthly_demand_enhanced('CHG-001', 100, 5, '2024-03')

        if normal_result >= 100:
            _record_test_result(test_results, "Enhanced Normal Correction", True,
                              f"Normal sales corrected to: {normal_result}")
        else:
            _record_test_result(test_results, "Enhanced Normal Correction", False,
                              f"Expected >= 100, got: {normal_result}")

    except Exception as e:
        _record_test_result(test_results, "Enhanced Stockout Correction", False, f"Exception: {e}")


async def test_seasonal_pattern_detection(test_results):
    """Test seasonal pattern detection"""
    try:
        detector = SeasonalPatternDetector()

        # Test pattern detection
        pattern = detector.detect_seasonal_pattern('CHG-001')

        valid_patterns = ['spring_summer', 'fall_winter', 'holiday', 'year_round']
        if pattern in valid_patterns:
            _record_test_result(test_results, "Seasonal Pattern Detection", True,
                              f"Detected pattern: {pattern}")
        else:
            _record_test_result(test_results, "Seasonal Pattern Detection", False,
                              f"Invalid pattern: {pattern}")

        # Test seasonal multiplier
        multiplier = detector.get_seasonal_multiplier(pattern, 3)  # March

        if 0.5 <= multiplier <= 2.0:
            _record_test_result(test_results, "Seasonal Multiplier", True,
                              f"Valid multiplier for March: {multiplier}")
        else:
            _record_test_result(test_results, "Seasonal Multiplier", False,
                              f"Invalid multiplier: {multiplier}")

    except Exception as e:
        _record_test_result(test_results, "Seasonal Pattern Detection", False, f"Exception: {e}")


async def test_viral_growth_detection(test_results):
    """Test viral growth detection"""
    try:
        detector = ViralGrowthDetector()

        # Test growth detection
        growth_status = detector.detect_viral_growth('CHG-001')

        valid_statuses = ['viral', 'normal', 'declining']
        if growth_status in valid_statuses:
            _record_test_result(test_results, "Viral Growth Detection", True,
                              f"Detected growth status: {growth_status}")
        else:
            _record_test_result(test_results, "Viral Growth Detection", False,
                              f"Invalid growth status: {growth_status}")

        # Test growth multiplier
        multiplier = detector.get_growth_multiplier(growth_status)

        if 0.5 <= multiplier <= 2.0:
            _record_test_result(test_results, "Growth Multiplier", True,
                              f"Valid multiplier: {multiplier}")
        else:
            _record_test_result(test_results, "Growth Multiplier", False,
                              f"Invalid multiplier: {multiplier}")

    except Exception as e:
        _record_test_result(test_results, "Viral Growth Detection", False, f"Exception: {e}")


async def test_enhanced_transfer_recommendations(test_results):
    """Test enhanced transfer recommendation calculation"""
    try:
        calculator = TransferCalculator()

        sample_sku_data = {
            'sku_id': 'CHG-001',
            'description': 'USB-C Fast Charger 65W',
            'burnaby_qty': 500,
            'kentucky_qty': 0,
            'kentucky_sales': 0,
            'kentucky_stockout_days': 25,
            'abc_code': 'A',
            'xyz_code': 'X',
            'transfer_multiple': 25
        }

        # Test enhanced recommendation
        enhanced_rec = calculator.calculate_enhanced_transfer_recommendation(sample_sku_data)

        if enhanced_rec and 'enhanced_calculation' in enhanced_rec:
            _record_test_result(test_results, "Enhanced Transfer Recommendation", True,
                              f"Generated enhanced recommendation with transfer qty: {enhanced_rec.get('recommended_transfer_qty', 0)}")
        else:
            _record_test_result(test_results, "Enhanced Transfer Recommendation", False,
                              "Failed to generate enhanced recommendation")

        # Verify enhanced fields are present
        required_fields = ['seasonal_pattern', 'growth_status', 'seasonal_multiplier', 'growth_multiplier']
        missing_fields = [field for field in required_fields if field not in (enhanced_rec or {})]

        if not missing_fields:
            _record_test_result(test_results, "Enhanced Fields Validation", True,
                              "All enhanced fields present in recommendation")
        else:
            _record_test_result(test_results, "Enhanced Fields Validation", False,
                              f"Missing enhanced fields: {missing_fields}")

    except Exception as e:
        _record_test_result(test_results, "Enhanced Transfer Recommendations", False, f"Exception: {e}")


async def test_performance_benchmarks(test_results):
    """Test performance benchmarks for enhanced calculations"""
    try:
        from calculations import calculate_all_transfer_recommendations

        # Benchmark enhanced calculations
        start_time = datetime.now()
        enhanced_recs = calculate_all_transfer_recommendations(use_enhanced=True)
        enhanced_duration = (datetime.now() - start_time).total_seconds()

        # Benchmark basic calculations for comparison
        start_time = datetime.now()
        basic_recs = calculate_all_transfer_recommendations(use_enhanced=False)
        basic_duration = (datetime.now() - start_time).total_seconds()

        # Performance targets
        TARGET_RESPONSE_TIME = 5.0  # seconds

        if enhanced_duration <= TARGET_RESPONSE_TIME:
            _record_test_result(test_results, "Enhanced Performance Test", True,
                              f"Enhanced calculations completed in {enhanced_duration:.2f}s (target: {TARGET_RESPONSE_TIME}s)")
        else:
            _record_test_result(test_results, "Enhanced Performance Test", False,
                              f"Enhanced calculations took {enhanced_duration:.2f}s (target: {TARGET_RESPONSE_TIME}s)")

        # Compare counts
        if len(enhanced_recs) == len(basic_recs):
            _record_test_result(test_results, "Recommendation Count Consistency", True,
                              f"Both methods returned {len(enhanced_recs)} recommendations")
        else:
            _record_test_result(test_results, "Recommendation Count Consistency", False,
                              f"Enhanced: {len(enhanced_recs)}, Basic: {len(basic_recs)}")

    except Exception as e:
        _record_test_result(test_results, "Performance Benchmarks", False, f"Exception: {e}")


async def test_discontinued_consolidation(test_results):
    """Test discontinued item consolidation logic"""
    try:
        calculator = TransferCalculator()

        consolidation_recs = calculator.consolidate_discontinued_items()

        if isinstance(consolidation_recs, list):
            _record_test_result(test_results, "Discontinued Consolidation", True,
                              f"Generated {len(consolidation_recs)} consolidation recommendations")
        else:
            _record_test_result(test_results, "Discontinued Consolidation", False,
                              "Failed to generate consolidation recommendations")

        # Verify consolidation recommendation structure
        if consolidation_recs:
            sample_rec = consolidation_recs[0]
            required_fields = ['sku_id', 'consolidation_type', 'recommended_transfer_qty', 'reason']
            missing_fields = [field for field in required_fields if field not in sample_rec]

            if not missing_fields:
                _record_test_result(test_results, "Consolidation Structure", True,
                                  "Consolidation recommendations have correct structure")
            else:
                _record_test_result(test_results, "Consolidation Structure", False,
                                  f"Missing fields: {missing_fields}")

    except Exception as e:
        _record_test_result(test_results, "Discontinued Consolidation", False, f"Exception: {e}")


async def test_integration_full_dataset(test_results):
    """Test integration with full dataset and error handling"""
    try:
        from calculations import test_enhanced_calculations, update_all_seasonal_and_growth_patterns

        # Run the built-in test function
        test_results_internal = test_enhanced_calculations()

        if 'error' not in test_results_internal:
            _record_test_result(test_results, "Internal Test Suite", True,
                              "Built-in test suite completed successfully")
        else:
            _record_test_result(test_results, "Internal Test Suite", False,
                              f"Built-in test suite failed: {test_results_internal['error']}")

        # Test pattern update function
        pattern_update_result = update_all_seasonal_and_growth_patterns()

        if pattern_update_result:
            _record_test_result(test_results, "Pattern Update Function", True,
                              "Successfully updated patterns for all SKUs")
        else:
            _record_test_result(test_results, "Pattern Update Function", False,
                              "Pattern update function failed")

    except Exception as e:
        _record_test_result(test_results, "Integration Testing", False, f"Exception: {e}")


def _record_test_result(test_results, test_name, passed, details):
    """Helper function to record test results"""
    if passed:
        test_results['tests_passed'] += 1
        status = "PASSED"
    else:
        test_results['tests_failed'] += 1
        status = "FAILED"

    test_results['test_details'].append({
        'test_name': test_name,
        'status': status,
        'details': details,
        'timestamp': datetime.now().isoformat()
    })

    logger.info(f"Test '{test_name}': {status} - {details}")


async def run_playwright_integration_test():
    """
    Run the enhanced calculation tests with Playwright MCP integration
    This function can be called from Playwright MCP browser automation
    """
    try:
        logger.info("Starting Playwright MCP Enhanced Calculation Tests...")

        # Run the comprehensive test suite
        test_results = await test_enhanced_calculation_engine()

        # Generate test report
        test_report = generate_test_report(test_results)

        # Log summary
        logger.info(f"Test Suite Complete: {test_results.get('overall_status', 'UNKNOWN')}")
        logger.info(f"Tests Passed: {test_results.get('tests_passed', 0)}")
        logger.info(f"Tests Failed: {test_results.get('tests_failed', 0)}")
        logger.info(f"Success Rate: {test_results.get('success_rate', 0)}%")

        return {
            'status': test_results.get('overall_status', 'UNKNOWN'),
            'summary': f"{test_results.get('tests_passed', 0)}/{test_results.get('total_tests', 0)} passed",
            'success_rate': test_results.get('success_rate', 0),
            'test_results': test_results,
            'test_report': test_report
        }

    except Exception as e:
        logger.error(f"Playwright integration test failed: {e}")
        return {
            'status': 'ERROR',
            'error': str(e),
            'summary': 'Test suite failed with exception'
        }


def generate_test_report(test_results):
    """Generate a formatted test report"""

    report_lines = [
        "=" * 80,
        "ENHANCED CALCULATION ENGINE TEST REPORT",
        "=" * 80,
        f"Test Timestamp: {test_results.get('test_timestamp', 'Unknown')}",
        f"Overall Status: {test_results.get('overall_status', 'Unknown')}",
        f"Tests Passed: {test_results.get('tests_passed', 0)}",
        f"Tests Failed: {test_results.get('tests_failed', 0)}",
        f"Total Tests: {test_results.get('total_tests', 0)}",
        f"Success Rate: {test_results.get('success_rate', 0)}%",
        "",
        "DETAILED TEST RESULTS:",
        "-" * 40
    ]

    for test_detail in test_results.get('test_details', []):
        status_icon = "✓" if test_detail['status'] == 'PASSED' else "✗"
        report_lines.append(f"{status_icon} {test_detail['test_name']}: {test_detail['status']}")
        report_lines.append(f"   Details: {test_detail['details']}")
        report_lines.append("")

    if 'fatal_error' in test_results:
        report_lines.extend([
            "FATAL ERROR:",
            "-" * 20,
            test_results['fatal_error']
        ])

    report_lines.append("=" * 80)

    return "\n".join(report_lines)


if __name__ == "__main__":
    # Run tests directly if called as script
    asyncio.run(run_playwright_integration_test())