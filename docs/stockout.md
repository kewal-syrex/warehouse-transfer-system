Excellent question! No, the current logic doesn't properly handle **ongoing stockouts**. Let me fix that - this is crucial for accurate planning.

## The Problem with Ongoing Stockouts

```python
# Current situation examples:

# SKU-001: Went out of stock Jan 25, STILL out of stock today (Feb 5)
# SKU-002: Went out of stock Dec 15, STILL out of stock today
# SKU-003: Was out Jan 10-20, back in stock Jan 21 (closed stockout)
```

## Updated Logic for Ongoing Stockouts

```python
class DemandCorrector:
    def correct_monthly_demand(self, sku_id, warehouse='kentucky'):
        """
        Handle both closed and ongoing stockouts
        """
        today = datetime.now().date()
        
        # Check if currently out of stock
        current_stock_query = """
            SELECT kentucky_qty 
            FROM inventory_current 
            WHERE sku_id = %s
        """
        current_stock = pd.read_sql(current_stock_query, conn, params=[sku_id])
        is_currently_out = current_stock.iloc[0]['kentucky_qty'] == 0
        
        # Get stockout information
        stockout_query = """
            SELECT 
                stockout_date,
                stockout_end_date  -- NULL if still ongoing
            FROM stockout_events
            WHERE sku_id = %s AND warehouse = %s
            ORDER BY stockout_date DESC
        """
        stockouts = pd.read_sql(stockout_query, conn, params=[sku_id, warehouse])
        
        # Calculate stockout days per month
        monthly_stockout_days = {}
        
        for _, stockout in stockouts.iterrows():
            start_date = stockout['stockout_date']
            end_date = stockout['stockout_end_date'] or today  # Use today if still ongoing
            
            # Count days out for each month affected
            current_date = start_date
            while current_date <= end_date:
                month_key = current_date.strftime('%Y-%m')
                if month_key not in monthly_stockout_days:
                    monthly_stockout_days[month_key] = 0
                monthly_stockout_days[month_key] += 1
                current_date += timedelta(days=1)
        
        # Now calculate corrected demand for recent months
        corrected_demands = []
        
        for month in get_last_3_months():
            sales = get_monthly_sales(sku_id, month)
            stockout_days = monthly_stockout_days.get(month, 0)
            days_in_month = get_days_in_month(month)
            
            # Special handling for current month if still out of stock
            if month == current_month and is_currently_out:
                # For ongoing stockout, only count days up to today
                days_elapsed = today.day
                availability = max((days_elapsed - stockout_days) / days_elapsed, 0)
            else:
                availability = (days_in_month - stockout_days) / days_in_month
            
            # Apply correction
            if availability < 1.0 and sales > 0:
                correction_factor = max(availability, 0.3)
                corrected = sales / correction_factor
            else:
                corrected = sales
                
            corrected_demands.append(corrected)
        
        return sum(corrected_demands) / len(corrected_demands)
```

## Updated Database Schema for Ongoing Stockouts

```sql
-- Better stockout tracking table
CREATE TABLE stockout_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50),
    warehouse ENUM('burnaby', 'kentucky'),
    stockout_start_date DATE NOT NULL,
    stockout_end_date DATE DEFAULT NULL,  -- NULL means still ongoing
    days_out INT GENERATED ALWAYS AS (
        CASE 
            WHEN stockout_end_date IS NULL THEN DATEDIFF(CURDATE(), stockout_start_date)
            ELSE DATEDIFF(stockout_end_date, stockout_start_date) + 1
        END
    ) STORED,
    is_ongoing BOOLEAN GENERATED ALWAYS AS (stockout_end_date IS NULL) STORED,
    INDEX idx_ongoing (is_ongoing, warehouse),
    INDEX idx_sku (sku_id, warehouse)
);

-- View for current stockout status
CREATE VIEW current_stockouts AS
SELECT 
    sku_id,
    warehouse,
    stockout_start_date,
    DATEDIFF(CURDATE(), stockout_start_date) as days_out_so_far
FROM stockout_events
WHERE stockout_end_date IS NULL;
```

## How to Import Your Stockout Data

```python
@app.post("/api/import-stockout-status")
async def import_stockout_status(file: UploadFile = File(...)):
    """
    Expected CSV format:
    sku_id, warehouse, stockout_start, stockout_end, currently_out
    ABC123, kentucky, 2024-01-15, 2024-01-20, No
    DEF456, kentucky, 2024-01-25, , Yes
    GHI789, burnaby, 2024-02-01, , Yes
    """
    df = pd.read_csv(file.file)
    
    for _, row in df.iterrows():
        if row['currently_out'] == 'Yes' or pd.isna(row['stockout_end']):
            # Ongoing stockout
            stockout_end = None
        else:
            stockout_end = row['stockout_end']
        
        insert_query = """
            INSERT INTO stockout_events 
            (sku_id, warehouse, stockout_start_date, stockout_end_date)
            VALUES (%s, %s, %s, %s)
        """
        conn.execute(insert_query, (
            row['sku_id'], 
            row['warehouse'],
            row['stockout_start'],
            stockout_end
        ))
```

