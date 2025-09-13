  ⎿  Comprehensive Stockout Management Enhancement Plan

     Phase 1: Database Schema Updates (Day 1)

     Following existing patterns from schema.sql

     1. Add fields to skus table:
       - seasonal_pattern VARCHAR(20) - Auto-detected pattern
       - growth_status ENUM('normal', 'viral', 'declining')
       - last_stockout_date DATE
     2. Enhance stockout_dates table usage:
       - Add index for performance
       - Create triggers for auto-sync with monthly_sales

     Phase 2: Quick Stockout Update UI (Day 2-3)

     New file: frontend/stockout-management.html

     1. Create Quick Update Interface:
       - Textarea for bulk SKU paste
       - Radio buttons for status (out/in)
       - Warehouse selection
       - Date picker (default today)
       - Recent updates history
     2. API Endpoints:
       - POST /api/stockouts/bulk-update
       - GET /api/stockouts/current
       - GET /api/stockouts/history

     Phase 3: CSV Import for Historical Data (Day 3-4)

     Extend existing import_export.py

     1. CSV Import Features:
       - Support format: SKU, date_out, date_back_in
       - Auto-detect format (no headers required)
       - Validate SKUs exist
       - Handle blank date_back_in
       - Bulk insert with transaction
     2. API Endpoint:
       - POST /api/import/stockout-history
       - Support both individual dates and monthly aggregates

     Phase 4: Fix Calculation Engine (Day 4-5)

     Update calculations.py following existing patterns

     1. Zero Sales Stockout Fix:
     def correct_monthly_demand_enhanced(sku_id, monthly_sales, stockout_days):
         if monthly_sales == 0 and stockout_days > 20:
             # Look at same month last year
             last_year_demand = get_same_month_last_year(sku_id)
             if last_year_demand:
                 return last_year_demand * 1.1  # Growth factor
             
             # Fall back to category average
             category_avg = get_category_average(sku_id)
             return category_avg
         
         # Existing correction logic
         return correct_monthly_demand(monthly_sales, stockout_days)
     2. Seasonal Pattern Detection:
     def detect_seasonal_pattern(sku_id):
         # Analyze 2+ years of monthly data
         # Classify as spring_summer, fall_winter, holiday, year_round
         # Store in database for future use
     3. Viral Growth Detection:
     def detect_viral_growth(sku_id):
         # Compare recent 3 months to previous 3 months
         # Flag if growth > 2x
         # Update growth_status in database

     Phase 5: Enhanced Transfer Logic (Day 5-6)

     Update calculations.py transfer calculations

     1. Discontinued/Death Row Consolidation:
       - Transfer all inventory to higher-selling warehouse
       - New reason: "Consolidate discontinued item"
     2. Seasonal Pre-positioning:
       - Increase transfers 1 month before detected peak
       - Use year-over-year data for predictions

     Phase 6: Stockout Dashboard (Day 6-7)

     New section in frontend/index.html

     1. Dashboard Widgets:
       - Current stockouts count with days out
       - Lost sales estimate
       - Stockout trends chart
       - Quick actions for critical items
     2. Reporting Features:
       - Export stockout history
       - Pattern analysis report
       - Cost impact calculations

     Phase 7: Testing & Documentation (Day 7-8)

     1. Playwright MCP Testing:
       - Test Quick Update UI workflow
       - Test CSV import with various formats
       - Test calculation corrections
       - Test dashboard updates
       - Performance test with 4K SKUs
     2. Documentation Standards:
     def function_name(param1: str, param2: int) -> dict:
         """
         Clear description of function purpose
         
         Args:
             param1: Description of parameter 1
             param2: Description of parameter 2
             
         Returns:
             Dictionary containing results
             
         Raises:
             ValueError: When validation fails
         """

     Phase 8: TASKS.md Updates

     Add new section: Week 5-6 Stockout Management Enhancement

     ### Week 5-6: Stockout Management Enhancement
     **Focus**: Comprehensive stockout tracking and demand correction

     #### Day 1: Database Schema Updates
     - [ ] **TASK-082**: Add seasonal_pattern field to skus table
     - [ ] **TASK-083**: Add growth_status field to skus table
     - [ ] **TASK-084**: Create indexes for stockout_dates performance
     - [ ] **TASK-085**: Add triggers for data synchronization

     #### Day 2-3: Quick Stockout Update UI
     - [ ] **TASK-086**: Create stockout-management.html interface
     - [ ] **TASK-087**: Implement bulk paste textarea functionality
     - [ ] **TASK-088**: Add status radio buttons and warehouse selection
     - [ ] **TASK-089**: Create /api/stockouts/bulk-update endpoint
     - [ ] **TASK-090**: Add recent updates history display
     - [ ] **TASK-091**: Implement validation and error handling

     #### Day 3-4: CSV Import for Historical Data
     - [ ] **TASK-092**: Create CSV parser for stockout format
     - [ ] **TASK-093**: Implement /api/import/stockout-history endpoint
     - [ ] **TASK-094**: Add validation for SKU existence
     - [ ] **TASK-095**: Handle blank date_back_in fields
     - [ ] **TASK-096**: Create transaction-based bulk insert
     - [ ] **TASK-097**: Add import progress tracking

     #### Day 4-5: Fix Calculation Engine
     - [ ] **TASK-098**: Implement year-over-year demand lookup
     - [ ] **TASK-099**: Add category average fallback
     - [ ] **TASK-100**: Create seasonal pattern detection algorithm
     - [ ] **TASK-101**: Implement viral growth detection (2x threshold)
     - [ ] **TASK-102**: Update database with detected patterns
     - [ ] **TASK-103**: Test with historical data

     #### Day 5-6: Enhanced Transfer Logic
     - [ ] **TASK-104**: Implement discontinued item consolidation
     - [ ] **TASK-105**: Add seasonal pre-positioning logic
     - [ ] **TASK-106**: Update transfer reasons and priorities
     - [ ] **TASK-107**: Test with various SKU statuses

     #### Day 6-7: Stockout Dashboard
     - [ ] **TASK-108**: Create current stockouts widget
     - [ ] **TASK-109**: Add lost sales calculation
     - [ ] **TASK-110**: Implement stockout trends chart
     - [ ] **TASK-111**: Add export functionality
     - [ ] **TASK-112**: Create pattern analysis report

     #### Day 7-8: Testing & Documentation
     - [ ] **TASK-113**: Playwright test Quick Update UI
     - [ ] **TASK-114**: Playwright test CSV import
     - [ ] **TASK-115**: Playwright test dashboard updates
     - [ ] **TASK-116**: Performance test with 4K SKUs
     - [ ] **TASK-117**: Add comprehensive docstrings
     - [ ] **TASK-118**: Update API documentation
     - [ ] **TASK-119**: Create user guide for new features
     - [ ] **TASK-120**: Update GitHub repository

     Implementation Guidelines:

     1. Use Existing Patterns:
       - Follow FastAPI structure from main.py
       - Use database connection patterns from database.py
       - Match UI styling from existing pages
       - Reuse validation logic patterns
     2. Break Complex Features:
       - Separate UI, API, and calculation logic
       - Create reusable utility functions
       - Implement incrementally with testing
     3. Code Quality Standards:
       - All functions must have docstrings
       - Complex logic needs inline comments
       - Use type hints for all parameters
       - Handle errors gracefully
       - Log important operations
     4. Testing Requirements:
       - Unit tests for calculations
       - API endpoint tests
       - Playwright UI automation tests
       - Performance benchmarks

     Ready to implement this comprehensive stockout management enhancement?
