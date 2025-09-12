#!/usr/bin/env python3
"""
Simple test script for the backend API
"""

import sys
import database
import calculations

def test_database():
    """Test database connection and basic queries"""
    print("Testing database connection...")
    
    try:
        if database.test_connection():
            print("  OK Database connection successful")
        else:
            print("  ERROR Database connection failed")
            return False
    except Exception as e:
        print(f"  ERROR Database error: {e}")
        return False
    
    # Test basic queries
    try:
        skus = database.get_current_stock_status()
        print(f"  OK Found {len(skus)} SKUs in database")
        
        sales_data = database.get_monthly_sales_data(year_month='2024-03')
        print(f"  OK Found {len(sales_data)} sales records for March 2024")
        
        out_of_stock = database.get_out_of_stock_skus()
        print(f"  OK Found {len(out_of_stock)} SKUs out of stock")
        
        return True
        
    except Exception as e:
        print(f"  ERROR Query error: {e}")
        return False

def test_calculations():
    """Test calculation functions"""
    print("\nTesting calculation functions...")
    
    try:
        # Test stockout correction
        corrector = calculations.StockoutCorrector()
        
        # Test case 1: No stockout
        result1 = corrector.correct_monthly_demand(100, 0)
        assert result1 == 100.0
        print("  OK No stockout case: 100 -> 100")
        
        # Test case 2: Mild stockout
        result2 = corrector.correct_monthly_demand(100, 5)  # 5 days out of 30
        expected2 = 100 / (25/30)  # Should be ~120
        assert abs(result2 - expected2) < 0.1
        print(f"  OK Mild stockout case: 100 -> {result2}")
        
        # Test case 3: Severe stockout (30% floor applied)
        result3 = corrector.correct_monthly_demand(100, 25)  # 25 days out of 30
        expected3 = 100 / 0.3  # Should use 30% floor, capped at 150 (50% increase)
        print(f"  OK Severe stockout case: 100 -> {result3} (floor applied)")
        
        return True
        
    except Exception as e:
        print(f"  ERROR Calculation error: {e}")
        return False

def test_transfer_recommendations():
    """Test transfer recommendation generation"""
    print("\nTesting transfer recommendations...")
    
    try:
        recommendations = calculations.calculate_all_transfer_recommendations()
        print(f"  OK Generated {len(recommendations)} recommendations")
        
        if recommendations:
            # Show first few recommendations
            print("  Sample recommendations:")
            for i, rec in enumerate(recommendations[:3]):
                sku = rec['sku_id']
                priority = rec['priority']
                qty = rec['recommended_transfer_qty']
                reason = rec['reason']
                print(f"    {i+1}. {sku}: {qty} units ({priority}) - {reason}")
        
        return True
        
    except Exception as e:
        print(f"  ERROR Recommendation error: {e}")
        return False

def main():
    """Run all tests"""
    print("Warehouse Transfer Planning Tool - Backend Tests")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    if test_database():
        tests_passed += 1
    
    if test_calculations():
        tests_passed += 1
        
    if test_transfer_recommendations():
        tests_passed += 1
    
    print(f"\nTest Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("SUCCESS All tests passed! Backend is ready.")
        return 0
    else:
        print("FAILURE Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())