# **Product Requirements Document (PRD)**
## **Supplier Performance Analytics System**
*Version 1.0 - December 2024*

---

## **1. Executive Summary**

### **Product Overview**
A supplier performance tracking and analytics system that uses historical shipment data to calculate lead time reliability, predict delivery dates, and optimize reorder points for inventory planning.

### **Key Objectives**
- Track and analyze supplier lead time performance using historical PO data
- Calculate reliable planning lead times for each supplier
- Integrate with existing forecasting and ordering systems
- Reduce stockouts caused by unexpected supplier delays
- Minimize excess inventory from overly conservative lead time estimates

### **Target Users**
- Primary: Inventory/Supply Chain Manager (1 user initially)
- Secondary: Operations team members (2-3 users)

---

## **2. Problem Statement**

### **Current Situation**
- Using fixed 120-day lead time assumption for all suppliers
- No visibility into actual supplier performance variations
- Cannot identify which suppliers are reliable vs problematic
- Safety stock calculations don't account for supplier variability
- No early warning system for degrading supplier performance

### **Impact**
- Stockouts when suppliers deliver late
- Excess inventory from overly conservative planning
- ~$800K annual carrying cost on $8M excess inventory (per previous discussion)
- Unable to negotiate with suppliers using data

---

## **3. Solution Overview**

### **Core Concept**
Import historical shipment data (PO number, dates, supplier) to automatically calculate lead time statistics and reliability scores for each supplier, then use these metrics to optimize inventory planning.

### **Key Features**
1. **Data Import** - Upload CSV of historical shipments
2. **Lead Time Analytics** - Calculate avg, min, max, P95 statistics
3. **Reliability Scoring** - Rate suppliers based on consistency
4. **Performance Dashboard** - Visualize supplier metrics and trends
5. **Planning Integration** - Export metrics for use in ordering decisions

---

## **4. Functional Requirements**

### **4.1 Data Import**

#### **Upload Interface**
```
REQUIREMENT: Support CSV upload for supplier shipment history
- File format: CSV (up to 50MB)
- Required columns: po_number, supplier, order_date, received_date, destination
- Optional columns: notes, was_partial
- Validation: Check date formats, ensure received_date > order_date
- Duplicate handling: Update existing PO if re-uploaded
```

#### **Sample Import File**
```csv
po_number,supplier,order_date,received_date,destination
PO-2024-001,Yuasa Battery,2024-01-15,2024-05-20,burnaby
PO-2024-002,Power Systems,2024-01-20,2024-04-28,kentucky
PO-2024-003,Yuasa Battery,2024-02-01,2024-05-25,kentucky
```

#### **Import Validation Rules**
- PO number: Unique, non-empty string
- Supplier: Non-empty string, will be normalized (trim, uppercase)
- Order date: Valid date, cannot be future
- Received date: Valid date, must be ≥ order_date
- Destination: Must be 'burnaby' or 'kentucky'
- Calculate and store: actual_lead_time = received_date - order_date

### **4.2 Analytics Calculations**

#### **Per Supplier Metrics**
```python
For each supplier, calculate:
- Average lead time (mean)
- Median lead time (P50)
- Planning lead time (P95) ← PRIMARY METRIC FOR PLANNING
- Minimum lead time (fastest ever)
- Maximum lead time (slowest ever)
- Standard deviation (variability measure)
- Coefficient of variation (CV = StdDev/Mean)
- Total shipments in period
```

#### **Time Period Options**
```
Default: Last 12 months (recommended)
Options: 
- Last 6 months (recent performance)
- Last 24 months (longer-term view)
- All time (historical reference)
- Custom date range
```