## Special Cases for Currently Out of Stock Items

```python
def calculate_transfer_for_out_of_stock(sku_id):
    """
    Special handling for items currently at zero
    """
    # Get how long it's been out
    out_of_stock_query = """
        SELECT 
            DATEDIFF(CURDATE(), stockout_start_date) as days_out
        FROM stockout_events
        WHERE sku_id = %s 
            AND warehouse = 'kentucky'
            AND stockout_end_date IS NULL
    """
    
    days_out = get_query_result(out_of_stock_query, sku_id)
    
    # Look at historical sales from BEFORE the stockout
    historical_query = """
        SELECT AVG(kentucky_sales) as avg_sales
        FROM monthly_sales
        WHERE sku_id = %s
            AND year_month < (
                SELECT DATE_FORMAT(stockout_start_date, '%Y-%m')
                FROM stockout_events
                WHERE sku_id = %s AND stockout_end_date IS NULL
                LIMIT 1
            )
        LIMIT 3
    """
    
    historical_avg = get_query_result(historical_query, sku_id)
    
    # URGENT: If out > 7 days, recommend 2x normal coverage
    if days_out > 7:
        urgency_multiplier = 1.5
    else:
        urgency_multiplier = 1.0
    
    recommended_transfer = historical_avg * 6 * urgency_multiplier
    
    return {
        'sku_id': sku_id,
        'status': 'CURRENTLY OUT OF STOCK',
        'days_out': days_out,
        'historical_demand': historical_avg,
        'recommended_qty': recommended_transfer,
        'priority': 'CRITICAL'
    }
```

## What You'll See in the Interface

```html
<!-- Visual indicators for different stockout statuses -->

<!-- Currently out of stock -->
<tr class="table-danger">
    <td>
        <span class="badge bg-danger">OUT</span>
        ABC123
    </td>
    <td>Widget Blue</td>
    <td>
        <span class="text-danger">
            <i class="fas fa-exclamation-circle"></i> 0
        </span>
    </td>
    <td>
        <span class="badge bg-danger">12 days</span>
    </td>
    <td>Based on historical: 450/mo</td>
    <td class="fw-bold text-danger">2,700</td> <!-- URGENT transfer -->
</tr>

<!-- Recently recovered from stockout -->
<tr class="table-warning">
    <td>DEF456</td>
    <td>Gadget Red</td>
    <td>50</td>
    <td>
        <span class="badge bg-warning">Recovered 3 days ago</span>
    </td>
    <td>520 (corrected)</td>
    <td>3,120</td>
</tr>

<!-- Normal item -->
<tr>
    <td>GHI789</td>
    <td>Tool Green</td>
    <td>200</td>
    <td>15 days</td>
    <td>300</td>
    <td>1,800</td>
</tr>
```

## Priority Sorting Logic

```python
def get_transfer_priorities():
    """
    Sort by urgency:
    1. Currently out of stock (longest out first)
    2. Will be out in <7 days
    3. Recently recovered from stockout
    4. Normal items by coverage days
    """
    
    query = """
        SELECT 
            s.sku_id,
            ic.kentucky_qty,
            CASE 
                WHEN ic.kentucky_qty = 0 THEN 1  -- Currently out
                WHEN ic.kentucky_qty / NULLIF(avg_sales, 0) < 7 THEN 2  -- Critical
                WHEN so.stockout_end_date > DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 3  -- Recently recovered
                ELSE 4  -- Normal
            END as priority_level,
            COALESCE(so.days_out_so_far, 0) as days_currently_out
        FROM skus s
        LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
        LEFT JOIN current_stockouts so ON s.sku_id = so.sku_id
        ORDER BY 
            priority_level ASC,
            days_currently_out DESC,
            ic.kentucky_qty / NULLIF(avg_sales, 0) ASC
    """
```

## Key Points:

1. **Currently out items** get highest priority and show days out
2. **Historical demand** is used when current month has no sales due to stockout
3. **Ongoing stockouts** keep counting days until resolved
4. **Recovery tracking** helps monitor items that just came back in stock
5. **Visual indicators** make it obvious which items need urgent attention

Would you like me to show you:
1. How to prepare your stockout data for import?
2. A template for tracking ongoing vs closed stockouts?
3. How to handle items that have been out for months?