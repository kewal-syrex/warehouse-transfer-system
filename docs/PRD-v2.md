# Product Requirements Document (PRD) v2.0
## Warehouse Transfer Planning Tool - Comprehensive Requirements

### Version: 2.0
### Date: January 2025
### Status: In Development

---

## 1. Executive Summary

### 1.1 Vision
Transform warehouse transfer planning from a time-consuming, error-prone Excel process into an intelligent, automated system that maximizes inventory efficiency while minimizing stockouts.

### 1.2 Mission Statement
Build a web-based tool that provides accurate, stockout-corrected transfer recommendations for optimizing inventory allocation between Burnaby (Canada) and Kentucky (US) warehouses.

### 1.3 Success Metrics
- **Time Savings**: Reduce transfer planning from 4+ hours to <30 minutes
- **Stockout Reduction**: Decrease stockout incidents by 50%
- **Inventory Efficiency**: Improve inventory turnover by 20%
- **Data Accuracy**: Eliminate human calculation errors
- **User Adoption**: Achieve >90% preference over Excel

---

## 2. Business Context

### 2.1 Current State Problems
1. **Hidden Demand**: Monthly sales don't reflect true demand during stockouts
2. **Limited Visibility**: Cannot view historical CA vs US sales breakdown
3. **Manual Calculations**: 2000+ SKUs require hours of Excel work
4. **Human Error**: Formula mistakes and copy-paste errors
5. **Reactive Planning**: No systematic approach to safety stock
6. **Data Fragmentation**: Multiple Excel tabs with VLOOKUP dependencies

### 2.2 Business Impact
- **Revenue Loss**: Stockouts = lost sales (unquantified currently)
- **Cash Flow**: Excess inventory ties up working capital
- **Labor Cost**: Manual process consumes valuable staff time  
- **Customer Satisfaction**: Stockouts affect service levels
- **Operational Stress**: Firefighting mode vs strategic planning

### 2.3 Stakeholders
- **Primary User**: Inventory/Purchasing Manager (Arjay)
- **Secondary Users**: Purchasing staff, warehouse management
- **Affected Departments**: Sales, finance, logistics, customer service

---

## 3. Product Requirements

### 3.1 Core Functional Requirements

#### 3.1.1 Stockout Detection & Correction
**Priority: Critical**
- **FR-001**: Detect when SKUs have zero inventory
- **FR-002**: Identify ongoing vs closed stockout periods
- **FR-003**: Calculate availability rate for each SKU by month
- **FR-004**: Apply demand correction using minimum 30% availability factor
- **FR-005**: Handle edge cases (new SKUs, no history, seasonal items)
- **FR-006**: Visual indicators for stockout-adjusted items ("SO" badge)

#### 3.1.2 Historical Data Management
**Priority: Critical**
- **FR-007**: Store monthly sales data with stockout days count
- **FR-008**: Maintain monthly sales by warehouse (CA/US breakdown)
- **FR-009**: Track inventory levels by warehouse over time
- **FR-010**: Record pending/in-transit inventory with arrival dates
- **FR-011**: Preserve transfer history for performance analysis

#### 3.1.3 Transfer Calculation Engine
**Priority: Critical**
- **FR-012**: Calculate optimal transfer quantities using corrected demand
- **FR-013**: Apply ABC-XYZ classification for coverage targets
- **FR-014**: Round to appropriate transfer multiples (25/50/100)
- **FR-015**: Respect minimum transfer quantities (10 units)
- **FR-016**: Ensure sufficient Burnaby inventory remains
- **FR-017**: Account for pending arrivals in calculations

#### 3.1.4 Data Import/Export
**Priority: High**
- **FR-018**: Import Excel files with inventory and sales data
- **FR-019**: Validate data quality and flag inconsistencies
- **FR-020**: Export transfer orders to Excel format
- **FR-021**: Support CSV import/export as alternative
- **FR-022**: Bulk update functionality for inventory snapshots

### 3.2 User Interface Requirements

#### 3.2.1 Dashboard
**Priority: High**
- **UI-001**: Display key metrics (critical SKUs, low stock, transfer value)
- **UI-002**: Show data freshness indicators
- **UI-003**: Alert system for urgent items
- **UI-004**: Quick action buttons (refresh, import, plan transfer)
- **UI-005**: Recent activity feed

