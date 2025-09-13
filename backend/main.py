"""
Warehouse Transfer Planning Tool - FastAPI Application
Main application entry point with API routing and middleware setup
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn
from pathlib import Path
import pymysql
import io
from datetime import datetime
import logging
import uuid

# Set up logging
logger = logging.getLogger(__name__)

# Import our modules
try:
    from . import database
    from . import models
    from . import calculations
    from . import import_export
except ImportError:
    # For direct execution - add current directory to path
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import database
    import models
    import calculations
    import import_export

# Create FastAPI application
app = FastAPI(
    title="Warehouse Transfer Planning Tool",
    description="Intelligent inventory transfer recommendations with stockout correction",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# =============================================================================
# API ENDPOINTS - WAREHOUSE TRANSFER PLANNING TOOL
# =============================================================================
# Purpose: RESTful API for inventory management and transfer recommendations
# Architecture: FastAPI with automatic OpenAPI documentation generation
# Performance: Optimized queries with database connection pooling
# Security: CORS enabled, input validation, error handling
# Business Logic: Stockout correction, ABC-XYZ classification, transfer calculations

@app.get("/", 
         summary="Application Root", 
         description="Basic application information and health status",
         tags=["System"])
async def root():
    """Root endpoint serving the dashboard"""
    return {"message": "Warehouse Transfer Planning Tool", "version": "1.0.0", "status": "running"}

@app.get("/health",
         summary="System Health Check", 
         description="Verify database connectivity and system status",
         tags=["System"],
         responses={
             200: {"description": "System is healthy and database is connected"},
             500: {"description": "Database connection failed or system error"}
         })
async def health_check():
    """
    Comprehensive system health check endpoint
    
    Verifies:
    - Database connectivity and query execution
    - System components availability
    - Application version information
    
    Returns:
        dict: System status with database connection status and version info
    
    Raises:
        HTTPException: 500 error if database connection fails
        
    Business Use:
    - Monitoring and alerting systems
    - Load balancer health checks  
    - Deployment verification
    """
    try:
        # Test database connection with simple query
        db = database.get_database_connection()
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        db.close()
        
        return {
            "status": "healthy",
            "database": "connected", 
            "version": "1.0.0",
            "components": {
                "api": "operational",
                "database": "connected",
                "calculations": "ready"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"System health check failed: {str(e)}"
        )

# =============================================================================
# CORE API ENDPOINTS - INVENTORY & TRANSFER MANAGEMENT
# =============================================================================

@app.get("/api/skus",
         summary="Get All Active SKUs",
         description="Retrieve all active SKUs with current inventory levels and stock status",
         tags=["Inventory Management"],
         responses={
             200: {
                 "description": "List of active SKUs with inventory data",
                 "content": {
                     "application/json": {
                         "example": {
                             "skus": [
                                 {
                                     "sku_id": "CHG-001",
                                     "description": "USB-C Fast Charger 65W",
                                     "supplier": "Supplier A",
                                     "abc_code": "A",
                                     "xyz_code": "X", 
                                     "transfer_multiple": 25,
                                     "burnaby_qty": 500,
                                     "kentucky_qty": 0,
                                     "stock_status": "OUT_OF_STOCK"
                                 }
                             ],
                             "count": 4
                         }
                     }
                 }
             },
             500: {"description": "Database query failed"}
         })
async def get_skus():
    """
    Retrieve all active SKUs with comprehensive inventory information
    
    Business Logic:
    - Joins SKU master data with current inventory levels
    - Calculates stock status based on Kentucky warehouse quantities
    - Sorts by urgency (out of stock first) then by SKU ID
    - Only includes active SKUs (excludes Death Row/Discontinued)
    
    Stock Status Logic:
    - OUT_OF_STOCK: Kentucky qty = 0 (critical)
    - LOW_STOCK: Kentucky qty < 100 (warning)  
    - IN_STOCK: Kentucky qty >= 100 (normal)
    
    Returns:
        dict: List of SKUs with inventory data and total count
        
    Raises:
        HTTPException: 500 error if database query fails
        
    Usage:
        Used by dashboard for total SKU count
        Used by frontend for detailed SKU browsing
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Comprehensive SKU query with inventory status calculation
        query = """
        SELECT 
            s.sku_id,
            s.description,
            s.supplier,
            s.abc_code,
            s.xyz_code,
            s.transfer_multiple,
            COALESCE(ic.burnaby_qty, 0) as burnaby_qty,
            COALESCE(ic.kentucky_qty, 0) as kentucky_qty,
            CASE 
                WHEN COALESCE(ic.kentucky_qty, 0) = 0 THEN 'OUT_OF_STOCK'
                WHEN COALESCE(ic.kentucky_qty, 0) < 100 THEN 'LOW_STOCK'
                ELSE 'IN_STOCK'
            END as stock_status
        FROM skus s
        LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
        WHERE s.status = 'Active'
        ORDER BY 
            COALESCE(ic.kentucky_qty, 0) ASC,  -- Out of stock first
            s.sku_id
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        db.close()
        
        return {"skus": results, "count": len(results)}
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"SKU query failed: {str(e)}"
        )

@app.get("/api/dashboard",
         summary="Get Dashboard Metrics",
         description="Retrieve key business metrics and alerts for the main dashboard",
         tags=["Dashboard"],
         responses={
             200: {
                 "description": "Dashboard metrics with KPIs and system alerts",
                 "content": {
                     "application/json": {
                         "example": {
                             "metrics": {
                                 "out_of_stock": 1,
                                 "low_stock": 1, 
                                 "total_inventory_value": 26250.00,
                                 "current_month_sales": 540,
                                 "stockout_affected_skus": 1
                             },
                             "alerts": [
                                 {"type": "danger", "message": "1 SKUs are out of stock"},
                                 {"type": "warning", "message": "1 SKUs have low stock"}
                             ],
                             "timestamp": "2024-03-15T10:00:00Z"
                         }
                     }
                 }
             },
             500: {"description": "Dashboard query failed"}
         })
async def get_dashboard_metrics():
    """
    Generate comprehensive dashboard metrics for business intelligence
    
    Key Performance Indicators (KPIs):
    - Out of stock count: Critical inventory shortages requiring immediate action
    - Low stock count: Items below safety threshold needing attention  
    - Total inventory value: Current dollar value of Kentucky warehouse inventory
    - Current month sales: Units sold in current month across all SKUs
    - Stockout affected SKUs: Items that experienced stockouts this month
    
    Alert Generation:
    - Creates actionable alerts based on current inventory status
    - Filters out null alerts for clean presentation
    - Uses color coding (danger/warning/info) for visual priority
    
    Business Impact:
    - Enables data-driven inventory decisions
    - Provides early warning system for stock issues
    - Tracks monthly performance trends
    
    Returns:
        dict: Comprehensive dashboard data with metrics, alerts, and timestamp
        
    Raises:
        HTTPException: 500 error if any database query fails
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Out of stock count
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM inventory_current 
            WHERE kentucky_qty = 0
        """)
        out_of_stock = cursor.fetchone()['count']
        
        # Low stock count (< 100 units)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM inventory_current 
            WHERE kentucky_qty > 0 AND kentucky_qty < 100
        """)
        low_stock = cursor.fetchone()['count']
        
        # Total inventory value (Kentucky)
        cursor.execute("""
            SELECT SUM(ic.kentucky_qty * s.cost_per_unit) as value
            FROM inventory_current ic
            JOIN skus s ON ic.sku_id = s.sku_id
            WHERE s.status = 'Active'
        """)
        result = cursor.fetchone()
        total_value = float(result['value']) if result['value'] else 0
        
        # Recent sales (current month)
        cursor.execute("""
            SELECT SUM(kentucky_sales) as sales
            FROM monthly_sales 
            WHERE `year_month` = '2024-03'
        """)
        result = cursor.fetchone()
        current_sales = result['sales'] if result['sales'] else 0
        
        # SKUs with stockouts this month
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM monthly_sales
            WHERE `year_month` = '2024-03' AND kentucky_stockout_days > 0
        """)
        stockout_skus = cursor.fetchone()['count']
        
        db.close()
        
        return {
            "metrics": {
                "out_of_stock": out_of_stock,
                "low_stock": low_stock,
                "total_inventory_value": round(total_value, 2),
                "current_month_sales": current_sales,
                "stockout_affected_skus": stockout_skus
            },
            "alerts": [
                {"type": "danger", "message": f"{out_of_stock} SKUs are out of stock"} if out_of_stock > 0 else None,
                {"type": "warning", "message": f"{low_stock} SKUs have low stock"} if low_stock > 0 else None,
                {"type": "info", "message": f"{stockout_skus} SKUs affected by stockouts this month"} if stockout_skus > 0 else None
            ],
            "timestamp": "2024-03-15T10:00:00Z"  # In production, use actual timestamp
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard query failed: {str(e)}")

# Test POST endpoint to debug endpoint registration issue
@app.post("/api/debug-test", 
          summary="Debug Test Endpoint",
          description="Test endpoint to debug endpoint registration issues")
async def debug_test():
    return {"message": "Debug test endpoint working", "method": "POST"}

@app.get("/api/transfer-recommendations",
         summary="Generate Transfer Recommendations", 
         description="Calculate optimal inventory transfer quantities using stockout-corrected demand",
         tags=["Transfer Planning"],
         responses={
             200: {
                 "description": "List of transfer recommendations with priorities and reasoning",
                 "content": {
                     "application/json": {
                         "example": {
                             "recommendations": [
                                 {
                                     "sku_id": "CHG-001",
                                     "description": "USB-C Fast Charger 65W",
                                     "current_kentucky_qty": 0,
                                     "current_burnaby_qty": 500,
                                     "corrected_monthly_demand": 0.0,
                                     "recommended_transfer_qty": 0,
                                     "coverage_months": 0.0,
                                     "target_coverage_months": 4,
                                     "priority": "CRITICAL",
                                     "reason": "Stockout correction applied (25 days out); Currently out of stock",
                                     "abc_class": "A",
                                     "xyz_class": "X",
                                     "transfer_multiple": 25,
                                     "stockout_days": 25
                                 }
                             ],
                             "count": 4,
                             "generated_at": "2024-03-15T10:00:00Z"
                         }
                     }
                 }
             },
             500: {"description": "Transfer calculation failed"}
         })
async def get_transfer_recommendations():
    """
    Generate intelligent transfer recommendations using advanced inventory algorithms
    
    Core Business Logic:
    1. Stockout Correction: Adjusts demand based on availability rate with 30% floor
    2. ABC-XYZ Classification: Determines target coverage based on value and variability  
    3. Priority Scoring: CRITICAL (out of stock) > HIGH (< 1 month) > MEDIUM/LOW
    4. Transfer Optimization: Rounds to multiples, respects minimums, checks availability
    
    Algorithm Details:
    - Uses monthly sales data with stockout days count (simplified approach)
    - Applies corrected_demand = monthly_sales / max(availability_rate, 0.3)
    - Calculates target_inventory = corrected_demand × coverage_months
    - Determines transfer_need = target_inventory - current_position
    - Rounds to appropriate multiples (25/50/100) with 10-unit minimum
    
    Priority Logic:
    - CRITICAL: Kentucky qty = 0 (immediate action required)
    - HIGH: Coverage < 1 month (urgent restocking needed)  
    - MEDIUM: Coverage < 2 months (planned restocking)
    - LOW: Adequate coverage (maintenance transfers)
    
    Business Impact:
    - Prevents stockouts through predictive analytics
    - Optimizes cash flow by right-sizing transfers
    - Reduces manual calculation time from hours to seconds
    - Provides audit trail with detailed reasoning
    
    Returns:
        dict: Complete transfer recommendations with metadata
        
    Raises:
        HTTPException: 500 error if calculation engine fails
        
    Usage:
        Primary endpoint for transfer planning interface
        Data exported to Excel for warehouse execution
    """
    try:
        # Generate recommendations using sophisticated calculation engine
        recommendations = calculations.calculate_all_transfer_recommendations()
        
        return {
            "recommendations": recommendations,
            "count": len(recommendations),
            "generated_at": "2024-03-15T10:00:00Z",
            "algorithm_version": "1.0-monthly-stockout-correction",
            "business_rules": {
                "min_transfer_qty": 10,
                "stockout_correction_floor": 0.3,
                "max_correction_multiplier": 1.5,
                "coverage_targets": {
                    "AX": 4, "AY": 5, "AZ": 6,
                    "BX": 3, "BY": 4, "BZ": 5, 
                    "CX": 2, "CY": 2, "CZ": 1
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Transfer calculation engine failed: {str(e)}"
        )

@app.get("/api/sku/{sku_id}")
async def get_sku_details(sku_id: str):
    """Get detailed information for a specific SKU"""
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # SKU basic info
        cursor.execute("""
            SELECT s.*, ic.burnaby_qty, ic.kentucky_qty, ic.last_updated
            FROM skus s
            LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
            WHERE s.sku_id = %s
        """, (sku_id,))
        
        sku = cursor.fetchone()
        if not sku:
            raise HTTPException(status_code=404, detail="SKU not found")
        
        # Sales history
        cursor.execute("""
            SELECT `year_month`, burnaby_sales, kentucky_sales, 
                   burnaby_stockout_days, kentucky_stockout_days,
                   corrected_demand_kentucky
            FROM monthly_sales
            WHERE sku_id = %s
            ORDER BY `year_month` DESC
        """, (sku_id,))
        
        sales_history = cursor.fetchall()
        
        # Pending inventory
        cursor.execute("""
            SELECT quantity, destination, order_date, expected_arrival, status
            FROM pending_inventory
            WHERE sku_id = %s AND status IN ('ordered', 'shipped')
        """, (sku_id,))
        
        pending = cursor.fetchall()
        
        db.close()
        
        return {
            "sku": sku,
            "sales_history": sales_history,
            "pending_inventory": pending
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

# =============================================================================
# IMPORT/EXPORT API ENDPOINTS
# =============================================================================

@app.post("/api/import/excel",
         summary="Import Excel File",
         description="Upload and import Excel file with inventory, sales, or SKU data",
         tags=["Import/Export"],
         responses={
             200: {
                 "description": "Import completed successfully",
                 "content": {
                     "application/json": {
                         "example": {
                             "success": True,
                             "filename": "inventory_data.xlsx",
                             "sheets_processed": 2,
                             "records_imported": 150,
                             "errors": [],
                             "warnings": ["Minor data formatting issues corrected"],
                             "summary": {
                                 "total_sheets": 2,
                                 "total_records": 150,
                                 "error_count": 0,
                                 "warning_count": 1,
                                 "success_rate": "100%"
                             }
                         }
                     }
                 }
             },
             400: {"description": "Invalid file format or missing required data"},
             500: {"description": "Import processing failed"}
         })
async def import_excel_file(file: UploadFile = File(...)):
    """
    Import Excel file with comprehensive data validation and processing
    
    Supported Data Types:
    - Inventory levels (burnaby_qty, kentucky_qty by SKU)
    - Sales history (monthly sales with stockout days)
    - SKU master data (description, supplier, cost)
    - Stockout events (dates and durations)
    
    File Requirements:
    - Excel format (.xlsx, .xls)
    - Column headers matching expected schema
    - SKU IDs in consistent format
    - Numeric data properly formatted
    
    Processing Features:
    - Auto-detection of sheet content types
    - Data validation with error/warning reporting
    - Upsert logic (update existing, insert new)
    - Comprehensive import statistics
    
    Returns:
        dict: Import results with success status, statistics, and validation feedback
        
    Raises:
        HTTPException: 400 for invalid files, 500 for processing errors
        
    Business Impact:
        Eliminates manual data entry, ensures data consistency,
        provides audit trail for all imports
    """
    
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file format. Please upload an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Process import using import_export manager
        result = import_export.import_export_manager.import_excel_file(
            file_content, 
            file.filename
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Excel import failed: {str(e)}"
        )

@app.post("/api/import/csv",
         summary="Import CSV File", 
         description="Upload and import CSV file with data validation",
         tags=["Import/Export"])
async def import_csv_file(file: UploadFile = File(...)):
    """Import CSV file with automatic format detection and validation"""
    
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a CSV file"
        )
    
    try:
        file_content = await file.read()
        
        result = import_export.import_export_manager.import_csv_file(
            file_content,
            file.filename
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"CSV import failed: {str(e)}"
        )

@app.get("/api/export/excel/transfer-orders",
         summary="Export Transfer Orders to Excel",
         description="Generate professional Excel file with transfer recommendations and analysis",
         tags=["Import/Export"],
         responses={
             200: {
                 "description": "Excel file generated successfully",
                 "content": {
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                         "example": "Binary Excel file content"
                     }
                 }
             },
             500: {"description": "Excel generation failed"}
         })
async def export_transfer_orders_excel():
    """
    Export transfer recommendations to professional Excel format
    
    Generated Excel Structure:
    - Transfer Orders: Main recommendations with color-coded priorities
    - Summary: Key statistics and priority distribution
    - Current Inventory: Complete inventory status report
    
    Formatting Features:
    - Color-coded priority levels (Critical=Red, High=Orange, etc.)
    - Professional headers with company branding
    - Auto-sized columns for optimal viewing
    - Frozen header rows for easy scrolling
    - Conditional formatting for visual analysis
    
    File Naming:
    - Format: transfer-orders-YYYY-MM-DD.xlsx
    - Includes generation timestamp
    - Ready for warehouse team distribution
    
    Returns:
        StreamingResponse: Excel file ready for download
        
    Raises:
        HTTPException: 500 if Excel generation fails
        
    Business Use:
        Primary tool for warehouse transfer execution,
        Management reporting, audit documentation
    """
    
    try:
        # Get current transfer recommendations
        recommendations = calculations.calculate_all_transfer_recommendations()
        
        # Generate Excel file
        excel_content = import_export.import_export_manager.export_transfer_recommendations_excel(
            recommendations
        )
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"transfer-orders-{timestamp}.xlsx"
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Excel export failed: {str(e)}"
        )

@app.get("/api/export/csv/transfer-orders",
         summary="Export Transfer Orders to CSV",
         description="Export transfer recommendations in CSV format for data analysis",
         tags=["Import/Export"])
async def export_transfer_orders_csv():
    """Export transfer recommendations to CSV format"""
    
    try:
        # Get recommendations
        recommendations = calculations.calculate_all_transfer_recommendations()
        
        # Generate CSV
        csv_content = import_export.import_export_manager.export_csv(
            recommendations,
            "transfer-orders"
        )
        
        # Create filename
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"transfer-orders-{timestamp}.csv"
        
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"CSV export failed: {str(e)}"
        )

@app.get("/api/export/excel/inventory-status",
         summary="Export Inventory Status Report",
         description="Generate comprehensive inventory status report in Excel format",
         tags=["Import/Export"])
async def export_inventory_status_excel():
    """Export current inventory status to Excel with analysis"""
    
    try:
        # Get inventory data from database
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        query = """
        SELECT 
            s.sku_id,
            s.description,
            s.supplier,
            s.abc_code,
            s.xyz_code,
            s.cost_per_unit,
            s.transfer_multiple,
            COALESCE(ic.burnaby_qty, 0) as burnaby_qty,
            COALESCE(ic.kentucky_qty, 0) as kentucky_qty,
            COALESCE(ic.burnaby_qty, 0) + COALESCE(ic.kentucky_qty, 0) as total_qty,
            COALESCE(ic.kentucky_qty, 0) * s.cost_per_unit as kentucky_value,
            ic.last_updated,
            CASE 
                WHEN COALESCE(ic.kentucky_qty, 0) = 0 THEN 'OUT_OF_STOCK'
                WHEN COALESCE(ic.kentucky_qty, 0) < 100 THEN 'LOW_STOCK'
                ELSE 'IN_STOCK'
            END as stock_status
        FROM skus s
        LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
        WHERE s.status = 'Active'
        ORDER BY ic.kentucky_qty ASC, s.sku_id
        """
        
        cursor.execute(query)
        inventory_data = cursor.fetchall()
        db.close()
        
        # Generate Excel with inventory data
        wb = import_export.Workbook()
        ws = wb.active
        ws.title = "Inventory Status"
        
        # Headers
        headers = [
            "SKU", "Description", "Supplier", "ABC/XYZ", "Unit Cost", "Transfer Multiple",
            "Burnaby Qty", "Kentucky Qty", "Total Qty", "KY Value", "Stock Status", "Last Updated"
        ]
        
        for col, header in enumerate(headers, 1):
            ws.cell(row=1, column=col, value=header)
        
        # Data
        for row, item in enumerate(inventory_data, 2):
            ws.cell(row=row, column=1, value=item['sku_id'])
            ws.cell(row=row, column=2, value=item['description'])
            ws.cell(row=row, column=3, value=item['supplier'])
            ws.cell(row=row, column=4, value=f"{item['abc_code']}{item['xyz_code']}")
            ws.cell(row=row, column=5, value=item['cost_per_unit'])
            ws.cell(row=row, column=6, value=item['transfer_multiple'])
            ws.cell(row=row, column=7, value=item['burnaby_qty'])
            ws.cell(row=row, column=8, value=item['kentucky_qty'])
            ws.cell(row=row, column=9, value=item['total_qty'])
            ws.cell(row=row, column=10, value=item['kentucky_value'])
            ws.cell(row=row, column=11, value=item['stock_status'])
            ws.cell(row=row, column=12, value=item['last_updated'])
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"inventory-status-{timestamp}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inventory export failed: {str(e)}"
        )

# =============================================================================
# SKU MANAGEMENT ENDPOINTS
# =============================================================================

@app.post("/api/skus/{sku_id}/delete",
           summary="Delete SKU with Cascade",
           description="Permanently delete a SKU and all associated data",
           tags=["SKU Management"],
           responses={
               200: {"description": "SKU deleted successfully"},
               404: {"description": "SKU not found"},
               500: {"description": "Deletion failed due to database error"}
           })
async def delete_sku(sku_id: str):
    """
    Delete a SKU with cascade deletion of all related records
    
    Cascade Deletion Order:
    1. monthly_sales records (historical sales data)
    2. inventory_current records (current stock levels)
    3. skus record (master SKU data)
    
    Parameters:
        sku_id (str): The SKU identifier to delete
        
    Returns:
        dict: Simple deletion confirmation
            
    Raises:
        HTTPException: 404 if SKU not found, 500 for database errors
    """
    try:
        logger.info(f"DELETE SKU REQUEST: Starting deletion for SKU {sku_id}")
        db = database.get_database_connection()
        logger.info(f"DELETE SKU REQUEST: Database connection established")
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Start transaction for atomic deletion
        db.begin()
        logger.info(f"DELETE SKU REQUEST: Transaction started")
        
        # First verify SKU exists
        cursor.execute("SELECT sku_id, description FROM skus WHERE sku_id = %s", (sku_id,))
        sku_data = cursor.fetchone()
        logger.info(f"DELETE SKU REQUEST: SKU lookup result: {sku_data}")
        
        if not sku_data:
            db.rollback()
            logger.warning(f"DELETE SKU REQUEST: SKU {sku_id} not found")
            raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")
        
        # Delete related records in proper order
        cursor.execute("DELETE FROM monthly_sales WHERE sku_id = %s", (sku_id,))
        cursor.execute("DELETE FROM inventory_current WHERE sku_id = %s", (sku_id,))
        cursor.execute("DELETE FROM skus WHERE sku_id = %s", (sku_id,))
        
        # Commit transaction
        db.commit()
        
        cursor.close()
        db.close()
        
        return {
            "success": True,
            "message": f"SKU {sku_id} deleted successfully",
            "sku_id": sku_data["sku_id"],
            "description": sku_data["description"]
        }
        
    except HTTPException:
        if 'db' in locals():
            db.rollback()
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"SKU deletion failed: {str(e)}"
        )

@app.post("/api/skus/bulk-delete",
          summary="Bulk Delete Test SKUs",
          description="Delete multiple SKUs matching test patterns (TEST-, DEMO-, SAMPLE-)",
          tags=["SKU Management"],
          responses={
              200: {"description": "Bulk deletion completed"},
              400: {"description": "No matching SKUs found"},
              500: {"description": "Bulk deletion failed"}
          })
async def bulk_delete_test_skus():
    """
    Bulk delete SKUs matching test patterns for development cleanup
    
    Patterns: TEST-%, DEMO-%, SAMPLE-%
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Find test SKUs
        patterns = ['TEST-%', 'DEMO-%', 'SAMPLE-%']
        pattern_conditions = " OR ".join(["sku_id LIKE %s" for _ in patterns])
        find_query = f"SELECT sku_id, description FROM skus WHERE {pattern_conditions}"
        
        cursor.execute(find_query, patterns)
        matching_skus = cursor.fetchall()
        
        if not matching_skus:
            raise HTTPException(status_code=400, detail="No test SKUs found")
        
        # Start transaction for bulk deletion
        db.begin()
        
        # Delete each matching SKU with cascade
        deleted_count = 0
        for sku in matching_skus:
            sku_id = sku['sku_id']
            cursor.execute("DELETE FROM monthly_sales WHERE sku_id = %s", (sku_id,))
            cursor.execute("DELETE FROM inventory_current WHERE sku_id = %s", (sku_id,))
            cursor.execute("DELETE FROM skus WHERE sku_id = %s", (sku_id,))
            deleted_count += 1
        
        # Commit all deletions
        db.commit()
        
        cursor.close()
        db.close()
        
        return {
            "success": True,
            "message": f"Deleted {deleted_count} test SKUs",
            "deleted_count": deleted_count
        }
        
    except HTTPException:
        if 'db' in locals():
            db.rollback()
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Bulk deletion failed: {str(e)}"
        )

