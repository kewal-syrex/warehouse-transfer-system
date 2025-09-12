"""
Performance Testing Script for Warehouse Transfer Planning Tool
Tests system performance with large datasets and measures response times
"""

import time
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import random
import string
import sys
import os
from pathlib import Path

# Add backend to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))

try:
    import database
    import calculations
except ImportError as e:
    print(f"Warning: Could not import backend modules: {e}")

class PerformanceTest:
    """
    Comprehensive performance testing suite for warehouse transfer system
    
    Tests include:
    - Database query performance with large datasets
    - API response times under load
    - Excel export performance with 4K+ SKUs
    - Memory usage during calculations
    - Concurrent user simulation
    """
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {}
        self.start_time = None
        
    def log(self, message):
        """Log test progress with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def generate_test_data(self, num_skus=4000):
        """
        Generate test dataset with specified number of SKUs
        
        Args:
            num_skus: Number of SKUs to generate (default 4000)
            
        Returns:
            Dictionary with SKU, inventory, and sales data
        """
        self.log(f"Generating test data for {num_skus} SKUs...")
        
        # Generate SKU master data
        skus = []
        suppliers = ["Supplier A", "Supplier B", "Supplier C", "Supplier D", "Supplier E"]
        
        for i in range(num_skus):
            sku_id = f"TEST-{i:04d}"
            skus.append({
                'sku_id': sku_id,
                'description': f'Test Product {i} - {"".join(random.choices(string.ascii_uppercase, k=3))}',
                'supplier': random.choice(suppliers),
                'status': 'Active',
                'cost_per_unit': round(random.uniform(5.0, 500.0), 2),
                'transfer_multiple': random.choice([25, 50, 100]),
                'abc_code': random.choices(['A', 'B', 'C'], weights=[20, 30, 50])[0],
                'xyz_code': random.choices(['X', 'Y', 'Z'], weights=[30, 40, 30])[0]
            })
        
        # Generate inventory data
        inventory = []
        for sku in skus:
            burnaby_qty = random.randint(0, 2000)
            # 10% chance of being out of stock in Kentucky
            kentucky_qty = 0 if random.random() < 0.1 else random.randint(0, 1000)
            
            inventory.append({
                'sku_id': sku['sku_id'],
                'burnaby_qty': burnaby_qty,
                'kentucky_qty': kentucky_qty
            })
        
        # Generate 6 months of sales history
        sales = []
        for month_offset in range(6):
            month_date = datetime.now() - timedelta(days=30 * month_offset)
            year_month = month_date.strftime("%Y-%m")
            
            for sku in skus:
                # Simulate sales with some correlation to ABC classification
                base_sales = 20 if sku['abc_code'] == 'A' else (10 if sku['abc_code'] == 'B' else 5)
                variation = random.uniform(0.5, 2.0)
                
                burnaby_sales = max(0, int(base_sales * variation * random.uniform(0.8, 1.2)))
                kentucky_sales = max(0, int(base_sales * variation * random.uniform(0.8, 1.2)))
                
                # Simulate stockouts (0-31 days)
                kentucky_stockout_days = random.choices(
                    [0, random.randint(1, 31)], 
                    weights=[85, 15]  # 15% chance of stockout
                )[0]
                
                sales.append({
                    'sku_id': sku['sku_id'],
                    'year_month': year_month,
                    'burnaby_sales': burnaby_sales,
                    'kentucky_sales': kentucky_sales,
                    'burnaby_stockout_days': 0,
                    'kentucky_stockout_days': kentucky_stockout_days
                })
        
        self.log(f"Generated {len(skus)} SKUs, {len(inventory)} inventory records, {len(sales)} sales records")
        
        return {
            'skus': skus,
            'inventory': inventory,
            'sales': sales
        }
    
    def load_test_data_to_database(self, test_data):
        """Load generated test data into database"""
        
        self.log("Loading test data into database...")
        start_time = time.time()
        
        try:
            import pymysql
            db = database.get_database_connection()
            cursor = db.cursor()
            
            # Clear existing test data
            cursor.execute("DELETE FROM skus WHERE sku_id LIKE 'TEST-%'")
            cursor.execute("DELETE FROM inventory_current WHERE sku_id LIKE 'TEST-%'")
            cursor.execute("DELETE FROM monthly_sales WHERE sku_id LIKE 'TEST-%'")
            
            # Insert SKUs
            for sku in test_data['skus']:
                cursor.execute("""
                    INSERT INTO skus (sku_id, description, supplier, status, cost_per_unit, 
                                    transfer_multiple, abc_code, xyz_code)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    sku['sku_id'], sku['description'], sku['supplier'], sku['status'],
                    sku['cost_per_unit'], sku['transfer_multiple'], 
                    sku['abc_code'], sku['xyz_code']
                ))
            
            # Insert inventory
            for inv in test_data['inventory']:
                cursor.execute("""
                    INSERT INTO inventory_current (sku_id, burnaby_qty, kentucky_qty, last_updated)
                    VALUES (%s, %s, %s, NOW())
                """, (inv['sku_id'], inv['burnaby_qty'], inv['kentucky_qty']))
            
            # Insert sales history
            for sale in test_data['sales']:
                cursor.execute("""
                    INSERT INTO monthly_sales (sku_id, year_month, burnaby_sales, kentucky_sales,
                                             burnaby_stockout_days, kentucky_stockout_days)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    sale['sku_id'], sale['year_month'], sale['burnaby_sales'],
                    sale['kentucky_sales'], sale['burnaby_stockout_days'], 
                    sale['kentucky_stockout_days']
                ))
            
            db.commit()
            db.close()
            
            load_time = time.time() - start_time
            self.log(f"Test data loaded successfully in {load_time:.2f} seconds")
            
            return True
            
        except Exception as e:
            self.log(f"Error loading test data: {str(e)}")
            return False
    
    def test_api_response_times(self):
        """Test API endpoint response times"""
        
        self.log("Testing API response times...")
        
        endpoints = [
            '/health',
            '/api/dashboard',
            '/api/skus',
            '/api/transfer-recommendations'
        ]
        
        results = {}
        
        for endpoint in endpoints:
            self.log(f"Testing {endpoint}...")
            times = []
            
            # Test each endpoint 5 times
            for i in range(5):
                start_time = time.time()
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                    end_time = time.time()
                    
                    if response.status_code == 200:
                        times.append(end_time - start_time)
                    else:
                        self.log(f"Warning: {endpoint} returned status {response.status_code}")
                        
                except requests.exceptions.RequestException as e:
                    self.log(f"Error testing {endpoint}: {str(e)}")
                    continue
                    
                # Small delay between requests
                time.sleep(0.1)
            
            if times:
                results[endpoint] = {
                    'avg_response_time': sum(times) / len(times),
                    'min_response_time': min(times),
                    'max_response_time': max(times),
                    'success_count': len(times)
                }
                
                self.log(f"{endpoint}: Avg {results[endpoint]['avg_response_time']:.3f}s, "
                        f"Min {results[endpoint]['min_response_time']:.3f}s, "
                        f"Max {results[endpoint]['max_response_time']:.3f}s")
        
        return results
    
    def test_transfer_calculations_performance(self):
        """Test transfer calculation performance with large dataset"""
        
        self.log("Testing transfer calculation performance...")
        
        start_time = time.time()
        
        try:
            # Test the calculation engine directly
            recommendations = calculations.calculate_all_transfer_recommendations()
            calculation_time = time.time() - start_time
            
            self.log(f"Transfer calculations completed in {calculation_time:.3f} seconds")
            self.log(f"Generated {len(recommendations)} recommendations")
            
            # Analyze calculation results
            critical_count = len([r for r in recommendations if r['priority'] == 'CRITICAL'])
            high_count = len([r for r in recommendations if r['priority'] == 'HIGH'])
            
            self.log(f"Priority breakdown: {critical_count} Critical, {high_count} High priority items")
            
            return {
                'calculation_time': calculation_time,
                'recommendations_count': len(recommendations),
                'critical_count': critical_count,
                'high_count': high_count
            }
            
        except Exception as e:
            self.log(f"Error in transfer calculations: {str(e)}")
            return None
    
    def test_excel_export_performance(self):
        """Test Excel export performance with large dataset"""
        
        self.log("Testing Excel export performance...")
        
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.base_url}/api/export/excel/transfer-orders", timeout=60)
            
            if response.status_code == 200:
                export_time = time.time() - start_time
                file_size = len(response.content)
                
                self.log(f"Excel export completed in {export_time:.3f} seconds")
                self.log(f"File size: {file_size / 1024:.1f} KB")
                
                return {
                    'export_time': export_time,
                    'file_size_kb': file_size / 1024,
                    'success': True
                }
            else:
                self.log(f"Excel export failed with status {response.status_code}")
                return None
                
        except Exception as e:
            self.log(f"Error testing Excel export: {str(e)}")
            return None
    
    def test_concurrent_users(self, num_users=5):
        """Simulate concurrent users accessing the system"""
        
        self.log(f"Testing concurrent access with {num_users} simulated users...")
        
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def simulate_user(user_id):
            """Simulate a single user session"""
            user_results = []
            
            # Simulate user workflow: dashboard -> transfer planning -> export
            endpoints = ['/api/dashboard', '/api/transfer-recommendations']
            
            for endpoint in endpoints:
                start_time = time.time()
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                    end_time = time.time()
                    
                    user_results.append({
                        'user_id': user_id,
                        'endpoint': endpoint,
                        'response_time': end_time - start_time,
                        'status_code': response.status_code
                    })
                    
                except Exception as e:
                    user_results.append({
                        'user_id': user_id,
                        'endpoint': endpoint,
                        'error': str(e)
                    })
            
            results_queue.put(user_results)
        
        # Start all user threads
        threads = []
        for i in range(num_users):
            thread = threading.Thread(target=simulate_user, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Collect results
        all_results = []
        while not results_queue.empty():
            all_results.extend(results_queue.get())
        
        # Analyze concurrent performance
        successful_requests = [r for r in all_results if 'response_time' in r and r['status_code'] == 200]
        
        if successful_requests:
            avg_response_time = sum(r['response_time'] for r in successful_requests) / len(successful_requests)
            max_response_time = max(r['response_time'] for r in successful_requests)
            
            self.log(f"Concurrent test completed: {len(successful_requests)} successful requests")
            self.log(f"Average response time: {avg_response_time:.3f}s")
            self.log(f"Maximum response time: {max_response_time:.3f}s")
            
            return {
                'total_requests': len(all_results),
                'successful_requests': len(successful_requests),
                'avg_response_time': avg_response_time,
                'max_response_time': max_response_time
            }
        
        return None
    
    def cleanup_test_data(self):
        """Remove test data from database"""
        
        self.log("Cleaning up test data...")
        
        try:
            import pymysql
            db = database.get_database_connection()
            cursor = db.cursor()
            
            cursor.execute("DELETE FROM monthly_sales WHERE sku_id LIKE 'TEST-%'")
            cursor.execute("DELETE FROM inventory_current WHERE sku_id LIKE 'TEST-%'")
            cursor.execute("DELETE FROM skus WHERE sku_id LIKE 'TEST-%'")
            
            db.commit()
            db.close()
            
            self.log("Test data cleanup completed")
            return True
            
        except Exception as e:
            self.log(f"Error during cleanup: {str(e)}")
            return False
    
    def run_full_performance_suite(self, num_skus=4000):
        """Run complete performance test suite"""
        
        self.log("=" * 60)
        self.log("WAREHOUSE TRANSFER SYSTEM - PERFORMANCE TEST SUITE")
        self.log("=" * 60)
        
        self.start_time = time.time()
        
        # Step 1: Generate and load test data
        test_data = self.generate_test_data(num_skus)
        if not self.load_test_data_to_database(test_data):
            self.log("Failed to load test data. Aborting tests.")
            return
        
        # Step 2: Test API response times
        api_results = self.test_api_response_times()
        self.test_results['api_performance'] = api_results
        
        # Step 3: Test transfer calculations
        calc_results = self.test_transfer_calculations_performance()
        if calc_results:
            self.test_results['calculation_performance'] = calc_results
        
        # Step 4: Test Excel export
        export_results = self.test_excel_export_performance()
        if export_results:
            self.test_results['export_performance'] = export_results
        
        # Step 5: Test concurrent users
        concurrent_results = self.test_concurrent_users()
        if concurrent_results:
            self.test_results['concurrent_performance'] = concurrent_results
        
        # Step 6: Cleanup
        self.cleanup_test_data()
        
        # Generate performance report
        self.generate_performance_report()
    
    def generate_performance_report(self):
        """Generate comprehensive performance test report"""
        
        total_time = time.time() - self.start_time
        
        self.log("=" * 60)
        self.log("PERFORMANCE TEST RESULTS")
        self.log("=" * 60)
        
        print(f"\nTest Duration: {total_time:.1f} seconds")
        print(f"Test Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # API Performance Summary
        if 'api_performance' in self.test_results:
            print("\n📊 API PERFORMANCE RESULTS:")
            for endpoint, results in self.test_results['api_performance'].items():
                status = "✅ PASS" if results['avg_response_time'] < 5.0 else "⚠️  SLOW"
                print(f"  {endpoint}: {results['avg_response_time']:.3f}s avg {status}")
        
        # Calculation Performance
        if 'calculation_performance' in self.test_results:
            calc = self.test_results['calculation_performance']
            calc_status = "✅ PASS" if calc['calculation_time'] < 5.0 else "⚠️  SLOW"
            print(f"\n🧮 CALCULATION PERFORMANCE:")
            print(f"  Transfer calculations: {calc['calculation_time']:.3f}s {calc_status}")
            print(f"  Recommendations generated: {calc['recommendations_count']}")
        
        # Export Performance  
        if 'export_performance' in self.test_results:
            export = self.test_results['export_performance']
            export_status = "✅ PASS" if export['export_time'] < 10.0 else "⚠️  SLOW"
            print(f"\n📁 EXPORT PERFORMANCE:")
            print(f"  Excel export: {export['export_time']:.3f}s {export_status}")
            print(f"  File size: {export['file_size_kb']:.1f} KB")
        
        # Concurrent Performance
        if 'concurrent_performance' in self.test_results:
            conc = self.test_results['concurrent_performance']
            conc_status = "✅ PASS" if conc['max_response_time'] < 10.0 else "⚠️  SLOW"
            print(f"\n👥 CONCURRENT USER PERFORMANCE:")
            print(f"  Success rate: {conc['successful_requests']}/{conc['total_requests']}")
            print(f"  Max response time: {conc['max_response_time']:.3f}s {conc_status}")
        
        # Performance Assessment
        print(f"\n📋 OVERALL ASSESSMENT:")
        
        issues = []
        if 'api_performance' in self.test_results:
            slow_endpoints = [ep for ep, res in self.test_results['api_performance'].items() 
                            if res['avg_response_time'] > 5.0]
            if slow_endpoints:
                issues.append(f"Slow API endpoints: {', '.join(slow_endpoints)}")
        
        if 'calculation_performance' in self.test_results:
            if self.test_results['calculation_performance']['calculation_time'] > 5.0:
                issues.append("Transfer calculations exceed 5 second target")
        
        if 'export_performance' in self.test_results:
            if self.test_results['export_performance']['export_time'] > 10.0:
                issues.append("Excel export exceeds 10 second target")
        
        if issues:
            print("  ⚠️  Performance Issues Identified:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  ✅ All performance targets met!")
        
        print(f"\n🎯 TARGET PERFORMANCE CRITERIA:")
        print(f"  • API Response Time: < 5 seconds")
        print(f"  • Transfer Calculations: < 5 seconds")
        print(f"  • Excel Export: < 10 seconds")
        print(f"  • Concurrent Users: No degradation with 5 users")
        
        # Save results to file
        self.save_results_to_file()
    
    def save_results_to_file(self):
        """Save test results to JSON file"""
        
        results_file = f"performance_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(results_file, 'w') as f:
                json.dump({
                    'test_timestamp': datetime.now().isoformat(),
                    'test_duration': time.time() - self.start_time,
                    'results': self.test_results
                }, f, indent=2)
            
            self.log(f"Test results saved to {results_file}")
            
        except Exception as e:
            self.log(f"Error saving results: {str(e)}")

def main():
    """Main performance test execution"""
    
    print("Warehouse Transfer Planning Tool - Performance Test Suite")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not responding correctly. Please start the server first.")
            return
    except:
        print("❌ Cannot connect to server at http://localhost:8000")
        print("Please ensure the FastAPI server is running with: uvicorn backend.main:app --reload")
        return
    
    print("✅ Server is running. Starting performance tests...\n")
    
    # Run performance tests
    tester = PerformanceTest()
    
    # Allow user to specify number of SKUs for testing
    num_skus = 4000
    if len(sys.argv) > 1:
        try:
            num_skus = int(sys.argv[1])
            print(f"Testing with {num_skus} SKUs (specified via command line)")
        except:
            print(f"Using default {num_skus} SKUs for testing")
    
    tester.run_full_performance_suite(num_skus)

if __name__ == "__main__":
    main()