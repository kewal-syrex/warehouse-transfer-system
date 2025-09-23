SELECT sku_id, `year_month`, burnaby_sales, kentucky_sales, burnaby_stockout_days, kentucky_stockout_days
FROM monthly_sales
WHERE sku_id = 'UB-YTX14AH-BS'
ORDER BY `year_month` DESC
LIMIT 6;