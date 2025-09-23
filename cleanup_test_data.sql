USE warehouse_transfer;

-- Delete the TEST-SKU that was used for testing
DELETE FROM monthly_sales WHERE sku_id = 'TEST-SKU';

-- Check what remains for our test SKUs
SELECT sku_id, `year_month`, burnaby_sales, kentucky_sales,
       burnaby_revenue, kentucky_revenue,
       burnaby_avg_revenue, kentucky_avg_revenue
FROM monthly_sales
WHERE sku_id IN ('UB-YTX14-BS', 'UB-YTX12-BS')
AND `year_month` = '2025-09'
ORDER BY sku_id;