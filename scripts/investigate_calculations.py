#!/usr/bin/env python3
"""
Script to investigate specific SKU demand calculations and identify issues
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import execute_query
from backend.weighted_demand import WeightedDemandCalculator
from backend.calculations import TransferCalculator

def investigate_wf_ro_gac10():
    """Investigate WF-RO-GAC10 demand calculation showing 702"""
    print("=" * 80)
    print("INVESTIGATING WF-RO-GAC10 DEMAND CALCULATION")
    print("=" * 80)

    # Get SKU info
    sku_query = "SELECT * FROM skus WHERE sku_id = %s"
    sku_info = execute_query(sku_query, ('WF-RO-GAC10',), fetch_one=True)

    if not sku_info:
        print("SKU WF-RO-GAC10 not found!")
        return

    print(f"\nSKU Classification: ABC={sku_info.get('abc_code')}, XYZ={sku_info.get('xyz_code')}")
    print(f"Current Inventory: KY={sku_info.get('kentucky_qty')}, BY={sku_info.get('burnaby_qty')}")

    # Get sales history
    sales_query = """
    SELECT
        `year_month`,
        kentucky_sales,
        burnaby_sales,
        total_sales,
        corrected_demand_kentucky,
        corrected_demand_burnaby
    FROM sales_history
    WHERE sku_id = %s
    ORDER BY `year_month` DESC
    LIMIT 6
    """

    sales = execute_query(sales_query, ('WF-RO-GAC10',), fetch_all=True)

    print("\n📊 Recent Sales History (Last 6 months):")
    print("Month     | KY Sales | BY Sales | Total | KY Corrected | BY Corrected")
    print("-" * 70)

    monthly_ky_sales = []
    if sales:
        for row in sales:
            ky_sales = row.get('kentucky_sales', 0) or 0
            by_sales = row.get('burnaby_sales', 0) or 0
            total = row.get('total_sales', 0) or 0
            ky_corr = row.get('corrected_demand_kentucky', 0) or 0
            by_corr = row.get('corrected_demand_burnaby', 0) or 0
            monthly_ky_sales.append(ky_corr)
            print(f"{row.get('year_month')} | {ky_sales:8} | {by_sales:8} | {total:5} | {ky_corr:12.2f} | {by_corr:12.2f}")

    # Calculate weighted demand
    print("\n🧮 Weighted Demand Calculation for Kentucky:")
    calc = WeightedDemandCalculator()
    ky_result = calc.get_enhanced_demand_calculation(
        sku_id='WF-RO-GAC10',
        abc_class=sku_info.get('abc_code', 'C'),
        xyz_class=sku_info.get('xyz_code', 'Z'),
        current_month_sales=0,
        stockout_days=0,
        warehouse='kentucky'
    )

    print(f"\n📈 Enhanced Demand Result: {ky_result.get('enhanced_demand'):.2f}")
    print(f"Weighted Average Base: {ky_result.get('weighted_average_base'):.2f}")
    print(f"Volatility Adjustment: {ky_result.get('volatility_adjustment'):.2f}")
    print(f"Calculation Method: {ky_result.get('calculation_method')}")
    print(f"Primary Method: {ky_result.get('primary_method')}")
    print(f"Sample Months Used: {ky_result.get('sample_months')}")

    # Show the formula
    print("\n📝 Formula Breakdown:")
    print(f"For C-Z classification, using {ky_result.get('primary_method')} approach")

    if monthly_ky_sales:
        print(f"\nMonthly corrected demands (most recent first): {monthly_ky_sales[:6]}")

        if len(monthly_ky_sales) >= 6:
            # 6-month weighted average calculation
            weights_6m = [0.3, 0.25, 0.2, 0.15, 0.1, 0.05]  # Newer months get higher weight
            weighted_sum = sum(monthly_ky_sales[i] * weights_6m[i] for i in range(min(6, len(monthly_ky_sales))))
            print(f"\n6-Month Weighted Calculation:")
            for i in range(min(6, len(monthly_ky_sales))):
                print(f"  Month {i+1}: {monthly_ky_sales[i]:.2f} * {weights_6m[i]:.2f} = {monthly_ky_sales[i] * weights_6m[i]:.2f}")
            print(f"  Weighted Sum = {weighted_sum:.2f}")

    print(f"\n✅ Final Enhanced Demand = {ky_result.get('weighted_average_base'):.2f} * {ky_result.get('volatility_adjustment'):.2f} = {ky_result.get('enhanced_demand'):.2f}")

    # Check if this matches the 702 being displayed
    if abs(ky_result.get('enhanced_demand') - 702) < 1:
        print("\n✅ This matches the displayed value of 702!")
    else:
        print(f"\n⚠️ This ({ky_result.get('enhanced_demand'):.2f}) does NOT match the displayed value of 702")

def investigate_vp_eu_hf2_flt():
    """Investigate VP-EU-HF2-FLT transfer logic issue"""
    print("\n" + "=" * 80)
    print("INVESTIGATING VP-EU-HF2-FLT TRANSFER LOGIC")
    print("=" * 80)

    # Get SKU info
    sku_query = "SELECT * FROM skus WHERE sku_id = %s"
    sku_info = execute_query(sku_query, ('VP-EU-HF2-FLT',), fetch_one=True)

    if not sku_info:
        print("SKU VP-EU-HF2-FLT not found!")
        return

    print(f"\nCurrent Inventory: KY={sku_info.get('kentucky_qty')}, BY={sku_info.get('burnaby_qty')}")
    print(f"Transfer Multiple: {sku_info.get('transfer_multiple')}")

    if sku_info.get('burnaby_qty') == 30:
        print("\n⚠️ ISSUE CONFIRMED: Burnaby only has 30 units available")
        print("System should NOT suggest transferring 50 units!")

    # Check the transfer calculation
    calc = WeightedDemandCalculator()
    ky_demand = calc.get_enhanced_demand_calculation(
        sku_id='VP-EU-HF2-FLT',
        abc_class=sku_info.get('abc_code', 'C'),
        xyz_class=sku_info.get('xyz_code', 'Z'),
        current_month_sales=0,
        stockout_days=0,
        warehouse='kentucky'
    )

    print(f"\nKentucky Weighted Demand: {ky_demand.get('enhanced_demand'):.2f} units/month")
    print(f"Current KY Inventory: {sku_info.get('kentucky_qty')} units")

    # Calculate what the transfer should be
    coverage_target = 6  # months for C-Z
    target_inventory = ky_demand.get('enhanced_demand') * coverage_target
    transfer_need = max(0, target_inventory - sku_info.get('kentucky_qty', 0))

    print(f"\n📊 Transfer Calculation:")
    print(f"Target Inventory = {ky_demand.get('enhanced_demand'):.2f} * {coverage_target} = {target_inventory:.2f}")
    print(f"Transfer Need = {target_inventory:.2f} - {sku_info.get('kentucky_qty')} = {transfer_need:.2f}")
    print(f"Available in Burnaby: {sku_info.get('burnaby_qty')} units")
    print(f"Maximum Transfer Possible: {min(transfer_need, sku_info.get('burnaby_qty', 0)):.2f} units")

    print("\n❌ PROBLEM: Transfer calculation is not properly checking Burnaby availability!")

def investigate_retention_math():
    """Investigate CA retention math issue"""
    print("\n" + "=" * 80)
    print("INVESTIGATING CA RETENTION CALCULATION")
    print("=" * 80)

    # Find an SKU with 4250 transfer suggestion
    query = """
    SELECT sku_id, kentucky_qty, burnaby_qty
    FROM skus
    WHERE burnaby_qty >= 4250
    LIMIT 1
    """

    result = execute_query(query, fetch_one=True)

    if result:
        sku_id = result.get('sku_id')
        print(f"\nExample SKU with large inventory: {sku_id}")
        print(f"Burnaby Available: {result.get('burnaby_qty')} units")

        # If transferring 4250 units
        transfer_qty = 4250
        remaining = result.get('burnaby_qty') - transfer_qty

        print(f"\nIf transferring {transfer_qty} units:")
        print(f"CA would retain: {remaining} units")
        print(f"NOT 92 units as stated in the reason!")

        print("\n❌ PROBLEM: Retention calculation appears to have incorrect math")
        print("The retention calculation in calculations.py needs to be reviewed")

if __name__ == "__main__":
    investigate_wf_ro_gac10()
    investigate_vp_eu_hf2_flt()
    investigate_retention_math()