#### 3.2.2 Transfer Planning Interface
**Priority: Critical**
- **UI-006**: Sortable/filterable table with all recommendations
- **UI-007**: Color-coded urgency levels (red/yellow/green)
- **UI-008**: Editable transfer quantities with real-time validation
- **UI-009**: Bulk selection and modification capabilities
- **UI-010**: SKU detail drill-down with sales history charts
- **UI-011**: Column visibility controls
- **UI-012**: Search functionality across all fields

#### 3.2.3 Import/Export Interface
**Priority: Medium**
- **UI-013**: Drag-and-drop file upload
- **UI-014**: Import progress indicators
- **UI-015**: Data validation results display
- **UI-016**: Export options with format selection
- **UI-017**: Preview before final import

### 3.3 Technical Requirements

#### 3.3.1 Performance
**Priority: High**
- **TR-001**: Handle 4000+ SKUs without lag
- **TR-002**: Generate recommendations in <5 seconds
- **TR-003**: Export Excel files in <10 seconds
- **TR-004**: Support concurrent users (up to 5)
- **TR-005**: Database queries optimized for sub-second response

#### 3.3.2 Data Management
**Priority: High**
- **TR-006**: MySQL database with proper indexing
- **TR-007**: Data backup and recovery procedures
- **TR-008**: Audit trail for all changes
- **TR-009**: Data retention policies
- **TR-010**: Data validation and cleaning routines

#### 3.3.3 Integration
**Priority: Medium**
- **TR-011**: API endpoints for future OMS integration
- **TR-012**: Bulk data processing capabilities
- **TR-013**: Email notification system (future)
- **TR-014**: Export to common formats (Excel, CSV, PDF)

---

## 4. Detailed Feature Specifications

### 4.1 Stockout Correction Algorithm

#### Input Data
- Daily sales by SKU and warehouse
- Daily inventory levels
- Stockout events (start/end dates)

#### Processing Logic
```python
def correct_demand(sku_id, month):
    availability_rate = calculate_availability(sku_id, month)
    actual_sales = get_monthly_sales(sku_id, month)
    
    if availability_rate < 1.0 and actual_sales > 0:
        correction_factor = max(availability_rate, 0.3)  # 30% floor
        corrected_demand = actual_sales / correction_factor
    else:
        corrected_demand = actual_sales
    
    return corrected_demand
```

#### Special Cases
- **Currently Out of Stock**: Use historical pre-stockout demand
- **Ongoing Stockouts**: Count days only up to current date
- **New SKUs**: No correction until sufficient history
- **Seasonal Items**: Apply seasonal factors before correction

### 4.2 ABC-XYZ Classification

#### ABC Analysis (Value-based)
- **A Items**: 80% of total value, 4-6 months coverage
- **B Items**: 15% of total value, 3-4 months coverage  
- **C Items**: 5% of total value, 1-2 months coverage

#### XYZ Analysis (Variability-based)
- **X Items**: CV < 0.25 (stable demand)
- **Y Items**: CV 0.25-0.50 (variable demand)
- **Z Items**: CV > 0.50 (irregular demand)

#### Coverage Matrix
| Class | Coverage (Months) | Service Level |
|-------|------------------|---------------|
| AX    | 4               | 99%           |
| AY    | 5               | 97.5%         |
| AZ    | 6               | 95%           |
| BX    | 3               | 95%           |
| BY    | 4               | 92.5%         |
| BZ    | 5               | 90%           |
| CX    | 2               | 85%           |
| CY    | 2               | 80%           |
| CZ    | 1               | 75%           |

### 4.3 Transfer Multiple Logic

#### Product Categories
- **Chargers/Cables**: 25-unit multiples
- **Standard Items**: 50-unit multiples
- **High-Volume Items**: 100-unit multiples
- **Special Cases**: Custom multiples per SKU

#### Rounding Rules
```python
def round_to_multiple(quantity, multiple):
    if quantity < 10:  # Minimum transfer
        return 0
    return math.ceil(quantity / multiple) * multiple
```

### 4.4 Data Model

