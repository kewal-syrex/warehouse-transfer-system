USE warehouse_transfer;

-- Test revenue columns by updating one record
UPDATE monthly_sales
SET burnaby_revenue = 1234.56, kentucky_revenue = 2345.67
WHERE sku_id = 'UB-YTX14-BS' AND `year_month` = '2025-08'
LIMIT 1;

-- Check the results including calculated fields
SELECT sku_id, `year_month`, burnaby_sales, kentucky_sales,
       burnaby_revenue, kentucky_revenue, total_revenue,
       burnaby_avg_revenue, kentucky_avg_revenue
FROM monthly_sales
WHERE sku_id = 'UB-YTX14-BS' AND `year_month` = '2025-08';