# Current Demand Calculation Report

## Overview
This document provides a detailed analysis of how the warehouse transfer planning tool currently calculates demand for inventory transfers from Burnaby (Canada) to Kentucky (US).

## Primary Demand Source: Latest Month's Sales with Stockout Correction

The system primarily uses the **most recent month's sales data**, NOT an average of multiple months. Here's exactly what factors are being used:

## 1. Base Demand Calculation
- **Source**: Latest month's Kentucky sales (single month)
- **NOT averaged** - uses actual monthly sales from the most recent period
- Stored in `monthly_sales` table with `kentucky_sales` field
- Each SKU's demand is calculated independently

## 2. Stockout Correction (Primary Enhancement)

The system applies sophisticated stockout correction to account for lost sales during stockout periods:

### Core Algorithm
```python
def correct_monthly_demand(monthly_sales, stockout_days, days_in_month=30):
    availability_rate = (days_in_month - stockout_days) / days_in_month

    if availability_rate < 1.0:
        correction_factor = max(availability_rate, 0.3)  # 30% floor
        corrected_demand = monthly_sales / correction_factor

        # Cap at 50% increase for very low availability
        if availability_rate < 0.3:
            corrected_demand = min(corrected_demand, monthly_sales * 1.5)

    return corrected_demand
```

### Key Parameters
- **Stockout Days**: Number of days the item was out of stock
- **Availability Rate**: `(days_in_month - stockout_days) / days_in_month`
- **Correction Formula**: `corrected_demand = monthly_sales / correction_factor`
- **Safety Floor**: Minimum 30% availability factor to prevent overcorrection
- **Maximum Cap**: 50% increase cap for very low availability

## 3. Seasonal Pattern Detection

The system analyzes 2+ years of historical data to detect seasonal patterns:

### Pattern Classifications
- **Spring/Summer Pattern**: Peak demand March-August
- **Fall/Winter Pattern**: Peak demand September-February
- **Holiday Pattern**: Peak in November-December
- **Year-Round**: Consistent demand throughout the year

### Seasonal Multipliers
- Ranges from 0.8 to 1.5 based on pattern and current month
- Applied as a multiplier to the corrected demand
- Automatically adjusts for seasonal peaks and valleys

### Detection Method
- Analyzes monthly sales distribution across years
- Calculates percentage of annual sales by month
- Identifies months with >10% of annual sales as peak periods
- Classifies pattern based on peak month distribution

## 4. Viral Growth Detection

Compares recent 3 months vs previous 3 months to identify growth trends:

### Growth Classifications
- **Viral Growth**: 2x+ increase ’ 1.5x multiplier
- **Normal Growth**: Stable ’ 1.0x multiplier
- **Declining**: Decreasing ’ 0.8x multiplier

### Detection Logic
```python
recent_avg = average(last_3_months_sales)
previous_avg = average(previous_3_months_sales)

if recent_avg > previous_avg * 2:
    growth_status = 'viral'
elif recent_avg < previous_avg * 0.5:
    growth_status = 'declining'
else:
    growth_status = 'normal'
```

## 5. Historical Fallbacks (Zero Sales/Heavy Stockouts)

When current month has zero sales with significant stockouts (>20 days), the system uses fallback methods:

### Fallback Hierarchy
1. **Year-Over-Year Lookup**: Same month from previous year
2. **Category Average**: Average demand for similar SKUs in same category
3. **Historical Pattern**: Monthly averages from 2+ years of data
4. **Minimum Viable Demand**: Default to 10 units if all else fails

### Implementation
- Triggered when monthly_sales = 0 AND stockout_days > 20
- Each fallback is tried in order until valid data is found
- Ensures some demand estimate even for heavily stocked-out items

## 6. Pending Orders Integration

The system incorporates pending orders with time-weighted confidence:

### Time-Based Weighting
- **0-30 days**: 100% weight (high confidence)
- **31-60 days**: 80% weight (medium confidence)
- **61-90 days**: 60% weight (low confidence)
- **90+ days**: 40% weight (very low confidence)

### Usage in Calculations
- Pending quantities reduce transfer need for Kentucky
- Pending orders affect Burnaby retention requirements
- Time-weighted totals used in coverage calculations

## 7. Final Demand Formula

```
Final Demand = Latest_Month_Sales
             × Stockout_Correction_Factor
             × Seasonal_Multiplier (0.8-1.5)
             × Growth_Multiplier (0.8-1.5)
```

### Example Calculation
```
SKU: USB-C Charger
Latest Month Sales: 100 units
Stockout Days: 10 days
Seasonal Pattern: Holiday (December, multiplier = 1.4)
Growth Status: Viral (multiplier = 1.5)

Stockout Correction: 100 / 0.67 = 149 units
Seasonal Adjustment: 149 × 1.4 = 209 units
Growth Adjustment: 209 × 1.5 = 313 units

Final Demand = 313 units/month
```

