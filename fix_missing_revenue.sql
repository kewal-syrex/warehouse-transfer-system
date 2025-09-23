USE warehouse_transfer;

-- Fix the UB-YTX12-BS record that didn't get updated due to append mode
UPDATE monthly_sales
SET burnaby_revenue = 1500.00, kentucky_revenue = 4500.00
WHERE sku_id = 'UB-YTX12-BS' AND `year_month` = '2025-09';

-- Verify both records now have correct revenue values
SELECT sku_id, `year_month`, burnaby_sales, kentucky_sales,
       burnaby_revenue, kentucky_revenue,
       burnaby_avg_revenue, kentucky_avg_revenue
FROM monthly_sales
WHERE sku_id IN ('UB-YTX14-BS', 'UB-YTX12-BS')
AND `year_month` = '2025-09'
ORDER BY sku_id;