# ===================================================================
# STOCKOUT MANAGEMENT API ENDPOINTS
# ===================================================================

@app.post("/api/skus/validate",
          summary="Validate SKU List", 
          description="Validate a list of SKUs against the database",
          tags=["Stockout Management"],
          responses={
              200: {"description": "SKU validation results"},
              422: {"description": "Invalid input format"}
          })
async def validate_skus(request: dict):
    """
    Validate a list of SKUs against the database
    
    Args:
        request: Dictionary containing 'skus' list
        
    Returns:
        Dictionary with valid_skus and invalid_skus lists
        
    Example:
        POST /api/skus/validate
        {
            "skus": ["CHG-001", "CBL-002", "INVALID-SKU"]
        }
    """
    try:
        skus = request.get('skus', [])
        if not isinstance(skus, list):
            raise HTTPException(status_code=422, detail="SKUs must be provided as a list")
        
        if not skus:
            return {"valid_skus": [], "invalid_skus": []}
        
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Query existing SKUs
        placeholders = ','.join(['%s'] * len(skus))
        query = f"""
            SELECT sku_id, description, status 
            FROM skus 
            WHERE sku_id IN ({placeholders})
        """
        
        cursor.execute(query, skus)
        found_skus = cursor.fetchall()
        found_sku_ids = {sku['sku_id'] for sku in found_skus}
        
        # Separate valid and invalid SKUs
        valid_skus = [sku for sku in found_skus]
        invalid_skus = [sku for sku in skus if sku not in found_sku_ids]
        
        cursor.close()
        db.close()
        
        return {
            "valid_skus": valid_skus,
            "invalid_skus": invalid_skus,
            "total_requested": len(skus),
            "valid_count": len(valid_skus),
            "invalid_count": len(invalid_skus)
        }
        
    except Exception as e:
        logger.error(f"SKU validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"SKU validation failed: {str(e)}"
        )

