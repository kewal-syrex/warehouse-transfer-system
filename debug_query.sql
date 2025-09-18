-- Debug query to check what calculate_all_transfer_recommendations is fetching
SELECT
    s.sku_id,
    s.description,
    COALESCE(ms.kentucky_sales, 0) as kentucky_sales,
    COALESCE(ms.kentucky_stockout_days, 0) as kentucky_stockout_days,
    COALESCE(ms.burnaby_sales, 0) as burnaby_sales,
    COALESCE(ms.burnaby_stockout_days, 0) as burnaby_stockout_days,
    COALESCE(ms.corrected_demand_kentucky, 0) as corrected_demand_kentucky,
    COALESCE(ms.corrected_demand_burnaby, 0) as corrected_demand_burnaby
FROM skus s
LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id
    AND ms.`year_month` = (
        SELECT MAX(`year_month`)
        FROM monthly_sales ms2
        WHERE ms2.sku_id = s.sku_id
        AND (ms2.kentucky_sales > 0 OR ms2.burnaby_sales > 0)
    )
WHERE s.sku_id = 'WF-RO-GAC10';