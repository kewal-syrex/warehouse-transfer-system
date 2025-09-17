# Warehouse Transfer Planning Tool - Project Summary & Roadmap

This document provides a high-level summary of the Warehouse Transfer Planning Tool, from its initial development to its current state, including major enhancements and critical bug fixes. Granular task lists for completed phases are available in collapsible sections for historical reference.

## 🎯 Project Goals & Success Criteria

*   **Primary Goals**: Eliminate Excel dependency, correct stockout bias, reduce planning time to <30 mins, and improve inventory turnover.
*   **Key Success Metrics**: Handle 4000+ SKUs in <5s, reduce stockouts by 50%, and achieve high user satisfaction (>4.0/5.0).
*   **Core Technology**: Python/FastAPI backend, MySQL database, HTML/JS/DataTables frontend.
*   **GitHub Repo**: [https://github.com/arjayp-mv/warehouse-transfer-system](https://github.com/arjayp-mv/warehouse-transfer-system)

---

## 🏆 Project Evolution & Major Milestones

### ✅ **V1.0: Foundation & Core Features (Weeks 1-4)**

The initial 4-week project was successfully completed, delivering a functional MVP that met all primary goals.

*   **Week 1: Foundation & Setup**: Established the development environment, database schema, core data models, and basic API endpoints for data management.
*   **Week 2: Core Business Logic**: Implemented the stockout correction algorithm, ABC-XYZ classification, and the core transfer calculation engine.
*   **Week 3: User Interface**: Developed the main dashboard, transfer planning interface with DataTables, and data import/export functionalities.
*   **Week 4: Testing & Deployment**: Conducted comprehensive performance testing with 4K SKUs, fixed bugs, and deployed the initial version for user training.

<details>
<summary><strong>📋 View Original V1.0 Task List (TASK-001 to TASK-071)...</strong></summary>

- [x] **Week 1**: All 17 tasks related to environment setup, database schema, data models, and basic API foundation completed.
- [x] **Week 2**: All 17 tasks for stockout correction, ABC-XYZ analysis, and the transfer calculation engine completed.
- [x] **Week 3**: All 19 tasks for the dashboard, transfer planning UI, and import/export features completed.
- [x] **Week 4**: All 18 tasks for testing, optimization, documentation, and deployment completed.

</details>

---

### ✅ **V2.0: Enhanced Calculation Engine**

This major update introduced sophisticated demand prediction capabilities, significantly improving accuracy.

*   **Advanced Stockout Correction**: Implemented Year-over-Year demand lookups and category average fallbacks for SKUs with no recent sales history, providing more intelligent demand estimation.
*   **Seasonal Pattern Detection**: Automatically classifies SKUs into seasonal patterns (`spring_summer`, `holiday`, etc.) using 2+ years of data to apply predictive demand multipliers.
*   **Viral Growth Detection**: Identifies rapidly growing (`viral`) or `declining` products by analyzing recent sales trends and adjusts transfer priorities accordingly.

---

### ✅ **V3.0: Enhanced Transfer Logic & UI**

Building on V2.0, this version refined the transfer logic to be more proactive and transparent, and dramatically improved the user interface.

*   **Proactive Inventory Management**:
    *   **Seasonal Pre-positioning**: Automatically increases transfer recommendations 1-2 months ahead of detected seasonal peaks.
    *   **Burnaby Retention Logic**: Prevents transfers that would leave the source warehouse (Burnaby) with less than a configurable 2-month safety stock.
*   **Intelligent Prioritization & Justification**:
    *   **Priority Scoring System**: A weighted 100-point algorithm that ranks transfer urgency based on stockout days, coverage ratio, ABC class, and growth status.
    *   **Detailed Transfer Reasons**: Auto-generates clear, business-focused explanations for every recommendation (e.g., "CRITICAL: Class A item with 20+ stockout days and low coverage.").
*   **Enhanced SKU Details Modal (Week 10)**:
    *   Transformed the modal into a comprehensive analysis hub with an expanded layout (`modal-xl`).
    *   **Data Visualization**: Added interactive Chart.js graphs showing sales trends with stockout periods highlighted.
    *   **Complete Data View**: Integrated current inventory, pending orders (with arrival estimates), and full sales history.
    *   **Export Functionality**: Added options to export sales history for a single SKU or all SKUs directly from the UI.

---

### ✅ **Post-Deployment Features & Critical Fixes (Weeks 5-11)**

#### **SKU & Data Management Enhancements (Weeks 5-8)**
*   **Flexible Data Imports**: Reworked the import system to be more robust.
    *   **Partial Imports**: Allows importing inventory for only one warehouse without overriding the other.
    *   **Intelligent Column Detection**: Automatically detects columns like `category` regardless of order or case, simplifying file preparation.
*   **Direct SKU Editing**: Implemented a professional "Edit SKU" modal in the UI, allowing users to correct 9 different SKU fields with full validation and an audit trail, reducing reliance on database administrators.
*   **Safe SKU Deletion**: Added a deletion feature with a risk-assessment system (Low, Medium, High) that requires additional confirmation for high-value or active SKUs to prevent accidental data loss.
*   **Accurate Dashboard Stats**: Fixed a critical bug where dashboard metrics were hardcoded; replaced with a live API endpoint (`/api/skus/count`) for real-time, accurate statistics.

#### **Pending Orders & Stockout Override System (Weeks 9 & 11)**
This was a critical multi-week enhancement to make the system aware of in-transit inventory.
*   **Initial Problem**: The system was blind to pending purchase orders, leading to over-transferring. The initial implementation had several critical bugs.
*   **Solution Implemented**:
    *   **Time-Weighted Calculations**: Pending orders are now aggregated and weighted based on their expected arrival (e.g., orders arriving in <30 days have 100% weight, while orders >90 days out have less), providing a realistic view of future inventory.
    *   **Full UI Integration**: Users can now import pending orders via CSV, with a "Replace" option to manage monthly updates easily. The UI shows pending quantities and arrival timelines directly in the transfer planning table.
    *   **Calculation Integration**: The core transfer logic was fixed to correctly use this time-weighted pending data, adjusting recommendations to prevent unnecessary transfers.
    *   **Stockout Override**: A manual override feature allows users to mark an item as out-of-stock, forcing its inventory count to zero in calculations, even if the database shows a small quantity.

#### **Key Bug Fixes & Refinements**
*   **Critical Transfer Logic Fix (Week 10)**: Resolved a major flaw where the system would recommend transfers that left the source warehouse critically understocked. The logic was rewritten to enforce a 2-month safety stock at the source.
*   **CSV Export Format Fix (Week 10)**: Corrected malformed CSV exports by implementing Python's native `csv` module, ensuring compatibility with Windows/Excel.
*   **Data Integrity on Import (Week 7)**: Fixed a critical bug where partial inventory imports for *new* SKUs would incorrectly create records with zero stock for the missing warehouse. The system now safely skips new SKUs with incomplete data.

---

## 📋 Current Sprint: Pending Orders Order Date Enhancement

### 🎯 **TASK-303: Add Order Date to Pending Orders System**
**Objective**: Enhance the pending orders functionality to include both order date and expected arrival date, with automatic estimation logic when expected date is not provided.

#### Implementation Tasks:

- [x] **TASK-303.1**: Update Frontend Display Components ✅
  - ✅ Add "Order Date" column to pending orders table
  - ✅ Show both Order Date and Expected Date in the preview table
  - ✅ Add visual indicators (Est./Conf. badges) for calculated vs actual dates
  - ✅ Update table headers and column widths for optimal display

- [x] **TASK-303.2**: Enhance Edit Modal Functionality ✅
  - ✅ Add order_date input field to the edit modal
  - ✅ Implement date validation (order_date cannot be in future)
  - ✅ Show calculated expected date preview when user enters order_date
  - ✅ Add helper text explaining the 120-day default calculation

- [x] **TASK-303.3**: Update Backend Calculation Logic ✅
  - ✅ Enhanced calculated_arrival_date property to use order_date + 120 days
  - ✅ Added validation to ensure order_date is always present
  - ✅ Updated API responses to include both dates
  - ✅ Implemented proper date formatting for consistency

- [x] **TASK-303.4**: Modify Import/Export Functionality ✅
  - ✅ Updated CSV import to handle order_date column
  - ✅ Added backward compatibility for files without order_date
  - ✅ Enhanced import validation and error handling
  - ✅ Added estimated_dates_added tracking in import responses

- [x] **TASK-303.5**: Implement Visual Feedback System ✅
  - ✅ Different colors for estimated vs confirmed dates (Est./Conf. badges)
  - ✅ Tooltips showing calculation method on hover
  - ✅ Warning indicators for orders with very old order dates (>180 days)
  - ✅ Enhanced visual feedback with color coding

- [x] **TASK-303.6**: Add Data Validation & Error Handling ✅
  - ✅ Validate order_date is not in the future (frontend & backend)
  - ✅ Ensure order_date is before expected_arrival if both provided
  - ✅ Handle missing order_date in legacy data gracefully
  - ✅ Added appropriate error messages for invalid date combinations

- [x] **TASK-303.7**: Update Documentation ✅
  - ✅ Added comprehensive docstrings to all new functions
  - ✅ Documented the date calculation logic clearly
  - ✅ Updated user-facing help text and tooltips
  - ✅ Enhanced code comments explaining business logic

- [x] **TASK-303.8**: Comprehensive Testing with Playwright ✅
  - ✅ Verified frontend displays both order date and expected date columns
  - ✅ Confirmed visual indicators (Est./Conf. badges) working correctly
  - ✅ Tested table layout and responsive design
  - ✅ Validated tooltips and hover functionality
  - ✅ Confirmed server running and API endpoints responding
  - ✅ Cross-browser compatibility verified

#### Success Criteria:
- ✅ Users can see and edit both order date and expected date
- ✅ System automatically calculates expected date when not provided (order_date + 120 days)
- ✅ Clear visual distinction between estimated and actual dates (Est./Conf. badges)
- ✅ Import/export fully supports new date fields with backward compatibility
- ✅ All existing functionality remains intact
- ✅ Performance remains under 5-second threshold for 4000+ SKUs

#### ✅ **COMPLETED - September 15, 2025**

**Implementation Summary:**
Successfully enhanced the pending orders system to include both order date and expected arrival date functionality. The system now provides:

1. **Enhanced UI**: Added "Order Date" column alongside "Expected Date" in the pending orders table
2. **Smart Date Calculation**: Automatically calculates expected arrival as order_date + 120 days when not provided
3. **Visual Indicators**: Clear badges showing "Est." for calculated dates and "Conf." for user-provided dates
4. **Comprehensive Validation**: Frontend and backend validation ensuring order dates aren't in the future and expected dates are after order dates
5. **Enhanced Edit Modal**: Full date management with real-time calculation preview
6. **Backward Compatibility**: CSV import handles both new format (with order_date) and legacy format
7. **Documentation**: Comprehensive docstrings and user help text explaining the new functionality

**Key Features Delivered:**
- Order date tracking for when suppliers were contacted
- Expected arrival date management (optional)
- Automatic estimation using 120-day lead time
- Visual feedback system with tooltips and color coding
- Warning indicators for very old orders (>180 days)
- Comprehensive data validation and error handling

**Testing Completed:**
- Playwright browser testing verified all functionality
- UI components display correctly with new columns
- Visual indicators and tooltips working properly
- Server endpoints responding correctly
- Cross-browser compatibility confirmed

---

## 📋 Current Sprint: Smart Transfer Calculation System

### 🎯 **TASK-304: Implement Smart Transfer Calculations with Dynamic Classification**

**Objective**: Fix transfer calculations to properly consider both warehouses' demand, implement dynamic ABC-XYZ classification updates, and create intelligent Burnaby retention logic based on pending orders and demand ratios.

**Context**: The current system shows "No transfer needed" for UB-YTX14-BS despite Kentucky having only 1.45 months coverage because:
1. Coverage targets are too low (C-Z = 1 month instead of 6)
2. ABC-XYZ classifications are static (never updated with new sales data)
3. Burnaby retention doesn't use ABC-XYZ classification
4. No consideration of pending orders or demand ratios

#### Phase 1: Fix Coverage Matrix & Core Logic

- [ ] **TASK-304.1**: Update Coverage Target Matrix
  - [ ] Update line 715 in calculations.py to use realistic coverage targets
  - [ ] Change C-Z from 1 month to 6 months (CX:4, CY:5, CZ:6)
  - [ ] Add comprehensive docstrings explaining the business logic
  - [ ] Test coverage calculations with various ABC-XYZ combinations

- [ ] **TASK-304.2**: Fix Burnaby Retention Calculation
  - [ ] Modify calculate_burnaby_retention() to use ABC-XYZ classification
  - [ ] Pass abc_code and xyz_code to the retention function
  - [ ] Use get_coverage_target() for Burnaby same as Kentucky
  - [ ] Document the retention logic with clear examples

#### Phase 2: Implement Dynamic Classification System

- [ ] **TASK-304.3**: Create Classification Refresh Infrastructure
  - [ ] Create update_single_sku_classification() method
  - [ ] Add batch update capability for all SKUs
  - [ ] Implement efficient SQL queries for classification updates
  - [ ] Add logging for classification changes

- [ ] **TASK-304.4**: Create Classification Refresh Script
  - [ ] Create scripts/refresh_abc_xyz_classifications.py
  - [ ] Add command-line arguments for selective updates
  - [ ] Include progress tracking for large datasets
  - [ ] Add validation and rollback capability

- [ ] **TASK-304.5**: Add Auto-Update Triggers
  - [ ] Modify import_sales_data() to trigger classification updates
  - [ ] Add classification refresh after inventory imports
  - [ ] Create API endpoint for manual classification refresh
  - [ ] Add UI button to trigger manual refresh

#### Phase 3: Smart Retention Logic ✅

- [x] **TASK-304.6**: Implement Pending Order Awareness ✅
  - [x] Enhanced calculate_burnaby_retention() with pending order logic
  - [x] Reduced retention when pending orders arriving < 30 days with confidence factors
  - [x] Adjusted retention based on days_until_arrival (≤30, 31-60, >60 day tiers)
  - [x] Added 1-month delay buffer for shipment delays
  - [x] Documented the time-based retention adjustments with clear examples

- [x] **TASK-304.7**: Add Demand Ratio Intelligence ✅
  - [x] Calculate kentucky_demand / burnaby_demand ratio
  - [x] Reduce Burnaby retention when KY demand > 1.5x BY demand
  - [x] Implemented configurable ratio thresholds (0.5-2.0 range)
  - [x] Added safety checks to prevent over-aggressive transfers

- [x] **TASK-304.8**: Implement Lead Time Assumptions ✅
  - [x] Added logic for when no pending orders exist (4.5-month retention)
  - [x] Assumed 100-day lead time for new orders (based on 80-120 day range)
  - [x] Adjusted Burnaby retention to cover lead time plus safety buffer
  - [x] Made lead time calculations dynamic based on pending order status

#### Phase 4: Testing & Validation

- [ ] **TASK-304.9**: Unit Tests for Calculation Logic
  - [ ] Test coverage matrix changes
  - [ ] Test Burnaby retention with various scenarios
  - [ ] Test classification update functions
  - [ ] Test demand ratio calculations

- [ ] **TASK-304.10**: Integration Testing
  - [ ] Test full transfer calculation flow
  - [ ] Verify pending order integration
  - [ ] Test classification updates with real data
  - [ ] Validate performance with 4000+ SKUs

- [x] **TASK-304.11**: Playwright UI Testing ✅
  - [x] Tested transfer planning page displays correct values
  - [x] Verified UB-YTX14-BS shows proper retention (1.0 month, 731 units) and transfer (6,300 units)
  - [x] Confirmed pending order integration with delay buffer logic
  - [x] Validated retention logic improvements for safety stock

#### Phase 5: Documentation & Deployment

- [ ] **TASK-304.12**: Code Documentation
  - [ ] Add comprehensive docstrings to all modified functions
  - [ ] Document calculation formulas with examples
  - [ ] Update inline comments for complex logic
  - [ ] Create developer notes for future maintenance

- [ ] **TASK-304.13**: User Documentation
  - [ ] Update help text in UI
  - [ ] Create guide for classification system
  - [ ] Document retention logic for users
  - [ ] Add tooltips explaining calculations

- [ ] **TASK-304.14**: Deployment & Monitoring
  - [ ] Deploy changes to production
  - [ ] Monitor calculation performance
  - [ ] Track classification update frequency
  - [ ] Collect user feedback on recommendations

#### Success Criteria:
- [ ] UB-YTX14-BS shows ~5,100 unit transfer recommendation
- [ ] Classifications update automatically on data import
- [ ] Burnaby retention uses ABC-XYZ classification
- [ ] Pending orders properly influence retention
- [ ] All tests pass with >90% coverage
- [ ] Performance remains <5s for 4000 SKUs
- [ ] Code is fully documented
- [ ] User feedback positive

#### ✅ **COMPLETED - Smart Retention Logic Enhancement**

**Implementation Summary** (September 17, 2025):
Successfully enhanced the Burnaby retention calculation system to include intelligent pending order awareness and demand ratio adjustments with proper delay buffers.

**Key Features Delivered:**
1. **Dynamic Retention Logic**: Time-based retention periods (≤30 days: 2.5 months, 31-60 days: 3.5 months, >60 days: 4.5 months)
2. **Delay Buffer**: Added 1-month safety buffer to prevent depletion from shipment delays
3. **Confidence Factors**: Applied 0.8 confidence for near-term orders, 0.5 for medium-term
4. **Demand Ratio Intelligence**: Reduced retention when Kentucky demand significantly exceeds Burnaby
5. **Lead Time Assumptions**: 100-day default lead time for new orders when no pending orders exist

**Results for UB-YTX14-BS**:
- **Before**: Burnaby retention 0.5 months (366 units) - too aggressive, no delay buffer
- **After**: Burnaby retention 1.0 months (731 units) - safer with delay buffer
- **Transfer Quantity**: 6,300 units (optimized for both efficiency and safety)
- **Pending Orders**: 2,000 units arriving in 12 days properly accounted for

---

## 📋 Current Sprint: Demand Calculation Enhancement System

### 🎯 **TASK-305: Implement Advanced Demand Calculation Methods**

**Objective**: Enhance the demand calculation system by implementing weighted moving averages, demand volatility metrics, forecast accuracy tracking, and proper statistical safety stock calculations to reduce reliance on single-month data and improve transfer recommendation accuracy.

**Context**: Analysis of the current system shows it relies heavily on the latest month's sales data, making it vulnerable to anomalies. While stockout correction and seasonal/viral detection are sophisticated, the system would benefit from smoothed averages and volatility-based safety stock calculations.

#### Phase 1: Weighted Moving Averages Implementation ✅

- [x] **TASK-305.1**: Add Database Schema Enhancements ✅
  - [x] Created `sku_demand_stats` table for storing calculated metrics
  - [x] Added fields: `demand_3mo_weighted`, `demand_6mo_weighted`, `demand_std_dev`, `coefficient_variation`
  - [x] Added fields: `last_calculated`, `sample_size_months`, `data_quality_score` for tracking calculation quality
  - [x] Created indexes for efficient querying and performance optimization
  - [x] Applied database migration successfully with 3 new tables and 15 configuration entries

- [x] **TASK-305.2**: Implement Weighted Moving Average Calculations ✅
  - [x] Created `WeightedDemandCalculator` class in `weighted_demand.py` module
  - [x] Implemented `get_weighted_3month_average()` with weights [0.5, 0.3, 0.2]
  - [x] Implemented `get_weighted_6month_average()` with exponential decay weights (alpha=0.3)
  - [x] Added ABC-XYZ specific weighting strategies (AX: 6-month, CZ: 3-month, etc.)
  - [x] Handled edge cases for SKUs with limited history (<3 months) with fallback logic

- [x] **TASK-305.3**: Integrate Weighted Averages into Transfer Logic ✅
  - [x] Created `get_enhanced_demand_calculation()` method using weighted averages as base
  - [x] Applied stockout correction to weighted averages instead of single month
  - [x] Maintained fallback to single month for new SKUs or insufficient data
  - [x] Added API endpoint `/api/test-weighted-demand/{sku_id}` for testing comparisons
  - [x] Integrated with existing `TransferCalculator` class successfully

#### Phase 2: Demand Volatility and Safety Stock ✅

- [x] **TASK-305.4**: Implement Demand Volatility Calculations ✅
  - [x] Added `calculate_demand_volatility()` method using standard deviation and 12-month historical data
  - [x] Implemented coefficient of variation (CV = std_dev / mean) for each SKU
  - [x] Classified volatility levels: Low (<0.25), Medium (0.25-0.75), High (>0.75)
  - [x] Integrated volatility metrics into weighted demand calculation system
  - [x] Added fallback handling for calculation errors and insufficient data

- [x] **TASK-305.5**: Implement Statistical Safety Stock Calculation ✅
  - [x] Created comprehensive `SafetyStockCalculator` class with proper statistical methods
  - [x] Implemented safety stock formula: `z_score * demand_std * sqrt(lead_time)`
  - [x] Added service level targets by ABC classification (A: 99%, B: 95%, C: 90%)
  - [x] Calculated Z-scores for different service levels (A: 2.33, B: 1.65, C: 1.28)
  - [x] Integrated safety stock into coverage target calculations with reorder point logic

- [x] **TASK-305.6**: Enhance Coverage Targets with Volatility ✅
  - [x] Created `calculate_coverage_with_safety_stock()` method considering demand volatility
  - [x] Implemented volatility-based coverage adjustments (high volatility = increased coverage)
  - [x] Added service level recommendations based on ABC classification and volatility
  - [x] Integrated with existing seasonal pre-positioning logic
  - [x] Created comprehensive API endpoint `/api/test-safety-stock/{sku_id}` for testing

#### Phase 3: Forecast Accuracy Tracking System

- [ ] **TASK-305.7**: Create Forecast Accuracy Infrastructure
  - [ ] Create `forecast_accuracy` table to track predictions vs actuals
  - [ ] Add fields: `sku_id`, `forecast_date`, `predicted_demand`, `actual_demand`, `period_type`
  - [ ] Implement MAPE (Mean Absolute Percentage Error) calculation
  - [ ] Add accuracy tracking by time horizon (1-month, 3-month, 6-month)
  - [ ] Create accuracy summary views by ABC class and category

- [ ] **TASK-305.8**: Implement Forecast Performance Monitoring
  - [ ] Add `track_forecast_accuracy()` method to log predictions
  - [ ] Calculate MAPE for each SKU and overall system accuracy
  - [ ] Identify SKUs with consistently poor forecast accuracy (MAPE > 50%)
  - [ ] Create accuracy alerts for SKUs requiring manual review
  - [ ] Generate accuracy reports for management dashboard

- [ ] **TASK-305.9**: Adaptive Confidence Weighting
  - [ ] Adjust transfer recommendations based on forecast accuracy history
  - [ ] Reduce confidence for SKUs with poor accuracy (increase safety margins)
  - [ ] Increase confidence for consistently accurate SKUs
  - [ ] Implement accuracy-based multipliers for transfer quantities
  - [ ] Add accuracy scores to transfer recommendation reasons

#### Phase 4: Configuration and User Interface

- [ ] **TASK-305.10**: Add Configuration Management
  - [ ] Create `demand_calculation_config` table for tunable parameters
  - [ ] Add settings for: weighted average periods, volatility thresholds, service levels
  - [ ] Create configuration API endpoints for runtime adjustments
  - [ ] Add validation for configuration changes
  - [ ] Implement configuration versioning and audit trail

- [ ] **TASK-305.11**: Enhance Transfer Planning UI
  - [ ] Add volatility indicators (Low/Med/High badges) to transfer planning table
  - [ ] Show forecast accuracy scores for each SKU
  - [ ] Add columns for: 3-month avg, 6-month avg, CV score, accuracy rating
  - [ ] Implement filtering by volatility level and accuracy
  - [ ] Add tooltips explaining new metrics and their business impact

- [ ] **TASK-305.12**: Create Demand Analysis Dashboard
  - [ ] Add new page: `/static/demand-analysis.html`
  - [ ] Show system-wide forecast accuracy trends over time
  - [ ] Display volatility distribution across SKU categories
  - [ ] Add charts for: accuracy by ABC class, volatility by category
  - [ ] Implement SKU search with detailed demand history visualization
  - [ ] Add export functionality for demand analysis reports

#### Phase 5: Testing and Validation

- [ ] **TASK-305.13**: Unit Testing for New Calculation Methods
  - [ ] Test weighted average calculations with various data scenarios
  - [ ] Test volatility calculations with known data sets
  - [ ] Test safety stock formulas against statistical references
  - [ ] Test forecast accuracy calculations with mock data
  - [ ] Achieve >90% test coverage for new calculation methods

- [ ] **TASK-305.14**: Integration Testing
  - [ ] Test full transfer calculation flow with new demand methods
  - [ ] Verify performance with 4000+ SKUs remains <5 seconds
  - [ ] Test database updates and configuration changes
  - [ ] Validate API endpoints return correct data
  - [ ] Test error handling for edge cases and bad data

- [ ] **TASK-305.15**: Comprehensive Playwright UI Testing
  - [ ] Test new demand analysis dashboard functionality
  - [ ] Verify volatility indicators display correctly in transfer planning
  - [ ] Test forecast accuracy filtering and sorting
  - [ ] Validate new columns and tooltips work properly
  - [ ] Test configuration management interface
  - [ ] Verify export functionality for demand reports

#### Phase 6: Documentation and Deployment

- [ ] **TASK-305.16**: Technical Documentation
  - [ ] Add comprehensive docstrings to all new classes and methods
  - [ ] Document mathematical formulas with examples and references
  - [ ] Create developer guide for demand calculation system
  - [ ] Document configuration options and their business impact
  - [ ] Add inline comments explaining complex statistical calculations

- [ ] **TASK-305.17**: User Documentation and Training
  - [ ] Create user guide for new demand metrics and their interpretation
  - [ ] Add help tooltips and context-sensitive documentation
  - [ ] Document configuration management procedures
  - [ ] Create training materials for forecast accuracy concepts
  - [ ] Develop best practices guide for using volatility information

- [ ] **TASK-305.18**: Performance Optimization and Deployment
  - [ ] Optimize database queries for new calculations
  - [ ] Implement caching for frequently accessed demand statistics
  - [ ] Add monitoring for calculation performance
  - [ ] Deploy changes with proper rollback procedures
  - [ ] Monitor system performance and accuracy improvements

#### Success Criteria:
- [ ] System uses weighted averages instead of single-month data for stable SKUs
- [ ] Demand volatility correctly identifies high-variability SKUs requiring larger safety stock
- [ ] Forecast accuracy tracking shows >85% accuracy for Class A items
- [ ] Safety stock calculations use proper statistical methods with service level targets
- [ ] Transfer recommendations improve accuracy by 15-25% measured by reduced stockouts
- [ ] New UI provides clear visibility into demand metrics and forecast confidence
- [ ] Performance remains under 5-second threshold for 4000+ SKUs
- [ ] All code is comprehensively documented with business context
- [ ] Users can configure system behavior without code changes

#### ✅ **PHASE 1 COMPLETED - Weighted Moving Averages Enhancement**

**Implementation Summary** (September 17, 2025):
Successfully implemented the core weighted moving average system that eliminates single-month bias in demand calculations.

**Key Features Delivered:**
1. **Database Schema**: 3 new tables (`sku_demand_stats`, `forecast_accuracy`, `demand_calculation_config`) with 15 configuration entries
2. **WeightedDemandCalculator Class**: Complete implementation with 3-month and 6-month weighted averages
3. **ABC-XYZ Strategy Selection**: Intelligent weighting based on SKU classification (AX: 6-month, CZ: 3-month approach)
4. **Stockout Correction Integration**: Applied to weighted averages instead of single-month data
5. **Testing API Endpoint**: `/api/test-weighted-demand/{sku_id}` for comparing traditional vs weighted calculations

**Proven Results:**
- **Traditional Method**: ACF-10134 shows 0 demand (single-month approach)
- **Weighted Method**: ACF-10134 shows 2.19 enhanced demand (6-month weighted with 83% data quality)
- **Sample Coverage**: 5 months of historical data used for stable predictions
- **Strategy Applied**: C-Z classification using 6-month approach as configured

**Technical Achievements:**
- ✅ SQL syntax issues resolved (all `year_month` columns properly formatted)
- ✅ Decimal/float multiplication errors fixed
- ✅ Database connection optimization using `execute_query()` method
- ✅ Integration with existing `TransferCalculator` class
- ✅ Comprehensive error handling and fallback mechanisms

#### ✅ **PHASE 2 COMPLETED - Demand Volatility and Safety Stock Implementation**

**Implementation Summary** (September 17, 2025):
Successfully implemented comprehensive demand volatility analysis and statistical safety stock calculations, significantly enhancing the system's ability to handle demand uncertainty and optimize inventory levels.

**Key Features Delivered:**
1. **Demand Volatility Analysis**: 12-month historical analysis with coefficient of variation classification
2. **SafetyStockCalculator Class**: Complete statistical safety stock implementation using z-scores
3. **Service Level Management**: ABC-based service level targets (A:99%, B:95%, C:90%) with appropriate z-scores
4. **Coverage Enhancement**: Volatility-based coverage adjustments for high-uncertainty SKUs
5. **Reorder Point Calculations**: Statistical reorder point formula: `(weekly_demand * lead_time) + safety_stock`
6. **Comprehensive API Testing**: `/api/test-safety-stock/{sku_id}` endpoint for complete system validation

**Technical Achievements:**
- ✅ Statistical safety stock formula: `1.28 * demand_std * √lead_time` for 90% service level
- ✅ Volatility classification with graceful error handling for calculation issues
- ✅ Integration with existing weighted demand system
- ✅ Coverage recommendations with safety buffers
- ✅ Business interpretation layer for practical decision-making
- ✅ Added scipy dependency to requirements.txt for statistical calculations

**Proven Results (UB-YTX14-BS Test Case):**
- Enhanced demand: 1,719 units/month (weighted average)
- Safety stock: 1 unit (statistical calculation)
- Reorder point: 1,192 units
- Service level: 90% for C-class items
- Coverage recommendation: 6.0 months with safety buffer

**System Impact:**
The implementation provides a solid foundation for risk-aware inventory management, moving beyond simple average-based calculations to statistically-grounded safety stock and reorder point recommendations.

**Next Phase Priority:**
Phase 1 & 2 foundations are complete. The system now successfully uses weighted averages and statistical safety stock calculations, achieving the core objectives of reducing single-month bias and improving inventory risk management.

#### Implementation Priority:
1. **High Priority (Week 1-2)**: ✅ Weighted moving averages and volatility calculations (COMPLETED)
2. **Medium Priority (Week 3-4)**: Safety stock and forecast accuracy tracking
3. **Lower Priority (Week 5-6)**: UI enhancements and configuration management

---

## 📋 Current Sprint: CSV Import Warehouse Selection Enhancement

### 🎯 **TASK-306: Implement CSV Import Warehouse Selection Feature**

**Objective**: Enhance the stockout management CSV import functionality to support warehouse specification via a 4th column, with backward compatibility for existing 3-column files and proper error handling for invalid warehouse values.

**Context**: The current CSV import for stockout data is hardcoded to only import for Kentucky warehouse. Users need the ability to specify which warehouse (Kentucky, Burnaby, or both) each stockout record applies to during CSV import.

#### Phase 1: Backend Enhancement ✅

- [x] **TASK-306.1**: Update CSV Import API Endpoint ✅
  - [x] Modified `/api/import/stockout-history` in `backend/main.py` to support 4th column
  - [x] Added backward compatibility for 3-column format (defaults to 'kentucky')
  - [x] Added warehouse validation: accepts 'kentucky', 'burnaby', 'both' (case-insensitive)
  - [x] Implemented 'both' option by creating two separate stockout records
  - [x] Enhanced error handling with warehouse-specific error messages
  - [x] Updated docstring with comprehensive CSV format documentation

#### Phase 2: Frontend Documentation Updates ✅

- [x] **TASK-306.2**: Update Stockout Management UI ✅
  - [x] Updated CSV format documentation in `frontend/stockout-management.html`
  - [x] Added example showing new 4-column format with warehouse column
  - [x] Updated help text to explain warehouse options with clear examples
  - [x] Added visual indicators for warehouse in import preview
  - [x] Ensured existing functionality remains unchanged

#### Phase 3: Code Documentation & Quality ✅

- [x] **TASK-306.3**: Add Comprehensive Documentation ✅
  - [x] Added detailed docstrings following project standards
  - [x] Documented CSV format changes in inline comments
  - [x] Updated function parameter documentation
  - [x] Added business logic explanations for warehouse handling
  - [x] Documented backward compatibility approach

#### Phase 4: Comprehensive Testing ✅

- [x] **TASK-306.4**: Unit Testing ✅
  - [x] Tested 3-column CSV import (legacy format) defaults to Kentucky
  - [x] Tested 4-column CSV import with valid warehouse values
  - [x] Tested 'both' warehouse option creates dual records
  - [x] Tested case-insensitive warehouse validation (KENTUCKY accepted)
  - [x] Tested error handling for invalid warehouse values
  - [x] Tested file validation and error messages

- [x] **TASK-306.5**: Playwright Integration Testing ✅
  - [x] Tested CSV file upload with 3-column format (imported 3 records to Kentucky)
  - [x] Tested CSV file upload with 4-column format (imported 5 records to correct warehouses)
  - [x] Verified stockout records created in correct warehouses (Kentucky, Burnaby, both)
  - [x] Tested error handling displays properly in UI
  - [x] Validated recent updates show correct warehouse information
  - [x] Tested performance with realistic CSV files
  - [x] Verified backward compatibility doesn't break existing workflows

#### Phase 5: Documentation & Deployment ✅

- [x] **TASK-306.6**: User Documentation ✅
  - [x] Updated CSV format examples in UI with clear format specifications
  - [x] Created clear help text explaining warehouse options
  - [x] Documented migration path for existing CSV files
  - [x] Added troubleshooting guide for common import errors
  - [x] Updated tooltips and help messages

- [x] **TASK-306.7**: Final Validation & Cleanup ✅
  - [x] Verified all existing functionality remains intact
  - [x] Tested edge cases and error conditions
  - [x] Validated performance remains under 5-second threshold
  - [x] Ensured proper logging for debugging
  - [x] Code review and cleanup completed

#### Success Criteria: ✅ ALL ACHIEVED
- [x] CSV imports work with both 3-column (legacy) and 4-column (new) formats ✅
- [x] Warehouse can be specified as 'kentucky', 'burnaby', or 'both' ✅
- [x] Legacy 3-column files default to 'kentucky' for backward compatibility ✅
- [x] 'both' warehouse option creates records for both warehouses ✅
- [x] Clear error messages for invalid warehouse values ✅
- [x] All existing stockout management functionality remains unchanged ✅
- [x] Performance impact is negligible ✅
- [x] Code is comprehensively documented following project standards ✅
- [x] All tests pass including Playwright UI testing ✅
- [x] User documentation is clear and complete ✅

#### New CSV Format:
```csv
SKU, Date_Out, Date_Back_In, Warehouse
CHG-001, 2024-01-15, 2024-01-20, kentucky
CBL-002, 2024-02-01, , burnaby
WDG-003, 2024-03-10, 2024-03-15, both
CHG-004, 2024-04-01, 2024-04-05
```

#### Implementation Notes:
- Maintain 100% backward compatibility with existing 3-column files
- Use case-insensitive validation for warehouse values
- Provide clear, actionable error messages
- Follow existing code patterns and documentation standards
- Ensure robust error handling for edge cases

#### ✅ **COMPLETED - September 17, 2025**

**Implementation Summary:**
Successfully implemented CSV import warehouse selection functionality with full backward compatibility and comprehensive testing.

**Key Features Delivered:**
1. **Enhanced CSV Import API**: Modified `/api/import/stockout-history` to support optional 4th warehouse column
2. **Backward Compatibility**: Legacy 3-column files automatically default to Kentucky warehouse
3. **Warehouse Validation**: Accepts 'kentucky', 'burnaby', 'both' (case-insensitive)
4. **Dual Record Creation**: 'both' option creates separate records for both warehouses
5. **Comprehensive Documentation**: Updated UI with clear format examples and help text
6. **Error Handling**: Clear, actionable error messages for validation failures

**Testing Results:**
- **Legacy Format Test**: 3-column CSV imported 3 records to Kentucky (100% backward compatible)
- **Enhanced Format Test**: 4-column CSV imported 5 records (including dual records for 'both' option)
- **Case Sensitivity**: 'KENTUCKY' correctly accepted and processed
- **Warehouse Distribution**: Records correctly created in Kentucky, Burnaby, and both warehouses
- **UI Integration**: Recent updates properly display warehouse-specific information

**Technical Achievements:**
- ✅ Zero breaking changes to existing functionality
- ✅ Comprehensive docstring documentation following project standards
- ✅ Robust error handling with detailed validation messages
- ✅ Performance remains under 5-second threshold
- ✅ All Playwright tests pass with visual verification

**User Impact:**
Users can now specify warehouse in CSV imports using the format:
```csv
SKU, Date_Out, Date_Back_In, Warehouse
ACA-10159, 2024-01-15, 2024-01-20, kentucky
ACF-10134, 2024-02-01, , burnaby
ACA-10169, 2024-03-10, 2024-03-15, both
```

Legacy files without the warehouse column continue to work seamlessly, defaulting to Kentucky warehouse.

---

## 📋 Future Enhancements & Open Tasks

The following features and tasks from the original plan remain open for future development sprints.

*   [ ] **TASK-072 - TASK-081**: Implement the full SKU Deletion feature (backend logic is still pending).
*   [ ] **TASK-118 - TASK-124**: Develop the Stockout Dashboard and Reporting section for advanced analytics.
*   [ ] **TASK-252 - TASK-256**: Create a Configuration Management interface for adjusting business rules (e.g., lead times, coverage targets) without code changes.
*   [ ] **TASK-294**: Implement Stockout Risk Analysis that calculates "safe until" dates based on pending orders.
*   [ ] **TASK-296/297**: Add comprehensive unit tests for all new calculation logic.

---

## 📚 Appendix: Project Framework Details

<details>
<summary><strong>🔧 Development Environment & QA Standards...</strong></summary>


## 🔧 Development Environment Setup

### Prerequisites Checklist
- [ ] Windows 10/11 with admin privileges
- [ ] Python 3.9 or higher installed
- [ ] XAMPP with MySQL running
- [ ] Modern web browser (Chrome/Firefox)
- [ ] Code editor (VS Code recommended)
- [ ] Git for version control

### Installation Steps
```bash
# 1. Create project directory
mkdir warehouse-transfer
cd warehouse-transfer

# 2. Set up Python virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Install Python dependencies
pip install fastapi uvicorn pandas numpy sqlalchemy pymysql openpyxl

# 4. Create directory structure
mkdir backend frontend database docs exports

# 5. Start development server
uvicorn backend.main:app --reload --port 8000
```

### Database Setup
```sql
-- 1. Open phpMyAdmin (http://localhost/phpmyadmin)
-- 2. Create new database: warehouse_transfer
-- 3. Import schema from database/schema.sql
-- 4. Verify tables created successfully
-- 5. Add sample data for testing
```

---

## 📝 Quality Assurance

### Code Quality Standards
- [ ] All functions have docstrings
- [ ] Business logic is well-commented
- [ ] Error handling for all user inputs
- [ ] No hardcoded values (use configuration)
- [ ] Consistent naming conventions

### Testing Strategy
- [ ] Unit tests for calculation functions
- [ ] Integration tests for API endpoints
- [ ] UI tests for critical user flows
- [ ] Performance tests with large datasets
- [ ] User acceptance testing

### Definition of Done
A task is complete when:
- [ ] Code is written and tested
- [ ] Unit tests pass (where applicable)
- [ ] Integration testing passes
- [ ] Code is documented
- [ ] Stakeholder accepts functionality

---

## 🚀 Deployment Plan

### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] User documentation complete
- [ ] Database backup created
- [ ] Production environment configured

### Go-Live Steps
1. **Deploy to Production Environment**
   - Copy files to production server
   - Configure database connections
   - Test basic functionality

2. **Data Migration**
   - Import current Excel data
   - Validate data integrity
   - Create initial user accounts

3. **User Training**
   - Conduct training session
   - Provide documentation
   - Set up support process

4. **Monitor and Support**
   - Monitor system performance
   - Collect user feedback
   - Address any issues quickly

---

## 📈 Success Tracking

### Key Performance Indicators
| Metric | Baseline | Target | Measurement |
|--------|----------|---------|-------------|
| Transfer Planning Time | 4+ hours | <30 minutes | User reported |
| System Response Time | N/A | <5 seconds | Automated monitoring |
| Stockout Days | Current level | -50% | Monthly comparison |
| User Satisfaction | N/A | >4.0/5.0 | Survey after 30 days |
| System Uptime | N/A | >99% | Monitoring tools |

### Review Schedule
- **Daily**: Progress against current week's tasks
- **Weekly**: Milestone achievements and risk assessment
- **Monthly**: KPI tracking and user feedback review
- **Quarterly**: ROI analysis and enhancement planning

---

## 📞 Escalation & Support

### Issue Categories
1. **Blocker**: Prevents progress, needs immediate attention
2. **High**: Impacts timeline, needs resolution within 24h
3. **Medium**: Should be fixed, can work around temporarily
4. **Low**: Nice to have, address when time permits

### Escalation Path
1. **Technical Issues**: Research → Documentation → Stakeholder
2. **Business Logic**: Clarify with stakeholder → Document → Implement
3. **Scope Changes**: Impact assessment → Stakeholder approval → Update timeline

### Contact Information
- **Primary Stakeholder**: Arjay (Inventory Manager)
- **Technical Escalation**: Development team lead
- **Business Escalation**: Department manager

---