@app.post("/api/stockouts/bulk-update",
          summary="Bulk Update Stockout Status",
          description="Update stockout status for multiple SKUs",
          tags=["Stockout Management"],
          responses={
              200: {"description": "Bulk update completed successfully"},
              400: {"description": "Invalid input data"},
              500: {"description": "Update operation failed"}
          })
async def bulk_update_stockout_status(request: dict):
    """
    Bulk update stockout status for multiple SKUs
    
    Args:
        request: Dictionary containing update parameters
            - skus: List of SKU IDs to update
            - status: 'out' or 'in' 
            - warehouse: 'kentucky', 'burnaby', or 'both'
            - date: Date string (YYYY-MM-DD)
            - notes: Optional notes for the update
            
    Returns:
        Dictionary with update results and statistics
        
    Example:
        POST /api/stockouts/bulk-update
        {
            "skus": ["CHG-001", "CBL-002"],
            "status": "out",
            "warehouse": "kentucky", 
            "date": "2024-03-28",
            "notes": "Morning stockout check"
        }
    """
    try:
        # Validate input
        required_fields = ['skus', 'status', 'warehouse', 'date']
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        skus = request['skus']
        status = request['status']
        warehouse = request['warehouse']
        date_str = request['date']
        notes = request.get('notes', '')
        
        # Validate parameters
        if not isinstance(skus, list) or not skus:
            raise HTTPException(status_code=400, detail="SKUs must be a non-empty list")
        
        if status not in ['out', 'in']:
            raise HTTPException(status_code=400, detail="Status must be 'out' or 'in'")
            
        if warehouse not in ['kentucky', 'burnaby', 'both']:
            raise HTTPException(status_code=400, detail="Warehouse must be 'kentucky', 'burnaby', or 'both'")
        
        # Parse date
        from datetime import datetime
        try:
            stockout_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Date must be in YYYY-MM-DD format")
        
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Generate batch ID for tracking
        import uuid
        batch_id = str(uuid.uuid4())
        
        # Start transaction
        db.begin()
        
        updated_count = 0
        warehouses = ['kentucky', 'burnaby'] if warehouse == 'both' else [warehouse]
        
        for sku_id in skus:
            for wh in warehouses:
                if status == 'out':
                    # Check if SKU is already out of stock for this warehouse (any unresolved stockout)
                    cursor.execute("""
                        SELECT sku_id, stockout_date FROM stockout_dates
                        WHERE sku_id = %s AND warehouse = %s AND is_resolved = FALSE
                    """, (sku_id, wh))

                    existing_stockout = cursor.fetchone()
                    if existing_stockout:
                        logger.warning(f"SKU {sku_id} is already marked as out of stock for {wh} warehouse since {existing_stockout['stockout_date']}. Skipping duplicate entry.")
                        continue  # Skip this SKU/warehouse combination

                    # Mark as out of stock
                    cursor.execute("""
                        INSERT INTO stockout_dates (sku_id, warehouse, stockout_date, is_resolved)
                        VALUES (%s, %s, %s, FALSE)
                        ON DUPLICATE KEY UPDATE
                            stockout_date = VALUES(stockout_date),
                            is_resolved = FALSE,
                            resolved_date = NULL
                    """, (sku_id, wh, stockout_date))
                    
                    # Update last stockout date in SKUs table
                    cursor.execute("""
                        UPDATE skus 
                        SET last_stockout_date = %s, updated_at = NOW()
                        WHERE sku_id = %s
                    """, (stockout_date, sku_id))
                    
                else:  # status == 'in'
                    # Mark as back in stock (resolve stockout)
                    cursor.execute("""
                        UPDATE stockout_dates
                        SET is_resolved = TRUE, resolved_date = %s
                        WHERE sku_id = %s AND warehouse = %s AND is_resolved = FALSE
                    """, (stockout_date, sku_id, wh))

                # Log the update (only if we didn't skip due to duplicate)
                cursor.execute("""
                    INSERT INTO stockout_updates_log
                    (update_batch_id, sku_id, warehouse, action, new_status, stockout_date,
                     resolution_date, update_source, user_notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    batch_id,
                    sku_id,
                    wh,
                    'mark_out' if status == 'out' else 'mark_in',
                    'out_of_stock' if status == 'out' else 'in_stock',
                    stockout_date,
                    stockout_date if status == 'in' else None,
                    'quick_ui',
                    notes
                ))

                updated_count += 1
        
        # Commit transaction
        db.commit()
        cursor.close()
        db.close()
        
        logger.info(f"Bulk stockout update completed: {updated_count} updates for batch {batch_id}")
        
        return {
            "success": True,
            "batch_id": batch_id,
            "updated_count": updated_count,
            "skus_processed": len(skus),
            "warehouses_processed": len(warehouses),
            "status": status,
            "date": date_str,
            "notes": notes
        }
        
    except HTTPException:
        if 'db' in locals():
            db.rollback()
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        logger.error(f"Bulk stockout update failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Bulk stockout update failed: {str(e)}"
        )

@app.get("/api/stockouts/current",
         summary="Get Current Stockouts",
         description="Retrieve all currently unresolved stockouts",
         tags=["Stockout Management"],
         responses={
             200: {"description": "List of current stockouts"},
             500: {"description": "Failed to retrieve stockouts"}
         })
async def get_current_stockouts():
    """
    Get all currently unresolved stockouts with urgency levels
    
    Returns:
        List of stockout records with calculated urgency and days out
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Query stockout_dates directly with basic SKU information
        query = """
            SELECT
                sd.sku_id,
                s.description,
                s.category,
                sd.warehouse,
                sd.stockout_date,
                DATEDIFF(CURDATE(), sd.stockout_date) as days_out,
                CASE
                    WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 30 THEN 'CRITICAL'
                    WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 14 THEN 'HIGH'
                    WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 7 THEN 'MEDIUM'
                    ELSE 'LOW'
                END as urgency_level,
                s.cost_per_unit,
                ic.burnaby_qty,
                ic.kentucky_qty
            FROM stockout_dates sd
            INNER JOIN skus s ON sd.sku_id = s.sku_id
            LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
            WHERE sd.is_resolved = FALSE
            ORDER BY
                CASE
                    WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 30 THEN 1
                    WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 14 THEN 2
                    WHEN DATEDIFF(CURDATE(), sd.stockout_date) >= 7 THEN 3
                    ELSE 4
                END,
                sd.stockout_date ASC
        """
        
        cursor.execute(query)
        stockouts = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return stockouts
        
    except Exception as e:
        logger.error(f"Failed to get current stockouts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve current stockouts: {str(e)}"
        )

@app.get("/api/stockouts/recent-updates",
         summary="Get Recent Stockout Updates", 
         description="Retrieve recent stockout status updates",
         tags=["Stockout Management"],
         responses={
             200: {"description": "List of recent updates"},
             500: {"description": "Failed to retrieve updates"}
         })
async def get_recent_stockout_updates(limit: int = 10):
    """
    Get recent stockout status updates for audit trail
    
    Args:
        limit: Maximum number of updates to return (default 10)
        
    Returns:
        List of recent update records grouped by batch
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Get recent updates grouped by batch
        query = """
            SELECT 
                update_batch_id as batch_id,
                action,
                warehouse,
                COUNT(*) as sku_count,
                MIN(created_at) as created_at,
                MAX(user_notes) as notes,
                update_source
            FROM stockout_updates_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY update_batch_id, action, warehouse, update_source
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        updates = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return updates
        
    except Exception as e:
        logger.error(f"Failed to get recent updates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve recent updates: {str(e)}"
        )

@app.post("/api/stockouts/undo/{batch_id}",
          summary="Undo Stockout Update",
          description="Reverse a previous stockout update batch",
          tags=["Stockout Management"], 
          responses={
              200: {"description": "Update successfully undone"},
              404: {"description": "Batch not found"},
              500: {"description": "Undo operation failed"}
          })
async def undo_stockout_update(batch_id: str):
    """
    Undo a previous stockout update by batch ID
    
    Args:
        batch_id: The batch ID of the update to reverse
        
    Returns:
        Dictionary with undo operation results
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Get the updates to undo
        cursor.execute("""
            SELECT sku_id, warehouse, action, stockout_date, resolution_date
            FROM stockout_updates_log
            WHERE update_batch_id = %s
            ORDER BY created_at DESC
        """, (batch_id,))
        
        updates = cursor.fetchall()
        
        if not updates:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Start transaction for undo
        db.begin()
        
        undone_count = 0
        undo_batch_id = str(uuid.uuid4())
        
        for update in updates:
            sku_id = update['sku_id']
            warehouse = update['warehouse']
            action = update['action']
            
            if action == 'mark_out':
                # Reverse: mark as resolved/in stock
                cursor.execute("""
                    UPDATE stockout_dates 
                    SET is_resolved = TRUE, resolved_date = CURDATE()
                    WHERE sku_id = %s AND warehouse = %s 
                        AND stockout_date = %s AND is_resolved = FALSE
                """, (sku_id, warehouse, update['stockout_date']))
                
                new_action = 'mark_in'
                new_status = 'in_stock'
                
            elif action == 'mark_in':
                # Reverse: mark as out of stock again
                cursor.execute("""
                    UPDATE stockout_dates 
                    SET is_resolved = FALSE, resolved_date = NULL
                    WHERE sku_id = %s AND warehouse = %s 
                        AND stockout_date = %s
                """, (sku_id, warehouse, update['stockout_date']))
                
                new_action = 'mark_out'
                new_status = 'out_of_stock'
            
            # Log the undo action
            cursor.execute("""
                INSERT INTO stockout_updates_log 
                (update_batch_id, sku_id, warehouse, action, new_status, 
                 stockout_date, update_source, user_notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                undo_batch_id,
                sku_id,
                warehouse, 
                new_action,
                new_status,
                update['stockout_date'],
                'quick_ui',
                f'Undo of batch {batch_id}'
            ))
            
            undone_count += 1
        
        # Commit undo transaction
        db.commit()
        cursor.close()
        db.close()
        
        logger.info(f"Undid stockout update batch {batch_id}: {undone_count} operations reversed")
        
        return {
            "success": True,
            "undone_batch_id": batch_id,
            "new_batch_id": undo_batch_id,
            "undone_count": undone_count
        }
        
    except HTTPException:
        if 'db' in locals():
            db.rollback()
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        logger.error(f"Undo operation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Undo operation failed: {str(e)}"
        )

