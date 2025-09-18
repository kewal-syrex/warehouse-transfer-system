-- SQL script to fix missing corrected_demand_burnaby values
-- This applies the same stockout correction logic used for Kentucky to Burnaby

-- First, check current values for a sample SKU
SELECT
    sku_id,
    `year_month`,
    burnaby_sales,
    burnaby_stockout_days,
    corrected_demand_burnaby,
    corrected_demand_kentucky
FROM monthly_sales
WHERE sku_id = 'WF-RO-GAC10'
ORDER BY `year_month` DESC
LIMIT 5;

-- Update corrected_demand_burnaby using the same stockout correction formula
-- Formula: If no stockout, use sales directly. If stockout, apply correction factor.
-- Correction factor = max(availability_rate, 0.3) where availability_rate = (30 - stockout_days) / 30
-- This matches the Kentucky calculation logic

UPDATE monthly_sales
SET corrected_demand_burnaby = CASE
    WHEN burnaby_stockout_days = 0 OR burnaby_stockout_days IS NULL THEN
        burnaby_sales
    WHEN burnaby_sales > 0 THEN
        LEAST(
            burnaby_sales / GREATEST((30 - burnaby_stockout_days) / 30.0, 0.3),
            burnaby_sales * 1.5
        )
    ELSE
        0
END
WHERE corrected_demand_burnaby = 0.00 OR corrected_demand_burnaby IS NULL;

-- Check the results for the sample SKU
SELECT
    sku_id,
    `year_month`,
    burnaby_sales,
    burnaby_stockout_days,
    corrected_demand_burnaby,
    corrected_demand_kentucky
FROM monthly_sales
WHERE sku_id = 'WF-RO-GAC10'
ORDER BY `year_month` DESC
LIMIT 5;