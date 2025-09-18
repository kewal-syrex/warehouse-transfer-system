#!/usr/bin/env python3
"""
Check the monthly demand for UB-YTX14-BS to understand Burnaby retention
"""

import sys
sys.path.append('backend')
import database
import pymysql

db = database.get_database_connection()
cursor = db.cursor(pymysql.cursors.DictCursor)

# Get the sales data for UB-YTX14-BS
query = """
SELECT `year_month`, burnaby_sales, kentucky_sales,
       corrected_demand_burnaby, corrected_demand_kentucky
FROM monthly_sales
WHERE sku_id = %s
ORDER BY `year_month` DESC
LIMIT 5
"""

cursor.execute(query, ('UB-YTX14-BS',))
results = cursor.fetchall()

print('UB-YTX14-BS Monthly Sales Data:')
print('=' * 70)
for r in results:
    print(f"{r['year_month']}: BY Sales={r['burnaby_sales']}, KY Sales={r['kentucky_sales']}")
    print(f"         BY Corrected={r['corrected_demand_burnaby']}, KY Corrected={r['corrected_demand_kentucky']}")

# Calculate average
if results:
    avg_by = sum(float(r['corrected_demand_burnaby'] or 0) for r in results) / len(results)
    avg_ky = sum(float(r['corrected_demand_kentucky'] or 0) for r in results) / len(results)
    print(f"\nAverages: BY={avg_by:.0f}/month, KY={avg_ky:.0f}/month")

    # Calculate 2-month retention for Burnaby based on corrected demand
    retention_2m = avg_by * 2
    print(f"2-month retention for BY (based on corrected demand): {retention_2m:.0f} units")

    # But the system might be using a different calculation
    # Check with current inventory and pending
    inv_query = """
    SELECT burnaby_qty, kentucky_qty
    FROM inventory_current
    WHERE sku_id = %s
    """
    cursor.execute(inv_query, ('UB-YTX14-BS',))
    inv = cursor.fetchone()

    if inv:
        print(f"\nCurrent Inventory: BY={inv['burnaby_qty']}, KY={inv['kentucky_qty']}")
        print(f"After 3550 transfer: BY would have {inv['burnaby_qty'] - 3550} left")
        print(f"System says retaining 3509 units (which would be {3509/avg_by:.1f} months coverage)")

        # The discrepancy might be because the system is using the enhanced calculation
        # that includes ABC-XYZ classification
        print(f"\nSKU is classified as CZ (should use 6-month coverage for Kentucky)")
        print(f"But Burnaby retention should be 2 months based on the code")

cursor.close()
db.close()