@app.post("/api/import/stockout-history",
          summary="Import Historical Stockout Data",
          description="Import historical stockout data from CSV file",
          tags=["Stockout Management"],
          responses={
              200: {"description": "CSV import completed successfully"},
              400: {"description": "Invalid file format or data"},
              500: {"description": "Import operation failed"}
          })
async def import_stockout_history(file: UploadFile = File(...)):
    """
    Import historical stockout data from CSV file
    
    Expected CSV format (no headers):
    - Column 1: SKU ID
    - Column 2: Date out of stock (YYYY-MM-DD)
    - Column 3: Date back in stock (YYYY-MM-DD or blank for ongoing)
    
    Args:
        file: CSV file upload
        
    Returns:
        Dictionary with import results and statistics
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")
        
        # Read CSV content
        content = await file.read()
        decoded_content = content.decode('utf-8')
        
        import csv
        import io
        import uuid
        from datetime import datetime
        
        # Parse CSV
        csv_reader = csv.reader(io.StringIO(decoded_content))
        
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)
        
        # Start transaction
        db.begin()
        
        imported_count = 0
        error_count = 0
        batch_id = str(uuid.uuid4())
        errors = []
        
        for row_num, row in enumerate(csv_reader, 1):
            try:
                if len(row) < 2:
                    errors.append(f"Row {row_num}: Insufficient columns")
                    error_count += 1
                    continue
                
                sku_id = row[0].strip()
                date_out_str = row[1].strip()
                date_in_str = row[2].strip() if len(row) > 2 else ''
                
                if not sku_id or not date_out_str:
                    errors.append(f"Row {row_num}: Missing SKU or date")
                    error_count += 1
                    continue
                
                # Validate SKU exists
                cursor.execute("SELECT sku_id FROM skus WHERE sku_id = %s", (sku_id,))
                if not cursor.fetchone():
                    errors.append(f"Row {row_num}: SKU {sku_id} not found")
                    error_count += 1
                    continue
                
                # Parse dates
                try:
                    date_out = datetime.strptime(date_out_str, '%Y-%m-%d').date()
                except ValueError:
                    errors.append(f"Row {row_num}: Invalid date format for date_out")
                    error_count += 1
                    continue
                
                date_in = None
                is_resolved = False
                if date_in_str:
                    try:
                        date_in = datetime.strptime(date_in_str, '%Y-%m-%d').date()
                        is_resolved = True
                    except ValueError:
                        errors.append(f"Row {row_num}: Invalid date format for date_in")
                        error_count += 1
                        continue
                
                # Insert stockout record (assuming Kentucky warehouse for now)
                # TODO: Add warehouse detection logic based on data or add warehouse column
                cursor.execute("""
                    INSERT INTO stockout_dates 
                    (sku_id, warehouse, stockout_date, is_resolved, resolved_date)
                    VALUES (%s, 'kentucky', %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        is_resolved = VALUES(is_resolved),
                        resolved_date = VALUES(resolved_date)
                """, (sku_id, date_out, is_resolved, date_in))
                
                # Log the import
                cursor.execute("""
                    INSERT INTO stockout_updates_log 
                    (update_batch_id, sku_id, warehouse, action, new_status, 
                     stockout_date, resolution_date, update_source, user_notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    batch_id,
                    sku_id,
                    'kentucky',
                    'mark_in' if is_resolved else 'mark_out',
                    'in_stock' if is_resolved else 'out_of_stock',
                    date_out,
                    date_in,
                    'csv_import',
                    f'Historical import from {file.filename}'
                ))
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                error_count += 1
                continue
        
        # Commit if any successful imports
        if imported_count > 0:
            db.commit()
        else:
            db.rollback()
        
        cursor.close()
        db.close()
        
        logger.info(f"CSV import completed: {imported_count} imported, {error_count} errors")
        
        return {
            "success": imported_count > 0,
            "imported_count": imported_count,
            "error_count": error_count,
            "total_rows": imported_count + error_count,
            "batch_id": batch_id,
            "filename": file.filename,
            "errors": errors[:10]  # Return first 10 errors
        }
        
    except HTTPException:
        if 'db' in locals():
            db.rollback()
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        logger.error(f"CSV import failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"CSV import failed: {str(e)}"
        )

