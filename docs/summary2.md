 ⎿  Fix Pending Orders Import & Improve Error Reporting

     Problem Analysis:

     1. Database Issue: expected_arrival column doesn't allow NULL values
     2. Import Failure: 63 orders with empty expected dates fail to import
     3. Poor Error Visibility: Current error reporting doesn't show which SKUs succeeded vs failed

     Solution Plan:

     1. Fix Database Schema

     Option A - Make Column Nullable (Simpler):
     ALTER TABLE pending_inventory
     MODIFY COLUMN expected_arrival DATE NULL;

     Option B - Calculate Date During Import (Current approach):
     - When expected_arrival is empty, calculate it as order_date + 120 days
     - Store calculated date in database (no NULLs)

     2. Enhanced Import Code

     Update /api/pending-orders/import-csv to:
     - Calculate expected_arrival = order_date + 120 days when empty
     - Track successful imports with details (SKU, quantity, destination)
     - Track failed imports with specific error messages
     - Return comprehensive results

     3. Improved Error Reporting Structure

     {
       "success": true,
       "summary": {
         "total_rows": 287,
         "imported": 224,
         "failed": 63,
         "estimated_dates": 63
       },
       "successful_imports": [
         {"sku_id": "UB-YIX30L-BS", "quantity": 800, "destination": "burnaby"},
         // ... all successful imports
       ],
       "failed_imports": [
         {"sku_id": "CALLAWAY-UPRO", "quantity": 50, "error": "Missing expected date"},
         // ... all failed imports with reasons
       ]
     }

     4. Frontend Display Improvements

     - Show collapsible sections for successful/failed imports
     - Display counts prominently
     - Allow export of error report for analysis
     - Color-code results (green for success, yellow for warnings, red for failures)

     Implementation Steps:

     1. Modify import endpoint to calculate dates when empty
     2. Track all import attempts (successful and failed)
     3. Return detailed results with both lists
     4. Update frontend to display comprehensive results
     5. Add "Export Error Report" button for failed imports

     This will ensure all 287 rows import successfully and provide complete visibility into the import process.