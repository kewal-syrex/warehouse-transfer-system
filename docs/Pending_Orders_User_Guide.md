# Pending Orders Management - User Guide

## Overview

The Pending Orders system helps you track in-transit inventory and make better transfer decisions by considering what's already on the way to each warehouse.

## Key Features

✅ **Smart Date Handling**: Automatically calculates arrival dates when not provided
✅ **Flexible CSV Import**: Supports mixed imports with and without dates
✅ **Enhanced Transfer Planning**: Prevents over-transferring by considering pending inventory
✅ **Supplier Configuration**: Customize lead times by supplier
✅ **Visual Indicators**: Clear status indicators for estimated vs confirmed dates

---

## Getting Started

### 1. Accessing Pending Orders

Navigate to **Data Management** → **Pending Orders** section

### 2. Import Your First Pending Orders

#### Required CSV Format:
```csv
sku_id,quantity,destination,expected_date
CHG-001,500,kentucky,2025-12-15
CBL-002,300,burnaby,
WDG-003,100,kentucky,2025-11-30
```

#### Column Descriptions:
- **sku_id** (Required): Must match existing SKU in system
- **quantity** (Required): Positive integer
- **destination** (Required): 'burnaby' or 'kentucky'
- **expected_date** (Optional): Leave blank for auto-calculation

#### Flexible Column Names:
The system accepts these column name variations:
- Date columns: `expected_date`, `expected_arrival`, `arrival_date`, `Expected Date`, `Arrival Date`
- Other columns: Case-insensitive matching supported

### 3. Understanding Date Handling

**When you provide dates:**
- Format: YYYY-MM-DD (e.g., 2025-12-15)
- Status: Marked as "Confirmed"
- Uses your exact date

**When you leave dates blank:**
- Auto-calculated as Today + 120 days
- Status: Marked as "Estimated"
- Can be updated later

### 4. Import Process

1. **Drag and drop** your CSV file or **click to browse**
2. **Review validation results**:
   - ✅ Success messages show what was imported
   - ⚠️ Warnings show auto-calculations and skipped items
   - ❌ Errors show what needs to be fixed
3. **Check the preview table** to see your imported data

---

## Understanding the Transfer Planning Impact

### Before Pending Orders:
```
Kentucky Stock: 100 units
Monthly Demand: 150 units
Coverage: 0.67 months → CRITICAL PRIORITY
```

### After Adding Pending Orders:
```
Kentucky Stock: 100 units
Pending Orders: 400 units arriving in 45 days
Projected Coverage: 3.33 months → MEDIUM PRIORITY
```

### Burnaby Retention Logic:
The system ensures Burnaby maintains adequate stock:
- **Minimum Coverage**: Never goes below 2.0 months
- **Target Coverage**: Maintains 6.0 months when possible
- **With Pending Orders**: Can reduce to 1.5 months if orders arrive within 45 days

---

## Advanced Features

### 1. Supplier-Specific Lead Times

Set custom lead times for different suppliers:

**Navigation**: Settings → Supplier Lead Times

**Examples**:
- Local Supplier: 14 days
- Overseas Supplier: 180 days
- Express Supplier (Burnaby only): 7 days

### 2. Mixed Import Scenarios

**Scenario 1: Partial Dates**
```csv
sku_id,quantity,destination,expected_date
CHG-001,500,kentucky,2025-12-15
CBL-002,300,burnaby,
```
**Result**: CHG-001 confirmed for Dec 15, CBL-002 estimated for +120 days

**Scenario 2: No Date Column**
```csv
sku_id,quantity,destination
CHG-001,500,kentucky
CBL-002,300,burnaby
```
**Result**: All orders estimated for Today + 120 days

### 3. Configuration Options

**Access**: Settings → Configuration

**Key Settings**:
- `default_lead_time_days`: Default when no date provided (120 days)
- `burnaby_min_coverage_months`: Minimum Burnaby retention (2.0 months)
- `burnaby_target_coverage_months`: Target Burnaby coverage (6.0 months)

### 4. Enhanced Excel Reports

The system generates comprehensive Excel reports with:

**Transfer Orders Sheet**:
- Enhanced with pending orders columns
- Coverage projections after transfers
- Stockout override indicators

**Pending Orders Sheet**:
- Complete list of all pending orders
- Status indicators and arrival dates
- Supplier and order type information

**Coverage Analysis Sheet**:
- Current vs projected coverage
- Impact analysis of pending orders
- Status indicators for coverage improvements

---

## Best Practices

### 📊 Data Quality

