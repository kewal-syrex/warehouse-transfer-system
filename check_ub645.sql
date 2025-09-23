USE warehouse_transfer;

SELECT sku_id, `year_month`, burnaby_sales, kentucky_sales, burnaby_revenue, kentucky_revenue
FROM monthly_sales
WHERE sku_id = 'UB645' AND `year_month` = '2025-09';