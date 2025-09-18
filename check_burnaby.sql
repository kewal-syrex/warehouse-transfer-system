SELECT sku_id, `year_month`, corrected_demand_burnaby
FROM monthly_sales
WHERE sku_id = 'WF-RO-GAC10'
ORDER BY `year_month` DESC
LIMIT 3;