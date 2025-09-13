"""
Enhanced Transfer Logic Test Suite
Tests the new seasonal pre-positioning, detailed reasons, and priority scoring features
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from calculations import TransferCalculator
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_seasonal_pre_positioning():
    """
    Test seasonal pre-positioning logic for different scenarios
    """
    logger.info("=== Testing Seasonal Pre-positioning Logic ===")

    calculator = TransferCalculator()
    test_cases = [
        # Test case: [sku_id, seasonal_pattern, current_month, expected_needs_positioning, description]
        ("TEST-001", "holiday", 10, True, "October - should pre-position for November holiday peak"),
        ("TEST-002", "holiday", 9, True, "September - should pre-position for November holiday peak"),
        ("TEST-003", "holiday", 8, False, "August - too early for holiday positioning"),
        ("TEST-004", "spring_summer", 3, True, "March - should pre-position for April spring peak"),
        ("TEST-005", "fall_winter", 9, True, "September - should pre-position for October fall peak"),
        ("TEST-006", "year_round", 6, False, "Year-round pattern - no seasonal positioning needed"),
        ("TEST-007", "spring_summer", 7, False, "July - in the middle of spring/summer season"),
    ]

    passed_tests = 0
    total_tests = len(test_cases)

    for sku_id, pattern, month, expected_positioning, description in test_cases:
        try:
            result = calculator.get_seasonal_pre_positioning(sku_id, pattern, month)
            actual_positioning = result['needs_pre_positioning']

            if actual_positioning == expected_positioning:
                logger.info(f"✅ PASS: {description}")
                logger.info(f"   Result: {result['reason']}")
                passed_tests += 1
            else:
                logger.error(f"❌ FAIL: {description}")
                logger.error(f"   Expected: {expected_positioning}, Got: {actual_positioning}")
                logger.error(f"   Result: {result}")

        except Exception as e:
            logger.error(f"❌ ERROR in {description}: {e}")

    logger.info(f"Seasonal Pre-positioning Tests: {passed_tests}/{total_tests} passed")
    return passed_tests == total_tests


def test_detailed_transfer_reasons():
    """
    Test detailed transfer reason generation with various factor combinations
    """
    logger.info("\n=== Testing Detailed Transfer Reason Generation ===")

    calculator = TransferCalculator()
    test_scenarios = [
        {
            'name': "Critical out of stock with viral growth",
            'factors': {
                'kentucky_qty': 0,
                'stockout_days': 25,
                'growth_status': 'viral',
                'abc_class': 'A',
                'current_coverage': 0,
                'seasonal_info': {'needs_pre_positioning': False}
            },
            'expected_keywords': ['CRITICAL', 'out of stock', 'Severe stockout', 'viral', 'High-value']
        },
        {
            'name': "Seasonal pre-positioning for holiday items",
            'factors': {
                'kentucky_qty': 50,
                'stockout_days': 0,
                'growth_status': 'normal',
                'abc_class': 'B',
                'current_coverage': 2.5,
                'seasonal_info': {
                    'needs_pre_positioning': True,
                    'reason': 'Pre-position for Holiday season (peak in Nov)'
                }
            },
            'expected_keywords': ['Pre-position', 'Holiday', 'Nov']
        },
        {
            'name': "Declining product with moderate stockout",
            'factors': {
                'kentucky_qty': 25,
                'stockout_days': 12,
                'growth_status': 'declining',
                'abc_class': 'C',
                'current_coverage': 1.0,
                'seasonal_info': {'needs_pre_positioning': False}
            },
            'expected_keywords': ['Moderate stockout', 'declining', 'trend']
        },
        {
            'name': "Low coverage urgent situation",
            'factors': {
                'kentucky_qty': 10,
                'stockout_days': 5,
                'growth_status': 'normal',
                'abc_class': 'A',
                'current_coverage': 0.3,
                'target_coverage': 6.0,
                'seasonal_info': {'needs_pre_positioning': False}
            },
            'expected_keywords': ['URGENT', 'weeks coverage', 'Recent stockout', 'High-value', 'Below minimum']
        }
    ]

    passed_tests = 0
    total_tests = len(test_scenarios)

    for scenario in test_scenarios:
        try:
            reason = calculator.generate_detailed_transfer_reason(scenario['factors'])

            # Check if all expected keywords are present
            keywords_found = all(keyword.lower() in reason.lower() for keyword in scenario['expected_keywords'])

            if keywords_found:
                logger.info(f"✅ PASS: {scenario['name']}")
                logger.info(f"   Reason: {reason}")
                passed_tests += 1
            else:
                logger.error(f"❌ FAIL: {scenario['name']}")
                logger.error(f"   Expected keywords: {scenario['expected_keywords']}")
                logger.error(f"   Generated reason: {reason}")

        except Exception as e:
            logger.error(f"❌ ERROR in {scenario['name']}: {e}")

    logger.info(f"Detailed Transfer Reason Tests: {passed_tests}/{total_tests} passed")
    return passed_tests == total_tests


def test_priority_scoring():
    """
    Test priority scoring system with different SKU scenarios
    """
    logger.info("\n=== Testing Priority Scoring System ===")

    calculator = TransferCalculator()
    test_scenarios = [
        {
            'name': "Critical: Out of stock A-class viral item",
            'sku_data': {
                'sku_id': 'TEST-CRITICAL',
                'kentucky_stockout_days': 30,
                'kentucky_qty': 0,
                'corrected_demand': 100,
                'abc_code': 'A',
                'growth_status': 'viral'
            },
            'expected_priority': 'CRITICAL',
            'expected_score_range': (90, 100)
        },
        {
            'name': "High: Low stock B-class normal item",
            'sku_data': {
                'sku_id': 'TEST-HIGH',
                'kentucky_stockout_days': 15,
                'kentucky_qty': 25,
                'corrected_demand': 50,
                'abc_code': 'B',
                'growth_status': 'normal'
            },
            'expected_priority': 'HIGH',
            'expected_score_range': (60, 79)
        },
        {
            'name': "Medium: Moderate stock B-class declining item",
            'sku_data': {
                'sku_id': 'TEST-MEDIUM',
                'kentucky_stockout_days': 10,
                'kentucky_qty': 50,
                'corrected_demand': 40,
                'abc_code': 'B',
                'growth_status': 'declining'
            },
            'expected_priority': 'MEDIUM',
            'expected_score_range': (40, 59)
        },
        {
            'name': "Low: Well stocked C-class normal item",
            'sku_data': {
                'sku_id': 'TEST-LOW',
                'kentucky_stockout_days': 0,
                'kentucky_qty': 500,
                'corrected_demand': 50,
                'abc_code': 'C',
                'growth_status': 'normal'
            },
            'expected_priority': 'LOW',
            'expected_score_range': (0, 39)
        }
    ]

    passed_tests = 0
    total_tests = len(test_scenarios)

    for scenario in test_scenarios:
        try:
            result = calculator.calculate_priority_score(scenario['sku_data'])

            actual_priority = result['priority_level']
            actual_score = result['total_score']
            expected_priority = scenario['expected_priority']
            min_score, max_score = scenario['expected_score_range']

            priority_correct = actual_priority == expected_priority
            score_in_range = min_score <= actual_score <= max_score

            if priority_correct and score_in_range:
                logger.info(f"✅ PASS: {scenario['name']}")
                logger.info(f"   Priority: {actual_priority}, Score: {actual_score}")
                logger.info(f"   Score breakdown: {result['score_breakdown']}")
                passed_tests += 1
            else:
                logger.error(f"❌ FAIL: {scenario['name']}")
                logger.error(f"   Expected priority: {expected_priority}, Got: {actual_priority}")
                logger.error(f"   Expected score range: {min_score}-{max_score}, Got: {actual_score}")
                logger.error(f"   Full result: {result}")

        except Exception as e:
            logger.error(f"❌ ERROR in {scenario['name']}: {e}")

    logger.info(f"Priority Scoring Tests: {passed_tests}/{total_tests} passed")
    return passed_tests == total_tests


def test_enhanced_calculation_integration():
    """
    Test integration of all enhanced features in the main calculation flow
    """
    logger.info("\n=== Testing Enhanced Calculation Integration ===")

    calculator = TransferCalculator()

    # Test data that should trigger multiple enhanced features
    test_sku_data = {
        'sku_id': 'TEST-INTEGRATION',
        'description': 'Test Integration SKU',
        'burnaby_qty': 1000,
        'kentucky_qty': 0,  # Out of stock
        'kentucky_sales': 0,  # Zero sales due to stockout
        'kentucky_stockout_days': 25,  # Severe stockout
        'abc_code': 'A',  # High value
        'xyz_code': 'X',  # Stable demand
        'transfer_multiple': 50
    }

    try:
        # Test with enhanced mode
        enhanced_result = calculator.calculate_enhanced_transfer_recommendation(test_sku_data)

        if enhanced_result:
            logger.info("✅ Enhanced calculation completed successfully")
            logger.info(f"   SKU: {enhanced_result['sku_id']}")
            logger.info(f"   Priority: {enhanced_result['priority']}")
            logger.info(f"   Transfer Qty: {enhanced_result['recommended_transfer_qty']}")
            logger.info(f"   Reason: {enhanced_result['reason']}")

            # Check if enhanced features are present
            has_seasonal = 'seasonal_positioning' in enhanced_result
            has_priority_analysis = 'priority_analysis' in enhanced_result
            has_enhanced_reason = len(enhanced_result['reason']) > 50  # Detailed reasons are longer

            if has_seasonal and has_priority_analysis and has_enhanced_reason:
                logger.info("✅ All enhanced features integrated successfully")
                return True
            else:
                logger.error("❌ Some enhanced features missing from result")
                logger.error(f"   Has seasonal positioning: {has_seasonal}")
                logger.error(f"   Has priority analysis: {has_priority_analysis}")
                logger.error(f"   Has enhanced reason: {has_enhanced_reason}")
                return False
        else:
            logger.error("❌ Enhanced calculation returned None")
            return False

    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return False


def test_performance_with_enhanced_features():
    """
    Test performance of enhanced calculations with multiple SKUs
    """
    logger.info("\n=== Testing Performance with Enhanced Features ===")

    calculator = TransferCalculator()

    # Create test data for multiple SKUs
    test_skus = []
    for i in range(100):  # Test with 100 SKUs
        sku_data = {
            'sku_id': f'PERF-{i:03d}',
            'description': f'Performance Test SKU {i}',
            'burnaby_qty': 500 + (i * 10),
            'kentucky_qty': i * 5,
            'kentucky_sales': max(0, i * 2 - 50),
            'kentucky_stockout_days': min(30, max(0, (100-i) // 10)),
            'abc_code': ['A', 'B', 'C'][i % 3],
            'xyz_code': ['X', 'Y', 'Z'][i % 3],
            'transfer_multiple': 25
        }
        test_skus.append(sku_data)

    try:
        start_time = datetime.now()

        successful_calculations = 0
        for sku_data in test_skus:
            result = calculator.calculate_enhanced_transfer_recommendation(sku_data)
            if result:
                successful_calculations += 1

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"✅ Performance test completed")
        logger.info(f"   Processed: {successful_calculations}/{len(test_skus)} SKUs")
        logger.info(f"   Duration: {duration:.2f} seconds")
        logger.info(f"   Average per SKU: {duration/len(test_skus)*1000:.1f} ms")

        # Performance target: should process 100 SKUs in under 5 seconds
        performance_target_met = duration < 5.0
        success_rate_met = successful_calculations >= len(test_skus) * 0.95  # 95% success rate

        if performance_target_met and success_rate_met:
            logger.info("✅ Performance targets met")
            return True
        else:
            logger.error("❌ Performance targets not met")
            logger.error(f"   Target duration: <5.0s, Actual: {duration:.2f}s")
            logger.error(f"   Target success rate: >=95%, Actual: {successful_calculations/len(test_skus)*100:.1f}%")
            return False

    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
        return False


def run_all_tests():
    """
    Run the complete Enhanced Transfer Logic test suite
    """
    logger.info("🚀 Starting Enhanced Transfer Logic Test Suite")
    logger.info("=" * 60)

    tests = [
        ("Seasonal Pre-positioning", test_seasonal_pre_positioning),
        ("Detailed Transfer Reasons", test_detailed_transfer_reasons),
        ("Priority Scoring System", test_priority_scoring),
        ("Enhanced Calculation Integration", test_enhanced_calculation_integration),
        ("Performance Testing", test_performance_with_enhanced_features)
    ]

    passed_tests = 0
    total_tests = len(tests)

    for test_name, test_function in tests:
        logger.info(f"\n📋 Running {test_name}...")
        try:
            if test_function():
                passed_tests += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} ERROR: {e}")

    logger.info("\n" + "=" * 60)
    logger.info(f"🏁 Test Suite Complete: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        logger.info("🎉 ALL TESTS PASSED - Enhanced Transfer Logic is ready for production!")
        return True
    else:
        logger.error(f"⚠️  {total_tests - passed_tests} tests failed - Review and fix issues before deployment")
        return False


if __name__ == "__main__":
    # Run the test suite
    success = run_all_tests()

    # Exit with appropriate code
    exit(0 if success else 1)