# docs/stockout_investigation.md

### Status
Accepted (2025-09-20)

### Context
- Reported issues:
  - Stockout days show for UB645 but not for other SKUs in the SKU Details modal on Transfer Planning.
  - Examples:
    - UB-YTX14AH-BS: Burnaby stockout Aug 21–Sep 2, 2025 not shown.
    - BT-183342: Kentucky stockout May 29–Jun 12 not shown.
  - Request: Show a stockout-days column for Burnaby and one for Kentucky, and ensure both are factored into demand.

### Findings

- Data model supports both warehouses:
  - `database/schema.sql` has `monthly_sales` with `burnaby_stockout_days` and `kentucky_stockout_days`.
  - `stockout_dates` table exists with views and triggers to track periods and update monthly aggregates.

- Backend returns both stockout columns to the modal:
  - `/api/sku/{sku_id}` selects:
    - `year_month, burnaby_sales, kentucky_sales, burnaby_stockout_days, kentucky_stockout_days, corrected_demand_*`.

- Demand calculations factor stockouts for BOTH warehouses:
  - Enhanced transfer path uses weighted demand with stockout correction per warehouse:
    - Kentucky: passes `kentucky_stockout_days` into `get_enhanced_demand_calculation(... warehouse='kentucky')`.
    - Burnaby: passes `burnaby_stockout_days` into `get_enhanced_demand_calculation(... warehouse='burnaby')`.
  - Cache population also reads both stockout fields and computes per-warehouse enhanced demand.

- Root cause in UI:
  - The SKU Details modal table and chart only use `kentucky_stockout_days`. `burnaby_stockout_days` is ignored.
  - Result: SKUs with Burnaby-only stockouts (e.g., UB-YTX14AH-BS) show no stockout indication; UB645 likely had Kentucky stockout, so it appears.

### Evidence

- Backend `/api/sku/{sku_id}` returns both stockout fields:
```588:635:backend/main.py
@app.get("/api/sku/{sku_id}")
async def get_sku_details(sku_id: str):
    ...
    cursor.execute("""
        SELECT `year_month`, burnaby_sales, kentucky_sales,
               burnaby_stockout_days, kentucky_stockout_days,
               corrected_demand_kentucky, corrected_demand_burnaby
        FROM monthly_sales
        WHERE sku_id = %s
        ORDER BY `year_month` DESC
    """, (sku_id,))
    sales_history = cursor.fetchall()
    ...
```

- Modal table only displays Kentucky stockouts:
```1516:1523:frontend/transfer-planning.html
<tbody>
    ${salesWithTotals.map(s => `
        <tr ${s.kentucky_stockout_days > 0 ? 'class="table-warning"' : ''}>
            <td><small>${s.year_month}</small></td>
            <td>${s.burnaby_sales}</td>
            <td>${s.kentucky_sales}</td>
            <td><strong>${s.total_sales}</strong></td>
            <td>${s.kentucky_stockout_days > 0 ? '<span class="badge bg-warning">' + s.kentucky_stockout_days + '</span>' : '-'}</td>
        </tr>
    `).join('')}
```

- Modal chart annotations and tooltips only consider Kentucky stockouts:
```1586:1603:frontend/transfer-planning.html
const stockoutDays = salesData.map(s => s.kentucky_stockout_days || 0).reverse();
...
salesData.forEach((s, originalIndex) => {
    if (s.kentucky_stockout_days > 0) {
        const reversedIndex = salesData.length - 1 - originalIndex;
        stockoutAnnotations[`stockout-${reversedIndex}`] = { ... };
    }
});
```

- Calculations use both warehouses’ stockouts:
```1266:1331:backend/calculations.py
kentucky_enhanced_result = self.weighted_demand_calculator.get_enhanced_demand_calculation(
    sku_id, abc_class, xyz_class, kentucky_sales, stockout_days, warehouse='kentucky'
)
...
burnaby_enhanced_result = self.weighted_demand_calculator.get_enhanced_demand_calculation(
    sku_id, abc_class, xyz_class, burnaby_sales, burnaby_stockout_days, warehouse='burnaby'
)
```

### Recommendations

- Frontend (SKU Details modal):
  - Add separate columns for Burnaby and Kentucky stockout days.
  - Highlight the row if either warehouse has stockouts.
  - Update the chart to visualize both warehouses’ stockout days (distinct annotation colors and tooltip lines).

- Transfer table (optional improvement):
  - Replace single `SO:Xd` badge with two badges `CA:Xd` and `US:Xd` when present.

- Backend/data sanity:
  - Verify `monthly_sales` contains correct `burnaby_stockout_days` and `kentucky_stockout_days` for the example SKUs and months.
  - Ensure stockout aggregation job/trigger populates monthly rows for the relevant months; if triggers are not deployed in prod, run a one-time backfill.

### Proposed UI edits (minimal)

- Table header: change from one “Stockout Days” to two columns.
- Table row: render both `burnaby_stockout_days` and `kentucky_stockout_days`, and warn if either > 0.
```1508:1514:frontend/transfer-planning.html
<thead class="table-light sticky-top">
    <tr>
        <th>Month</th>
        <th>CA Sales</th>
        <th>US Sales</th>
        <th>Total</th>
        <th>CA Stockout</th>
        <th>US Stockout</th>
    </tr>
</thead>
```

```1516:1523:frontend/transfer-planning.html
<tbody>
    ${salesWithTotals.map(s => `
        <tr ${(s.kentucky_stockout_days > 0 || s.burnaby_stockout_days > 0) ? 'class="table-warning"' : ''}>
            <td><small>${s.year_month}</small></td>
            <td>${s.burnaby_sales}</td>
            <td>${s.kentucky_sales}</td>
            <td><strong>${s.total_sales}</strong></td>
            <td>${s.burnaby_stockout_days > 0 ? '<span class="badge bg-warning">' + s.burnaby_stockout_days + '</span>' : '-'}</td>
            <td>${s.kentucky_stockout_days > 0 ? '<span class="badge bg-warning">' + s.kentucky_stockout_days + '</span>' : '-'}</td>
        </tr>
    `).join('')}
</tbody>