#### Core Tables
```sql
-- SKU Master Data
skus (
    sku_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255),
    supplier VARCHAR(100),
    status ENUM('Active', 'Death Row', 'Discontinued'),
    cost_per_unit DECIMAL(10,2),
    transfer_multiple INT DEFAULT 50,
    abc_code CHAR(1),
    xyz_code CHAR(1)
);

-- Current Inventory Levels
inventory_current (
    sku_id VARCHAR(50) PRIMARY KEY,
    burnaby_qty INT DEFAULT 0,
    kentucky_qty INT DEFAULT 0,
    last_updated TIMESTAMP
);

-- Monthly Sales History with Stockout Tracking
monthly_sales (
    year_month VARCHAR(7), -- '2024-01'
    sku_id VARCHAR(50),
    burnaby_sales INT DEFAULT 0,
    kentucky_sales INT DEFAULT 0,
    burnaby_stockout_days INT DEFAULT 0,
    kentucky_stockout_days INT DEFAULT 0,
    PRIMARY KEY (year_month, sku_id)
);

-- Optional: Individual Stockout Dates (if tracking specific dates)
stockout_dates (
    sku_id VARCHAR(50),
    warehouse ENUM('burnaby', 'kentucky'),
    stockout_date DATE,
    PRIMARY KEY (sku_id, warehouse, stockout_date)
);

-- Pending Inventory
pending_inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(50),
    quantity INT,
    destination ENUM('burnaby', 'kentucky'),
    order_date DATE,
    expected_arrival DATE,
    order_type ENUM('supplier', 'transfer')
);
```

---

## 5. User Stories & Acceptance Criteria

### 5.1 Epic 1: Stockout-Aware Planning

#### US-001: As an inventory manager, I want to see corrected demand that accounts for stockouts
**Acceptance Criteria:**
- [ ] System detects when SKUs have zero inventory
- [ ] Demand is adjusted upward based on availability rate
- [ ] Minimum 30% availability factor prevents overcorrection
- [ ] Visual indicator shows which items have been adjusted
- [ ] Can drill down to see original vs corrected demand

#### US-002: As an inventory manager, I want to prioritize currently out-of-stock items
**Acceptance Criteria:**
- [ ] Out-of-stock items appear at top of recommendation list
- [ ] Shows number of days out of stock
- [ ] Uses historical demand for calculations
- [ ] Applies urgency multiplier for extended stockouts (>7 days)
- [ ] Clear visual differentiation from other items

### 5.2 Epic 2: Historical Visibility

#### US-003: As an inventory manager, I want to see CA vs US sales trends
**Acceptance Criteria:**
- [ ] Dashboard shows sales breakdown by warehouse
- [ ] Historical charts for individual SKUs
- [ ] Monthly, quarterly, and annual views
- [ ] Exportable data for further analysis
- [ ] Filter by SKU status, supplier, or category

#### US-004: As an inventory manager, I want to track transfer performance
**Acceptance Criteria:**
- [ ] Compare recommended vs actual transfer quantities
- [ ] Track service level improvements post-transfer
- [ ] Identify SKUs that consistently need adjustment
- [ ] Performance metrics by ABC-XYZ classification
- [ ] Trend analysis over time

### 5.3 Epic 3: Efficient Operations

#### US-005: As an inventory manager, I want to complete transfer planning in under 30 minutes
**Acceptance Criteria:**
- [ ] One-click import of current inventory data
- [ ] Automatic calculation of all recommendations
- [ ] Quick filtering to focus on urgent items
- [ ] Bulk quantity adjustments
- [ ] Single-click export to Excel

#### US-006: As an inventory manager, I want confidence in my transfer decisions
**Acceptance Criteria:**
- [ ] Clear rationale for each recommendation
- [ ] Warning indicators for risky decisions
- [ ] Historical context for unusual recommendations
- [ ] Simulation of "what-if" scenarios
- [ ] Validation of sufficient Burnaby inventory

---

## 6. Non-Functional Requirements

### 6.1 Usability
- **NFR-001**: Learning curve <2 hours for Excel-proficient users
- **NFR-002**: All actions achievable within 3 clicks
- **NFR-003**: Responsive design for laptop/tablet use
- **NFR-004**: Keyboard shortcuts for power users
- **NFR-005**: Context-sensitive help system

### 6.2 Reliability
- **NFR-006**: 99.5% uptime during business hours
- **NFR-007**: Data backup every 24 hours
- **NFR-008**: Recovery time <1 hour for system failures
- **NFR-009**: Input validation prevents data corruption
- **NFR-010**: Graceful error handling with user-friendly messages

### 6.3 Security
- **NFR-011**: Access controls by user role
- **NFR-012**: Audit trail for all data modifications
- **NFR-013**: Secure data transmission (HTTPS)
- **NFR-014**: No sensitive data in browser cache
- **NFR-015**: Regular security updates

