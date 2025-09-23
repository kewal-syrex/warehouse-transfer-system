#!/usr/bin/env python3
"""Test stockout correction calculation for UB-YTX14AH-BS"""

def correct_monthly_demand(monthly_sales: int, stockout_days: int, days_in_month: int = 30) -> float:
    """
    Calculate stockout-corrected demand using the simplified monthly approach
    """
    if stockout_days == 0 or monthly_sales == 0:
        return float(monthly_sales)

    # Calculate availability rate
    availability_rate = (days_in_month - stockout_days) / days_in_month

    if availability_rate < 1.0:
        # Apply correction with 30% floor to prevent overcorrection
        correction_factor = max(availability_rate, 0.3)
        corrected_demand = monthly_sales / correction_factor

        # Cap at 50% increase for very low availability (safeguard)
        if availability_rate < 0.3:
            corrected_demand = min(corrected_demand, monthly_sales * 1.5)

        return round(corrected_demand, 2)

    return float(monthly_sales)

# Test for UB-YTX14AH-BS
print("Testing UB-YTX14AH-BS stockout correction:")
print("=" * 50)

# August 2025: 102 sales, 11 stockout days (Aug 21-31)
august_sales = 102
august_stockout = 11
days_in_august = 31

availability = (days_in_august - august_stockout) / days_in_august
print(f"\nAugust 2025:")
print(f"  Sales: {august_sales}")
print(f"  Stockout days: {august_stockout}")
print(f"  Days in month: {days_in_august}")
print(f"  Availability rate: {availability:.2%}")

august_corrected = correct_monthly_demand(august_sales, august_stockout, days_in_august)
print(f"  Corrected demand: {august_corrected}")
print(f"  Calculation: {august_sales} / {availability:.3f} = {august_corrected}")

# June 2025: 62 sales, 19 stockout days
june_sales = 62
june_stockout = 19
days_in_june = 30

june_availability = (days_in_june - june_stockout) / days_in_june
print(f"\nJune 2025:")
print(f"  Sales: {june_sales}")
print(f"  Stockout days: {june_stockout}")
print(f"  Days in month: {days_in_june}")
print(f"  Availability rate: {june_availability:.2%}")

june_corrected = correct_monthly_demand(june_sales, june_stockout, days_in_june)
print(f"  Corrected demand: {june_corrected}")
print(f"  Calculation: {june_sales} / {june_availability:.3f} = {june_corrected}")

# May 2025: 62 sales, 27 stockout days
may_sales = 62
may_stockout = 27
days_in_may = 31

may_availability = (days_in_may - may_stockout) / days_in_may
print(f"\nMay 2025:")
print(f"  Sales: {may_sales}")
print(f"  Stockout days: {may_stockout}")
print(f"  Days in month: {days_in_may}")
print(f"  Availability rate: {may_availability:.2%}")

# Note: Since availability < 30%, correction factor will be 0.3
if may_availability < 0.3:
    may_correction_factor = 0.3
    print(f"  Using 30% floor for correction factor (actual availability: {may_availability:.2%})")
else:
    may_correction_factor = may_availability

may_corrected = correct_monthly_demand(may_sales, may_stockout, days_in_may)
print(f"  Corrected demand: {may_corrected}")
print(f"  Calculation: {may_sales} / {may_correction_factor:.3f} = {may_corrected}")

# Calculate 3-month average
three_month_avg = (august_corrected + june_corrected + may_corrected) / 3
print(f"\n3-Month Average Corrected Demand: {three_month_avg:.2f}")

# What appears to be showing as 83
print(f"\nIf the UI is showing 83, it might be:")
print(f"1. Using raw sales average: ({august_sales} + {june_sales} + {may_sales}) / 3 = {(august_sales + june_sales + may_sales) / 3:.2f}")
print(f"2. Not applying stockout correction properly")
print(f"3. Using different data or time period")