#### **Reliability Score Formula**
```python
def calculate_reliability_score(supplier_stats):
    """
    0-100 score based on consistency
    """
    cv = supplier_stats['std_dev'] / supplier_stats['avg_lead_time']
    
    # Base score from consistency
    if cv < 0.10:      # <10% variation
        base_score = 95
    elif cv < 0.15:    # <15% variation  
        base_score = 85
    elif cv < 0.25:    # <25% variation
        base_score = 70
    elif cv < 0.35:    # <35% variation
        base_score = 50
    else:              # >35% variation
        base_score = 30
    
    # Adjustment for sample size
    if supplier_stats['shipment_count'] < 5:
        confidence_factor = 0.7  # Low confidence
    elif supplier_stats['shipment_count'] < 10:
        confidence_factor = 0.85
    elif supplier_stats['shipment_count'] < 20:
        confidence_factor = 0.95
    else:
        confidence_factor = 1.0
    
    return base_score * confidence_factor
```

### **4.3 Dashboard Requirements**

#### **Main Dashboard View**
```
┌─────────────────────────────────────────────┐
│ SUPPLIER PERFORMANCE DASHBOARD               │
├─────────────────────────────────────────────┤
│ Date Range: [Last 12 Months ▼] [Refresh]    │
└─────────────────────────────────────────────┘

┌─────────────┬─────────────┬─────────────┬─────────────┐
│ AVG LEAD    │ MOST        │ LEAST       │ ACTIVE      │
│ TIME        │ RELIABLE    │ RELIABLE    │ SUPPLIERS   │
│ 92 days     │ Yuasa (92%) │ PowerCo(45%)│ 12          │
└─────────────┴─────────────┴─────────────┴─────────────┘

[Supplier Performance Table]
┌──────────────┬──────┬──────┬──────┬──────┬────────┬──────┐
│ Supplier     │ Avg  │ P95  │ Min  │ Max  │ StdDev │Score │
├──────────────┼──────┼──────┼──────┼──────┼────────┼──────┤
│ Yuasa Battery│ 95d  │ 108d │ 78d  │ 125d │ ±8d    │ 92%  │
│ Power Systems│ 87d  │ 134d │ 45d  │ 156d │ ±28d   │ 45%  │
│ BattMax Co   │ 102d │ 118d │ 89d  │ 134d │ ±12d   │ 78%  │
└──────────────┴──────┴──────┴──────┴──────┴────────┴──────┘
[Export CSV]

[Lead Time Trend Chart - Line graph showing monthly average]
[Lead Time Distribution - Histogram by supplier]
```

#### **Supplier Detail View**
```
When clicking on a supplier:

YUASA BATTERY - DETAILED ANALYTICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Planning Recommendation: Use 108 days for reorder calculations

Statistics (Last 12 Months):
• Shipments analyzed: 47
• Average lead time: 95 days
• Planning lead time (P95): 108 days ← USE THIS
• Fastest delivery: 78 days
• Slowest delivery: 125 days
• Standard deviation: ±8 days
• Reliability score: 92/100 (Excellent)

By Destination:
• Burnaby: 93 days average (24 shipments)
• Kentucky: 97 days average (23 shipments)

Seasonal Pattern:
• Q1 (Jan-Mar): 98 days avg
• Q2 (Apr-Jun): 92 days avg
• Q3 (Jul-Sep): 91 days avg
• Q4 (Oct-Dec): 99 days avg

Performance Trend: [Chart showing if improving/degrading]
Recent Shipments: [Table of last 10 POs with dates]
```

### **4.4 Export & Integration**

#### **Export Formats**
```
1. Supplier Metrics CSV:
supplier,avg_lead_time,p95_lead_time,reliability_score,shipment_count
"Yuasa Battery",95,108,92,47
"Power Systems",87,134,45,23

2. Planning Parameters JSON (for system integration):
{
  "suppliers": [
    {
      "name": "Yuasa Battery",
      "planning_lead_time_days": 108,
      "reliability_score": 92,
      "use_for_safety_stock": 1.0
    }
  ]
}
```

#### **Integration with Ordering System**
```python
# API endpoint or export for reorder calculation
GET /api/supplier/{supplier_name}/planning_lead_time
Response: {
  "supplier": "Yuasa Battery",
  "planning_lead_time_days": 108,
  "confidence": "high",
  "based_on_shipments": 47,
  "last_updated": "2024-12-01"
}
```

### **4.5 Alerts & Monitoring**

