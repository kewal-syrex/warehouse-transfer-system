#!/usr/bin/env python3
"""
Create test Excel files for import functionality testing
"""
import pandas as pd
import os

# Create test_data directory if it doesn't exist
test_dir = "test_data"
if not os.path.exists(test_dir):
    os.makedirs(test_dir)

# Test 1: Burnaby-only inventory import
burnaby_only_data = {
    'sku_id': ['CHG-001', 'GAD-004', 'WDG-003'],
    'burnaby_qty': [100, 50, 75]
}
df1 = pd.DataFrame(burnaby_only_data)
df1.to_excel(f'{test_dir}/inventory_burnaby_only.xlsx', index=False)
print("Created: inventory_burnaby_only.xlsx")

# Test 2: Kentucky-only inventory import
kentucky_only_data = {
    'sku_id': ['CHG-001', 'GAD-004', 'WDG-003'],
    'kentucky_qty': [200, 75, 125]
}
df2 = pd.DataFrame(kentucky_only_data)
df2.to_excel(f'{test_dir}/inventory_kentucky_only.xlsx', index=False)
print("Created: inventory_kentucky_only.xlsx")

# Test 3: Mixed inventory import (both warehouses)
mixed_inventory_data = {
    'sku_id': ['CHG-001', 'GAD-004', 'WDG-003'],
    'burnaby_qty': [150, 60, 80],
    'kentucky_qty': [250, 90, 140]
}
df3 = pd.DataFrame(mixed_inventory_data)
df3.to_excel(f'{test_dir}/inventory_mixed.xlsx', index=False)
print("Created: inventory_mixed.xlsx")

# Test 4: Case-insensitive column detection
case_insensitive_data = {
    'SKU_ID': ['CHG-001', 'GAD-004'],
    'Burnaby_Qty': [111, 222],
    'KENTUCKY_QTY': [333, 444]
}
df4 = pd.DataFrame(case_insensitive_data)
df4.to_excel(f'{test_dir}/inventory_case_insensitive.xlsx', index=False)
print("Created: inventory_case_insensitive.xlsx")

# Test 5: Sales data with stockout days
sales_data = {
    'sku_id': ['CHG-001', 'GAD-004', 'WDG-003'],
    'year_month': ['2024-03', '2024-03', '2024-03'],
    'burnaby_sales': [100, 80, 120],
    'kentucky_sales': [150, 90, 180],
    'burnaby_stockout_days': [2, 0, 3],
    'kentucky_stockout_days': [5, 1, 7]
}
df5 = pd.DataFrame(sales_data)
df5.to_excel(f'{test_dir}/sales_with_stockouts.xlsx', index=False)
print("Created: sales_with_stockouts.xlsx")

# Test 6: Sales data with missing burnaby stockout days
sales_partial_data = {
    'sku_id': ['CHG-001', 'GAD-004'],
    'year_month': ['2024-04', '2024-04'],
    'burnaby_sales': [110, 85],
    'kentucky_sales': [160, 95],
    'kentucky_stockout_days': [3, 2]
    # Missing burnaby_stockout_days column
}
df6 = pd.DataFrame(sales_partial_data)
df6.to_excel(f'{test_dir}/sales_partial_stockouts.xlsx', index=False)
print("Created: sales_partial_stockouts.xlsx")

# Test 7: Sales data with invalid stockout days
sales_invalid_data = {
    'sku_id': ['CHG-001', 'GAD-004'],
    'year_month': ['2024-05', '2024-05'],
    'burnaby_sales': [120, 90],
    'kentucky_sales': [170, 100],
    'burnaby_stockout_days': [35, -5],  # Invalid: should be 0-31
    'kentucky_stockout_days': [4, 1]
}
df7 = pd.DataFrame(sales_invalid_data)
df7.to_excel(f'{test_dir}/sales_invalid_stockouts.xlsx', index=False)
print("Created: sales_invalid_stockouts.xlsx")

# Test 8: SKU data with category
sku_with_category_data = {
    'sku_id': ['TEST-001', 'TEST-002'],
    'description': ['Test Product 1', 'Test Product 2'],
    'supplier': ['Test Supplier A', 'Test Supplier B'],
    'cost_per_unit': [10.99, 15.50],
    'category': ['Electronics', 'Office Supplies']
}
df8 = pd.DataFrame(sku_with_category_data)
df8.to_excel(f'{test_dir}/sku_with_category.xlsx', index=False)
print("Created: sku_with_category.xlsx")

# Test 9: SKU data without category (minimal required)
sku_minimal_data = {
    'sku_id': ['TEST-003', 'TEST-004'],
    'description': ['Test Product 3', 'Test Product 4'],
    'supplier': ['Test Supplier C', 'Test Supplier D'],
    'cost_per_unit': [20.00, 25.99]
}
df9 = pd.DataFrame(sku_minimal_data)
df9.to_excel(f'{test_dir}/sku_minimal.xlsx', index=False)
print("Created: sku_minimal.xlsx")

# Test 10: SKU data with all optional fields
sku_full_data = {
    'sku_id': ['TEST-005', 'TEST-006'],
    'description': ['Test Product 5', 'Test Product 6'],
    'supplier': ['Test Supplier E', 'Test Supplier F'],
    'cost_per_unit': [12.75, 18.25],
    'category': ['Tools', 'Home & Garden'],
    'status': ['Active', 'Death Row'],
    'transfer_multiple': [25, 100],
    'abc_code': ['A', 'B'],
    'xyz_code': ['X', 'Y']
}
df10 = pd.DataFrame(sku_full_data)
df10.to_excel(f'{test_dir}/sku_full_optional.xlsx', index=False)
print("Created: sku_full_optional.xlsx")

# Test 11: SKU data with case-insensitive category detection
sku_case_insensitive_data = {
    'sku_id': ['TEST-007', 'TEST-008'],
    'description': ['Test Product 7', 'Test Product 8'],
    'supplier': ['Test Supplier G', 'Test Supplier H'],
    'cost_per_unit': [30.00, 35.50],
    'Category': ['Automotive', 'Sports'],  # Mixed case
    'STATUS': ['Active', 'Active'],
    'Transfer_Multiple': [75, 50]
}
df11 = pd.DataFrame(sku_case_insensitive_data)
df11.to_excel(f'{test_dir}/sku_case_insensitive.xlsx', index=False)
print("Created: sku_case_insensitive.xlsx")

print(f"\n✅ All test data files created in '{test_dir}' directory!")
print(f"Total files: {len([f for f in os.listdir(test_dir) if f.endswith('.xlsx')])}")