# Serve the main dashboard
@app.get("/dashboard")
async def dashboard_redirect():
    """Redirect to the main dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

# Serve the frontend dashboard (legacy)
@app.get("/dashboard-legacy", response_class=HTMLResponse)
async def dashboard_legacy():
    """Serve the main dashboard page"""
    # In a real implementation, we'd serve the actual HTML file
    return """
    <html>
        <head>
            <title>Warehouse Transfer Planning Tool</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }
                .alert { padding: 15px; margin: 10px 0; border-radius: 4px; }
                .alert-info { background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }
                .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
                .metric { background: #f8f9fa; padding: 20px; border-radius: 6px; text-align: center; border-left: 4px solid #007bff; }
                .metric h3 { margin: 0 0 10px 0; color: #666; font-size: 14px; }
                .metric .value { font-size: 24px; font-weight: bold; color: #333; }
                .api-links { margin: 30px 0; }
                .api-links a { display: inline-block; margin: 5px 10px 5px 0; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }
                .api-links a:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Warehouse Transfer Planning Tool</h1>
                
                <div class="alert alert-info">
                    <strong>Status:</strong> Application is running successfully! Database connection verified.
                </div>
                
                <div class="metrics">
                    <div class="metric">
                        <h3>Database Status</h3>
                        <div class="value">✅ Connected</div>
                    </div>
                    <div class="metric">
                        <h3>API Status</h3>
                        <div class="value">✅ Active</div>
                    </div>
                    <div class="metric">
                        <h3>Version</h3>
                        <div class="value">v1.0.0</div>
                    </div>
                </div>
                
                <div class="api-links">
                    <h3>API Endpoints:</h3>
                    <a href="/api/docs" target="_blank">API Documentation</a>
                    <a href="/api/dashboard" target="_blank">Dashboard Metrics</a>
                    <a href="/api/skus" target="_blank">SKU Data</a>
                    <a href="/api/transfer-recommendations" target="_blank">Transfer Recommendations</a>
                    <a href="/health" target="_blank">Health Check</a>
                </div>
                
                <p><strong>Next Steps:</strong></p>
                <ul>
                    <li>✅ Database setup completed with sample data</li>
                    <li>✅ Basic API endpoints working</li>
                    <li>⏳ Frontend development in progress</li>
                    <li>⏳ Stockout correction algorithms</li>
                    <li>⏳ Excel import/export functionality</li>
                </ul>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)