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
from typing import Optional
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
    import settings

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

@app.get("/api/skus/count",
         summary="Get SKU Count",
         description="Get the total count of active SKUs in the system",
         tags=["Inventory Management"],
         responses={
             200: {
                 "description": "SKU count information",
                 "content": {
                     "application/json": {
                         "example": {
                             "count": 4127,
                             "active": 4100,
                             "death_row": 25,
                             "discontinued": 2
                         }
                     }
                 }
             },
             500: {"description": "Database query failed"}
         })
async def get_sku_count():
    """
    Get comprehensive SKU count statistics

    Returns total counts by status and provides accurate statistics
    for dashboard display and data integrity checks.

    Returns:
        dict: SKU count statistics including totals by status
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        # Get counts by status
        query = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'Death Row' THEN 1 ELSE 0 END) as death_row,
            SUM(CASE WHEN status = 'Discontinued' THEN 1 ELSE 0 END) as discontinued
        FROM skus
        """

        cursor.execute(query)
        result = cursor.fetchone()
        db.close()

        return {
            "count": result['total'],
            "active": result['active'],
            "death_row": result['death_row'],
            "discontinued": result['discontinued']
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SKU count query failed: {str(e)}"
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

@app.put("/api/skus/{sku_id}",
         summary="Update SKU Master Data",
         description="Update editable fields of an existing SKU with comprehensive validation",
         tags=["SKU Management"],
         responses={
             200: {
                 "description": "SKU updated successfully",
                 "content": {
                     "application/json": {
                         "example": {
                             "success": True,
                             "sku_id": "CHG-001",
                             "message": "SKU updated successfully",
                             "updated_fields": ["description", "cost_per_unit", "abc_code"],
                             "updated_at": "2025-09-13T10:30:00Z"
                         }
                     }
                 }
             },
             400: {"description": "Invalid input data or validation failed"},
             404: {"description": "SKU not found"},
             500: {"description": "Update operation failed"}
         })
async def update_sku(sku_id: str, update_data: models.SKUUpdateRequest):
    """
    Update SKU master data with comprehensive validation and data integrity checks

    Updates only the provided fields, leaving others unchanged.
    All updates are performed within a database transaction for data integrity.

    Args:
        sku_id: The unique SKU identifier to update
        update_data: JSON object containing the fields to update

    Updateable Fields:
        - description: Product description (1-255 characters)
        - supplier: Supplier name (max 100 characters)
        - cost_per_unit: Unit cost (0.01-99999.99, rounded to 2 decimals)
        - status: Product status (Active, Death Row, or Discontinued)
        - transfer_multiple: Transfer quantity multiple (1-9999)
        - abc_code: ABC classification (A, B, or C)
        - xyz_code: XYZ classification (X, Y, or Z)
        - category: Product category (max 50 characters)

    Returns:
        JSON object with update confirmation and details

    Raises:
        HTTPException: 400 for validation errors, 404 if SKU not found, 500 for database errors
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        # First, verify the SKU exists
        cursor.execute("SELECT sku_id FROM skus WHERE sku_id = %s", (sku_id,))
        existing_sku = cursor.fetchone()

        if not existing_sku:
            db.close()
            raise HTTPException(status_code=404, detail=f"SKU '{sku_id}' not found")

        # Build dynamic update query from provided fields
        update_fields = []
        update_values = []
        updated_field_names = []

        # Only update fields that are provided in the request
        if update_data.description is not None:
            update_fields.append("description = %s")
            update_values.append(update_data.description)
            updated_field_names.append("description")

        if update_data.supplier is not None:
            update_fields.append("supplier = %s")
            update_values.append(update_data.supplier)
            updated_field_names.append("supplier")

        if update_data.cost_per_unit is not None:
            update_fields.append("cost_per_unit = %s")
            update_values.append(update_data.cost_per_unit)
            updated_field_names.append("cost_per_unit")

        if update_data.status is not None:
            update_fields.append("status = %s")
            update_values.append(update_data.status)
            updated_field_names.append("status")

        if update_data.transfer_multiple is not None:
            update_fields.append("transfer_multiple = %s")
            update_values.append(update_data.transfer_multiple)
            updated_field_names.append("transfer_multiple")

        if update_data.abc_code is not None:
            update_fields.append("abc_code = %s")
            update_values.append(update_data.abc_code)
            updated_field_names.append("abc_code")

        if update_data.xyz_code is not None:
            update_fields.append("xyz_code = %s")
            update_values.append(update_data.xyz_code)
            updated_field_names.append("xyz_code")

        if update_data.category is not None:
            update_fields.append("category = %s")
            update_values.append(update_data.category)
            updated_field_names.append("category")

        # Check if any fields were provided for update
        if not update_fields:
            db.close()
            raise HTTPException(status_code=400, detail="No valid fields provided for update")

        # Add updated_at timestamp
        update_fields.append("updated_at = NOW()")

        # Execute the update within a transaction
        try:
            # Start transaction
            cursor.execute("START TRANSACTION")

            # Build and execute update query
            update_query = f"UPDATE skus SET {', '.join(update_fields)} WHERE sku_id = %s"
            update_values.append(sku_id)

            cursor.execute(update_query, update_values)

            # Verify the update affected exactly one row
            if cursor.rowcount != 1:
                raise Exception(f"Expected to update 1 row, but affected {cursor.rowcount} rows")

            # Commit the transaction
            cursor.execute("COMMIT")

            # Log the successful update
            print(f"SKU update successful: {sku_id}, fields: {updated_field_names}")

            db.close()

            return {
                "success": True,
                "sku_id": sku_id,
                "message": "SKU updated successfully",
                "updated_fields": updated_field_names,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }

        except Exception as e:
            # Rollback on any error
            cursor.execute("ROLLBACK")
            raise e

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle validation errors from Pydantic
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Handle unexpected database or system errors
        print(f"SKU update error for {sku_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update operation failed: {str(e)}")

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

@app.post("/api/import/pending-orders",
         summary="Import Pending Orders CSV",
         description="Upload and import pending orders from CSV file with flexible date handling",
         tags=["Import/Export"])
async def import_pending_orders_csv(file: UploadFile = File(...)):
    """Import pending orders from CSV with automatic date calculations"""

    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a CSV file"
        )

    try:
        file_content = await file.read()

        result = import_export.import_export_manager.import_pending_orders_csv(
            file_content,
            file.filename
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pending orders CSV import failed: {str(e)}"
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

# ===================================================================
# PENDING ORDERS API ENDPOINTS
# ===================================================================

@app.get("/api/pending-orders",
         summary="Get All Pending Orders",
         description="Retrieve all pending inventory orders with analysis data",
         tags=["Pending Orders"])
async def get_pending_orders(
    status: Optional[str] = None,
    destination: Optional[str] = None,
    order_type: Optional[str] = None,
    overdue_only: bool = False
):
    """
    Retrieve pending orders with filtering options

    Args:
        status: Filter by order status (ordered/shipped/received/cancelled)
        destination: Filter by destination warehouse (burnaby/kentucky)
        order_type: Filter by order type (supplier/transfer)
        overdue_only: Show only overdue orders

    Returns:
        List of pending orders with analysis data
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        # Base query using the analysis view
        query = """
        SELECT * FROM v_pending_orders_analysis
        WHERE 1=1
        """
        params = []

        # Apply filters
        if status:
            query += " AND status = %s"
            params.append(status.lower())

        if destination:
            query += " AND destination = %s"
            params.append(destination.lower())

        if order_type:
            query += " AND order_type = %s"
            params.append(order_type.lower())

        if overdue_only:
            query += " AND is_overdue = TRUE"

        query += " ORDER BY priority_score DESC, order_date ASC"

        cursor.execute(query, params)
        results = cursor.fetchall()

        cursor.close()
        db.close()

        return {
            "success": True,
            "data": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Failed to retrieve pending orders: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pending orders: {str(e)}"
        )

@app.get("/api/pending-orders/summary",
         summary="Get Pending Orders Summary",
         description="Get summary of pending orders grouped by SKU",
         tags=["Pending Orders"])
async def get_pending_orders_summary():
    """
    Get pending orders summary by SKU using the pending quantities view
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        query = """
        SELECT
            pq.*,
            s.description,
            s.supplier,
            s.abc_code,
            s.xyz_code,
            ic.burnaby_qty as current_burnaby,
            ic.kentucky_qty as current_kentucky
        FROM v_pending_quantities pq
        INNER JOIN skus s ON pq.sku_id = s.sku_id
        LEFT JOIN inventory_current ic ON pq.sku_id = ic.sku_id
        ORDER BY pq.total_pending DESC, pq.earliest_arrival ASC
        """

        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        db.close()

        return {
            "success": True,
            "data": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Failed to get pending orders summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get pending orders summary: {str(e)}"
        )

@app.post("/api/pending-orders",
          summary="Create Pending Order",
          description="Create a new pending inventory order",
          tags=["Pending Orders"])
async def create_pending_order(order: models.PendingInventoryCreate):
    """
    Create a new pending inventory order
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor()

        # Validate SKU exists
        cursor.execute("SELECT sku_id FROM skus WHERE sku_id = %s", (order.sku_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"SKU '{order.sku_id}' not found"
            )

        # Insert new pending order
        insert_query = """
        INSERT INTO pending_inventory (
            sku_id, quantity, destination, order_date, expected_arrival,
            order_type, status, lead_time_days, is_estimated, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(insert_query, (
            order.sku_id,
            order.quantity,
            order.destination,
            order.order_date,
            order.expected_arrival,
            order.order_type,
            order.status,
            order.lead_time_days,
            order.is_estimated,
            order.notes
        ))

        order_id = cursor.lastrowid
        db.commit()

        cursor.close()
        db.close()

        return {
            "success": True,
            "message": "Pending order created successfully",
            "id": order_id,
            "sku_id": order.sku_id
        }

    except HTTPException:
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        logger.error(f"Failed to create pending order: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create pending order: {str(e)}"
        )

@app.post("/api/pending-orders/bulk",
          summary="Bulk Create Pending Orders",
          description="Create multiple pending orders in a single transaction",
          tags=["Pending Orders"])
async def bulk_create_pending_orders(bulk_data: models.BulkPendingInventoryCreate):
    """
    Create multiple pending orders in a single transaction
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor()

        imported_count = 0
        error_count = 0
        errors = []
        batch_id = str(uuid.uuid4())

        # Validate SKUs if requested
        if bulk_data.validate_skus:
            all_skus = [order.sku_id for order in bulk_data.orders]
            placeholders = ','.join(['%s'] * len(all_skus))
            cursor.execute(f"SELECT sku_id FROM skus WHERE sku_id IN ({placeholders})", all_skus)
            valid_skus = {row[0] for row in cursor.fetchall()}

            invalid_skus = set(all_skus) - valid_skus
            if invalid_skus:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid SKUs found: {', '.join(sorted(invalid_skus))}"
                )

        # Insert orders
        insert_query = """
        INSERT INTO pending_inventory (
            sku_id, quantity, destination, order_date, expected_arrival,
            order_type, status, lead_time_days, is_estimated, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for idx, order in enumerate(bulk_data.orders):
            try:
                cursor.execute(insert_query, (
                    order.sku_id,
                    order.quantity,
                    order.destination,
                    order.order_date,
                    order.expected_arrival,
                    order.order_type,
                    order.status,
                    order.lead_time_days,
                    order.is_estimated,
                    order.notes
                ))
                imported_count += 1

            except Exception as e:
                errors.append(f"Order {idx + 1} ({order.sku_id}): {str(e)}")
                error_count += 1
                continue

        if imported_count > 0:
            db.commit()
        else:
            db.rollback()

        cursor.close()
        db.close()

        return {
            "success": imported_count > 0,
            "imported_count": imported_count,
            "error_count": error_count,
            "total_orders": len(bulk_data.orders),
            "batch_id": batch_id,
            "errors": errors[:10]
        }

    except HTTPException:
        if 'db' in locals():
            db.rollback()
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        logger.error(f"Bulk pending orders creation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Bulk creation failed: {str(e)}"
        )

@app.put("/api/pending-orders/{order_id}",
         summary="Update Pending Order",
         description="Update an existing pending order",
         tags=["Pending Orders"])
async def update_pending_order(order_id: int, updates: models.PendingInventoryUpdate):
    """
    Update an existing pending order
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor()

        # Check if order exists
        cursor.execute("SELECT id FROM pending_inventory WHERE id = %s", (order_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Pending order {order_id} not found"
            )

        # Build update query dynamically
        update_fields = []
        update_values = []

        for field, value in updates.dict(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = %s")
                update_values.append(value)

        if not update_fields:
            raise HTTPException(
                status_code=400,
                detail="No fields to update"
            )

        update_query = f"""
        UPDATE pending_inventory
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = %s
        """
        update_values.append(order_id)

        cursor.execute(update_query, update_values)

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Pending order {order_id} not found"
            )

        db.commit()
        cursor.close()
        db.close()

        return {
            "success": True,
            "message": f"Pending order {order_id} updated successfully",
            "id": order_id
        }

    except HTTPException:
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        logger.error(f"Failed to update pending order {order_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update pending order: {str(e)}"
        )

@app.delete("/api/pending-orders/{order_id}",
           summary="Delete Pending Order",
           description="Delete a pending order",
           tags=["Pending Orders"])
async def delete_pending_order(order_id: int):
    """
    Delete a pending order
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor()

        cursor.execute("DELETE FROM pending_inventory WHERE id = %s", (order_id,))

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Pending order {order_id} not found"
            )

        db.commit()
        cursor.close()
        db.close()

        return {
            "success": True,
            "message": f"Pending order {order_id} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        logger.error(f"Failed to delete pending order {order_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete pending order: {str(e)}"
        )

@app.get("/api/pending-orders/{order_id}",
         summary="Get Pending Order Details",
         description="Get detailed information for a specific pending order",
         tags=["Pending Orders"])
async def get_pending_order(order_id: int):
    """
    Get detailed information for a specific pending order
    """
    try:
        db = database.get_database_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        query = """
        SELECT * FROM v_pending_orders_analysis
        WHERE id = %s
        """

        cursor.execute(query, (order_id,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Pending order {order_id} not found"
            )

        cursor.close()
        db.close()

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pending order {order_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get pending order: {str(e)}"
        )

# ===================================================================
# CONFIGURATION MANAGEMENT API ENDPOINTS
# ===================================================================

@app.get("/api/config/settings",
         summary="Get All Configuration Settings",
         description="Retrieve all system configuration settings by category",
         tags=["Configuration"])
async def get_configuration_settings(category: Optional[str] = None):
    """
    Get all configuration settings with optional category filter

    Args:
        category: Optional category filter (lead_times, coverage, business_rules, etc.)

    Returns:
        Dictionary of configuration settings with metadata
    """
    try:
        config_data = settings.configuration_manager.get_all_settings(category)

        return {
            "success": True,
            "settings": config_data,
            "categories": list(set(s['category'] for s in config_data.values())),
            "total_settings": len(config_data)
        }

    except Exception as e:
        logger.error(f"Error retrieving configuration settings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve configuration: {str(e)}"
        )

@app.get("/api/config/settings/{key}",
         summary="Get Configuration Setting",
         description="Retrieve a specific configuration setting by key",
         tags=["Configuration"])
async def get_configuration_setting(key: str):
    """Get specific configuration setting"""
    try:
        value = settings.configuration_manager.get_setting(key)

        if value is None:
            raise HTTPException(
                status_code=404,
                detail=f"Configuration key '{key}' not found"
            )

        # Get full setting info
        all_settings = settings.configuration_manager.get_all_settings()
        setting_info = all_settings.get(key, {})

        return {
            "key": key,
            "value": value,
            **setting_info
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration setting {key}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get setting: {str(e)}"
        )

@app.put("/api/config/settings/{key}",
         summary="Update Configuration Setting",
         description="Update a system configuration setting",
         tags=["Configuration"])
async def update_configuration_setting(key: str, setting_data: settings.ConfigurationValue):
    """Update configuration setting"""
    try:
        success = settings.configuration_manager.set_setting(
            key=key,
            value=setting_data.value,
            data_type=setting_data.data_type,
            category=setting_data.category,
            description=setting_data.description
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update configuration setting"
            )

        # Return updated value
        updated_value = settings.configuration_manager.get_setting(key)

        return {
            "success": True,
            "key": key,
            "value": updated_value,
            "message": f"Configuration '{key}' updated successfully"
        }

    except Exception as e:
        logger.error(f"Error updating configuration setting {key}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update setting: {str(e)}"
        )

@app.get("/api/config/supplier-lead-times",
         summary="Get Supplier Lead Time Overrides",
         description="Retrieve all supplier-specific lead time overrides",
         tags=["Configuration"])
async def get_supplier_lead_times():
    """Get all supplier lead time overrides"""
    try:
        lead_times = settings.configuration_manager.get_supplier_lead_times()

        return {
            "success": True,
            "supplier_lead_times": lead_times,
            "total_overrides": len(lead_times)
        }

    except Exception as e:
        logger.error(f"Error getting supplier lead times: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get supplier lead times: {str(e)}"
        )

@app.post("/api/config/supplier-lead-times",
          summary="Create Supplier Lead Time Override",
          description="Create or update supplier-specific lead time override",
          tags=["Configuration"])
async def create_supplier_lead_time(lead_time_data: settings.SupplierLeadTime):
    """Create or update supplier lead time override"""
    try:
        success = settings.configuration_manager.set_supplier_lead_time(
            supplier=lead_time_data.supplier,
            lead_time_days=lead_time_data.lead_time_days,
            destination=lead_time_data.destination,
            notes=lead_time_data.notes
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to create supplier lead time override"
            )

        return {
            "success": True,
            "supplier": lead_time_data.supplier,
            "lead_time_days": lead_time_data.lead_time_days,
            "destination": lead_time_data.destination,
            "message": f"Supplier lead time for '{lead_time_data.supplier}' updated successfully"
        }

    except Exception as e:
        logger.error(f"Error creating supplier lead time: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create supplier lead time: {str(e)}"
        )

@app.delete("/api/config/supplier-lead-times/{supplier}",
           summary="Delete Supplier Lead Time Override",
           description="Delete supplier-specific lead time override",
           tags=["Configuration"])
async def delete_supplier_lead_time(supplier: str, destination: Optional[str] = None):
    """Delete supplier lead time override"""
    try:
        success = settings.configuration_manager.delete_supplier_lead_time(
            supplier=supplier,
            destination=destination
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete supplier lead time override"
            )

        return {
            "success": True,
            "supplier": supplier,
            "destination": destination,
            "message": f"Supplier lead time override deleted successfully"
        }

    except Exception as e:
        logger.error(f"Error deleting supplier lead time: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete supplier lead time: {str(e)}"
        )

@app.get("/api/config/effective-lead-time",
         summary="Get Effective Lead Time",
         description="Get effective lead time considering supplier overrides",
         tags=["Configuration"])
async def get_effective_lead_time(supplier: Optional[str] = None, destination: Optional[str] = None):
    """Get effective lead time for supplier and destination"""
    try:
        lead_time = settings.configuration_manager.get_effective_lead_time(
            supplier=supplier,
            destination=destination
        )

        return {
            "supplier": supplier,
            "destination": destination,
            "effective_lead_time_days": lead_time,
            "source": "supplier_override" if supplier else "default_setting"
        }

    except Exception as e:
        logger.error(f"Error getting effective lead time: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get effective lead time: {str(e)}"
        )

@app.post("/api/config/reset",
          summary="Reset Configuration to Defaults",
          description="Reset configuration settings to default values",
          tags=["Configuration"])
async def reset_configuration(category: Optional[str] = None):
    """Reset configuration settings to defaults"""
    try:
        success = settings.configuration_manager.reset_to_defaults(category=category)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to reset configuration"
            )

        return {
            "success": True,
            "category": category,
            "message": f"Configuration reset to defaults" + (f" for category '{category}'" if category else "")
        }

    except Exception as e:
        logger.error(f"Error resetting configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset configuration: {str(e)}"
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
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)