#### **Automated Alerts**
```python
Alert Types:
1. Performance Degradation
   - Trigger: Lead time increased >15% vs 3-month average
   - Message: "Yuasa lead time increased from 95 to 112 days"
   
2. High Variability Warning
   - Trigger: Std deviation > 25% of average
   - Message: "PowerCo showing high variability (±28 days)"
   
3. Insufficient Data
   - Trigger: Supplier with <5 shipments in 6 months
   - Message: "Limited data for NewSupplier (3 shipments)"

4. Outlier Detection
   - Trigger: Single shipment >2x normal lead time
   - Message: "PO-2024-123 took 189 days (normal: 95)"
```

---

## **5. User Interface Requirements**

### **5.1 Navigation Structure**
```
Main Menu:
├── Dashboard (default view)
├── Upload Data
├── Supplier List
│   └── Supplier Detail
├── Settings
│   ├── Date Range
│   ├── Alert Thresholds
│   └── Export Settings
└── Reports
```

### **5.2 Responsive Design**
- Desktop: Full dashboard with charts
- Tablet: Simplified table view
- Mobile: Key metrics only

### **5.3 User Permissions**
- Admin: Upload data, modify settings, export
- Viewer: View dashboards and reports only

---

## **6. Database Schema**

```sql
-- Core shipment data
CREATE TABLE supplier_shipments (
    id SERIAL PRIMARY KEY,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    supplier VARCHAR(100) NOT NULL,
    order_date DATE NOT NULL,
    received_date DATE NOT NULL,
    destination VARCHAR(20) CHECK (destination IN ('burnaby', 'kentucky')),
    actual_lead_time INTEGER GENERATED ALWAYS AS (received_date - order_date) STORED,
    was_partial BOOLEAN DEFAULT FALSE,
    notes TEXT,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    uploaded_by VARCHAR(100)
);

-- Indexes for performance
CREATE INDEX idx_supplier ON supplier_shipments(supplier);
CREATE INDEX idx_order_date ON supplier_shipments(order_date);
CREATE INDEX idx_destination ON supplier_shipments(destination);

-- Calculated metrics (refreshed daily)
CREATE MATERIALIZED VIEW supplier_metrics AS
SELECT 
    supplier,
    COUNT(*) as shipment_count,
    AVG(actual_lead_time) as avg_lead_time,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY actual_lead_time) as median_lead_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY actual_lead_time) as p95_lead_time,
    MIN(actual_lead_time) as min_lead_time,
    MAX(actual_lead_time) as max_lead_time,
    STDDEV(actual_lead_time) as std_dev_lead_time,
    (STDDEV(actual_lead_time) / AVG(actual_lead_time)) as coefficient_variation
FROM supplier_shipments
WHERE received_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY supplier;

-- Alert history
CREATE TABLE supplier_alerts (
    id SERIAL PRIMARY KEY,
    supplier VARCHAR(100),
    alert_type VARCHAR(50),
    message TEXT,
    severity VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP
);
```

---

## **7. Success Metrics**

### **Primary KPIs (Month 3)**
- Lead time prediction accuracy: >85% within range
- Stockouts due to supplier delays: Reduce by 30%
- Excess inventory from over-planning: Reduce by 20%

### **Secondary KPIs (Month 6)**
- Suppliers with reliability scores calculated: 100%
- Average confidence in lead time planning: >80%
- Manual lead time overrides needed: <10%

### **Usage Metrics**
- Weekly active users: 3+
- Data freshness: Updated monthly minimum
- Export utilization: Used in 90% of reorder decisions

---

## **8. Implementation Timeline**

### **Phase 1: MVP (Weeks 1-2)**
- [ ] Database setup
- [ ] CSV upload functionality  
- [ ] Basic calculations (avg, min, max, P95)
- [ ] Simple table view of suppliers
- [ ] Export to CSV

### **Phase 2: Analytics (Weeks 3-4)**
- [ ] Reliability scoring algorithm
- [ ] Dashboard with charts
- [ ] Supplier detail pages
- [ ] Trend analysis

### **Phase 3: Integration (Weeks 5-6)**
- [ ] API for ordering system
- [ ] Automated alerts
- [ ] Performance tracking
- [ ] User training