1. **Keep SKU IDs accurate**: System validates against master SKU list
2. **Use consistent date formats**: YYYY-MM-DD works best
3. **Update confirmed dates**: Convert estimates to actuals when available
4. **Regular cleanup**: Remove received/cancelled orders periodically

### 🔄 Workflow Integration

1. **Weekly Updates**: Import new pending orders weekly
2. **Date Confirmations**: Update estimated dates when shipping details available
3. **Transfer Planning**: Run enhanced calculations before transfer decisions
4. **Status Tracking**: Mark orders as shipped/received as they progress

### ⚠️ Common Issues

**Issue**: "SKU not found" errors
**Solution**: Ensure SKU IDs match exactly (case-sensitive)

**Issue**: "Invalid destination" warnings
**Solution**: Use only 'burnaby' or 'kentucky' (lowercase)

**Issue**: Import shows 0 records
**Solution**: Check required columns: sku_id, quantity, destination

**Issue**: Dates not parsing correctly
**Solution**: Use YYYY-MM-DD format or leave blank for auto-calculation

---

## Excel Export Guide

### Understanding the Enhanced Export

**File Structure**:
```
📊 transfer-orders-2025-09-13.xlsx
├── Transfer Orders (Enhanced with pending data)
├── Pending Orders (Complete pending inventory)
├── Coverage Analysis (Impact projections)
├── Summary (Key statistics)
└── Inventory Status (Current stock levels)
```

### Reading the Transfer Orders Sheet

**New Columns Explained**:
- **Pending CA**: Quantity coming to Burnaby
- **Pending KY**: Quantity coming to Kentucky
- **CA Coverage After**: Burnaby coverage after recommended transfer
- **KY Coverage After**: Kentucky coverage after recommended transfer
- **Stockout Override**: Whether quantity was overridden due to stockouts

**Color Coding**:
- 🔴 **CRITICAL**: Immediate action required
- 🟠 **HIGH**: Transfer recommended this week
- 🟡 **MEDIUM**: Transfer recommended this month
- 🟢 **LOW**: Stable, monitor for changes

### Using Coverage Analysis

**Status Indicators**:
- **IMPROVING**: Pending orders will improve coverage
- **LOW COVERAGE**: Still below target even with pending orders
- **NO PENDING**: No pending orders for this SKU

**Green highlighting**: Coverage improvements from pending orders

---

## Troubleshooting

### Import Issues

**Problem**: CSV import fails completely
**Check**:
1. File format is CSV (not Excel)
2. Required columns present: sku_id, quantity, destination
3. File size under 10MB

**Problem**: Some rows skipped during import
**Check**:
1. SKU IDs exist in system and are active
2. Quantities are positive integers
3. Destinations are 'burnaby' or 'kentucky'

### Transfer Planning Issues

**Problem**: Recommendations don't seem to consider pending orders
**Solution**:
1. Ensure using "Enhanced Calculations" mode
2. Check pending orders are in 'ordered', 'shipped', or 'pending' status
3. Verify pending orders have future arrival dates

**Problem**: Burnaby showing unexpected transfer restrictions
**Explanation**: Burnaby retention logic prevents over-transferring. Check:
1. Current Burnaby coverage levels
2. Pending orders arriving within 45 days
3. Configuration settings for minimum coverage

### Configuration Issues

**Problem**: Supplier lead times not applying
**Check**:
1. Supplier name matches exactly (case-sensitive)
2. Destination specified if supplier has multiple lead times
3. System restart may be required after configuration changes

---

## FAQ

**Q: What happens if I import the same pending order twice?**
A: The system will create duplicate entries. Best practice is to clear old data before importing updates.

**Q: Can I edit individual pending orders after import?**
A: Currently, editing is done through re-import. Delete and re-import for corrections.

**Q: How does the system handle cancelled orders?**
A: Set status to 'cancelled' or delete the pending order record.

**Q: What's the difference between 'estimated' and 'confirmed' dates?**
A: Estimated dates are auto-calculated (shown with icons), confirmed dates are provided by you and considered more reliable.

**Q: Can I use this for internal transfers between warehouses?**
A: Yes, set order_type to 'transfer' for internal movements.

**Q: How often should I update pending orders?**
A: Weekly updates are recommended, with date confirmations as shipping information becomes available.

---

## Support

For additional help:
1. Check the system's built-in help tooltips
2. Review import validation messages carefully
3. Use the API documentation at `/api/docs` for technical details
4. Contact your system administrator for configuration changes

---

*Last updated: September 2025 - Version 2.0*