## What the System Does NOT Do

- **Does NOT use simple moving averages** (e.g., 3-month or 6-month averages)
- **Does NOT use weighted averages by default**
- **Does NOT forecast future demand** beyond pattern adjustments
- **Does NOT use traditional time series forecasting** methods (ARIMA, etc.)
- **Does NOT consider external factors** (promotions, market trends, competition)
- **Does NOT use exponential smoothing** or other smoothing techniques
- **Does NOT account for product lifecycle** stages (introduction, growth, maturity, decline)

## Key System Characteristics

### Strengths
1. **Stockout Intelligence**: Sophisticated correction for out-of-stock periods
2. **Pattern Recognition**: Detects seasonal and growth patterns automatically
3. **Fallback Logic**: Multiple methods to handle edge cases
4. **Real-time Adjustments**: Uses latest month data for responsiveness

### Limitations
1. **Single Month Focus**: Heavy bias toward latest month rather than smoothed averages
2. **Reactive Nature**: Corrects past issues rather than predicting future demand
3. **No True Forecasting**: Pattern overlays aren't true statistical forecasts
4. **Limited External Factors**: Doesn't consider promotions, competition, or market changes

## Data Flow

1. **Monthly Sales Import** ’ `monthly_sales` table
2. **Stockout Days Entry** ’ Manual or calculated
3. **Demand Correction** ’ Apply stockout formula
4. **Pattern Detection** ’ Analyze 2+ years history
5. **Growth Analysis** ’ Compare recent vs previous periods
6. **Final Calculation** ’ Apply all multipliers
7. **Transfer Recommendation** ’ Use final demand for coverage targets

## Database Fields Used

### Primary Tables
- `monthly_sales`: kentucky_sales, burnaby_sales, year_month
- `skus`: abc_code, xyz_code, category, seasonal_pattern, growth_status
- `current_inventory`: kentucky_qty, burnaby_qty
- `pending_inventory`: quantity, expected_arrival, destination

### Calculated Fields
- `corrected_demand_kentucky`: Stockout-corrected demand
- `corrected_demand_burnaby`: Stockout-corrected demand for CA
- `seasonal_multiplier`: Current month's seasonal adjustment
- `growth_multiplier`: Growth trend adjustment

## Potential Improvements to Consider

1. **Implement Moving Averages**: Use 3-month or 6-month averages for more stable baseline
2. **Add Exponential Smoothing**: Weight recent months more heavily
3. **Consider Demand Volatility**: Factor in coefficient of variation for safety stock
4. **True Forecasting Models**: Implement ARIMA or similar for seasonal items
5. **New Product Curves**: Special handling for products in introduction phase
6. **External Factor Integration**: Account for promotions, holidays, market events
7. **Demand Sensing**: Incorporate real-time signals (web traffic, search trends)
8. **Machine Learning**: Use ML models to improve prediction accuracy
9. **Scenario Planning**: Multiple demand scenarios (optimistic, realistic, pessimistic)
10. **Collaborative Forecasting**: Incorporate sales team input and customer forecasts

## Configuration Parameters

### Tunable Settings
- **Stockout Correction Floor**: 30% (prevents extreme corrections)
- **Stockout Correction Cap**: 50% increase maximum
- **Seasonal Peak Threshold**: 10% of annual sales
- **Viral Growth Threshold**: 2x increase
- **Declining Threshold**: 50% decrease
- **Coverage Targets**: Varies by ABC-XYZ classification
- **Pending Order Weights**: Time-based confidence factors

## Implementation Files

### Core Logic
- `backend/calculations.py`: Main calculation engine
- `backend/calculations.py:StockoutCorrector`: Stockout correction logic
- `backend/calculations.py:SeasonalPatternDetector`: Seasonal analysis
- `backend/calculations.py:ViralGrowthDetector`: Growth trend detection
- `backend/calculations.py:TransferCalculator`: Final recommendations

### Supporting Functions
- `database.py`: Data retrieval and updates
- `import_export.py`: Sales data import with correction triggers
- `main.py`: API endpoints for calculations

## Summary

The current demand calculation system is sophisticated in its correction mechanisms but fundamentally relies on the latest month's actual sales as its base. It's designed to be reactive and corrective rather than predictive, with multiple layers of adjustments to account for stockouts, seasonality, and growth trends. While effective for stable SKUs with consistent patterns, the system could benefit from more advanced forecasting techniques for new products, highly seasonal items, or volatile demand patterns.