### **Phase 4: Optimization (Month 2+)**
- [ ] Seasonal pattern detection
- [ ] Predictive analytics
- [ ] Automated reporting
- [ ] Mobile interface

---

## **9. Technical Requirements**

### **Technology Stack**
- Frontend: React (matching existing tool)
- Backend: Python/Node.js (matching existing)
- Database: PostgreSQL (matching existing)
- Charts: Recharts or D3.js
- Export: CSV generation, JSON API

### **Performance Requirements**
- Dashboard load: <2 seconds
- CSV import: <10 seconds for 10,000 rows
- Calculation refresh: <5 seconds
- Concurrent users: Support 5

### **Data Requirements**
- Historical data: Minimum 6 months, ideal 24 months
- Update frequency: Monthly minimum, weekly preferred
- Data retention: Keep 3 years of history

---

## **10. Risks & Mitigation**

| Risk | Probability | Impact | Mitigation |
|------|------------|---------|------------|
| Insufficient historical data | Medium | High | Start with available data, improve over time |
| Supplier name inconsistencies | High | Medium | Implement name normalization and mapping |
| Seasonal patterns not captured | Medium | Medium | Add seasonal adjustment in Phase 4 |
| Users don't trust automated metrics | Low | High | Show calculation transparency, allow overrides |

---

## **11. Out of Scope (Version 1)**

- Quality tracking by supplier
- Cost analysis and price variance
- Multi-tier supplier management
- Automated PO generation
- Supplier scorecards beyond lead time
- Integration with supplier portals
- Document management
- Communication tracking

---

## **12. Future Enhancements (Version 2)**

1. **Predictive Delays** - ML model to predict which POs will be late
2. **Supplier Negotiations** - Data package for supplier reviews
3. **Alternative Sourcing** - Suggest supplier switches for poor performers
4. **Capacity Planning** - Track supplier capacity constraints
5. **Cost Impact Analysis** - Calculate financial impact of delays

---

## **13. User Stories**

```gherkin
AS AN inventory manager
I WANT TO see actual supplier lead times
SO THAT I can set accurate reorder points

AS AN operations analyst  
I WANT TO identify unreliable suppliers
SO THAT we can address supply chain risks

AS A purchasing manager
I WANT TO export supplier metrics
SO THAT I can negotiate better terms
```

---

## **14. Acceptance Criteria**

### **Data Upload**
- ✓ Can upload CSV with 5,000+ historical records
- ✓ Validates data and shows errors clearly
- ✓ Handles duplicate PO numbers gracefully

### **Analytics**
- ✓ Calculates P95 lead time for planning
- ✓ Shows reliability score 0-100
- ✓ Updates automatically when new data uploaded

### **Integration**
- ✓ Exports planning parameters for order system
- ✓ API returns lead time for given supplier
- ✓ Metrics used in reorder calculations

---

## **15. Mockups Required**

1. Dashboard main view
2. Upload interface with validation
3. Supplier detail page
4. Alert notification design
5. Mobile responsive view

---

## **Appendix A: Sample Calculations**

```python
# Example for Yuasa Battery
Input data: 47 shipments over 12 months
Lead times: [78, 82, 85, 88, 89, 91, 92, 93, 94, 95, 95, 96...]

Calculations:
- Average: 95 days
- P95: 108 days (95% of shipments arrive within this)
- Std Dev: 8 days
- CV: 8/95 = 0.084 (8.4% variation)
- Reliability Score: 95 * 1.0 = 95 (Excellent)

Recommendation: 
"Use 108 days for planning (covers 95% of cases)"
```

---

## **Appendix B: Alert Examples**

```
🔴 HIGH: PowerCo lead time increased 35% (87→117 days)
Action: Review pending orders, consider expediting

🟡 MEDIUM: BattMax showing high variability (CV=28%)  
Action: Increase safety stock for BattMax SKUs

🟢 LOW: NewSupplier has limited history (3 shipments)
Action: Monitor closely, use conservative estimates
```

---

**Document Status:** Ready for Review  
**Next Steps:** Review with stakeholders → Approve → Begin Phase 1 development