### 6.4 Maintainability
- **NFR-016**: Code documentation for all business logic
- **NFR-017**: Modular architecture for easy updates
- **NFR-018**: Configuration-driven parameters
- **NFR-019**: Automated testing coverage >80%
- **NFR-020**: Performance monitoring and alerting

---

## 7. Constraints & Assumptions

### 7.1 Technical Constraints
- Must run on existing Windows infrastructure
- No budget for cloud services or premium software
- XAMPP/MySQL database limitations
- Single-user deployment initially

### 7.2 Business Constraints
- Cannot modify OMS system directly
- Monthly data update cycle cannot change immediately
- Manual stockout tracking until integration available
- Excel export format must match current templates

### 7.3 Assumptions
- Business rules remain stable during development
- Current Excel data is reasonably accurate
- User is willing to provide feedback during development
- Transfer multiples are consistent industry practice

---

## 8. Future Enhancements (Out of Scope v1.0)

### 8.1 Phase 2 Candidates
- Direct OMS integration via API
- Automated daily data sync
- Email alerts for critical stockouts
- Multi-user access with role permissions
- Mobile responsive interface

### 8.2 Phase 3 Possibilities
- Machine learning demand forecasting
- Seasonal adjustment algorithms
- Multi-warehouse optimization (beyond 2 warehouses)
- Supplier performance integration
- Cost optimization calculations

### 8.3 Advanced Features
- Real-time inventory tracking
- Automated transfer execution
- Customer demand visibility
- Supplier lead time optimization
- Transportation cost modeling

---

## 9. Risk Assessment

### 9.1 Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Database performance with 4K SKUs | Medium | Low | Proper indexing, query optimization |
| Excel import reliability | High | Medium | Robust validation, error handling |
| Data accuracy issues | High | Medium | Multiple validation layers |
| Browser compatibility | Medium | Low | Standard web technologies |

### 9.2 Business Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| User adoption resistance | High | Medium | Training, gradual rollout |
| Business rule changes | Medium | Medium | Configurable parameters |
| Data source changes | High | Low | Flexible import system |
| Scaling beyond capacity | Medium | High | Performance monitoring |

---

## 10. Success Metrics & KPIs

### 10.1 Operational Metrics
- **Time to Plan**: Target <30 minutes (from current 4+ hours)
- **Stockout Days**: Reduce by 50% within 6 months
- **Forecast Accuracy**: Improve by 25% (measured quarterly)
- **User Satisfaction**: >4.0/5.0 rating
- **System Uptime**: >99.5% during business hours

### 10.2 Business Metrics
- **Inventory Turnover**: Improve by 20% annually
- **Service Level**: Achieve 95% for A-items, 90% for B-items
- **Cash Flow**: Reduce average inventory investment by 15%
- **Customer Complaints**: Reduce stockout-related complaints by 60%

### 10.3 Technical Metrics
- **Response Time**: <2 seconds for all calculations
- **Data Quality**: <1% error rate in imports
- **Export Speed**: <10 seconds for full dataset
- **Bug Rate**: <5 bugs per month post-launch

---

## 11. Acceptance Criteria Summary

The system is ready for production when:
1. All critical functional requirements (FR-001 through FR-017) are complete
2. Performance targets are met with full 4K SKU dataset
3. User can complete full transfer planning cycle in <30 minutes
4. Data import/export works reliably with existing Excel formats
5. All high-priority UI requirements are implemented
6. User acceptance testing passes with >90% satisfaction
7. Documentation is complete for end users

---

## 12. Appendix

### 12.1 Glossary
- **ABC Analysis**: Classification by value (Annual sales × unit cost)
- **Coverage**: Months of inventory based on expected demand
- **CV (Coefficient of Variation)**: Standard deviation / mean
- **Lead Time**: Time from order placement to receipt
- **Safety Stock**: Buffer inventory to prevent stockouts
- **Service Level**: Percentage of demand met from stock
- **Stockout**: When inventory reaches zero
- **Transfer Multiple**: Standard quantities for shipping efficiency
- **XYZ Analysis**: Classification by demand variability

### 12.2 References
- Original PRD.md (v1.0)
- Stockout handling refinements (stockout.md)
- Inventory update guidelines (inventory.md)
- Forecasting methodology (forecasting-transcript.md)
- Inventory management principles (inventory-management.md)

### 12.3 Change Log
| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2025 | Initial PRD draft |
| 2.0 | Jan 2025 | Comprehensive requirements, user stories, technical details |

---

*This PRD is a living document and will be updated as requirements evolve during development.*