"""
Warehouse Transfer Planning Tool - Import/Export Module
Handles Excel and CSV data import/export with validation and formatting
"""

import pandas as pd
import numpy as np
from datetime import datetime
import io
import os
import logging
from typing import Dict, List, Tuple, Any, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils.dataframe import dataframe_to_rows
import pymysql
from pathlib import Path

# Import our modules
try:
    from . import database
    from . import models
    from . import calculations
except ImportError:
    # For direct execution
    import database
    import models
    import calculations

logger = logging.getLogger(__name__)

class ImportExportManager:
    """
    Comprehensive import/export manager for warehouse transfer data
    
    Handles:
    - Excel file import with validation
    - Excel export with professional formatting
    - CSV import/export capabilities
    - Data validation and error reporting
    - Transfer order generation
    """
    
    def __init__(self):
        """Initialize the import/export manager"""
        self.validation_errors = []
        self.validation_warnings = []
        
    # =============================================================================
    # EXCEL IMPORT FUNCTIONALITY
    # =============================================================================
    
    def import_excel_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Import Excel file with comprehensive validation and error handling
        
        Args:
            file_content: Raw bytes of the uploaded Excel file
            filename: Original filename for error reporting
            
        Returns:
            Dict containing import results, errors, and statistics
        """
        try:
            # Reset validation tracking
            self.validation_errors = []
            self.validation_warnings = []
            
            # Read Excel file into pandas DataFrame
            excel_data = pd.read_excel(io.BytesIO(file_content), sheet_name=None)
            
            results = {
                "success": False,
                "filename": filename,
                "import_timestamp": datetime.now().isoformat(),
                "sheets_processed": 0,
                "records_imported": 0,
                "errors": [],
                "warnings": [],
                "summary": {}
            }
            
            # Process each sheet
            for sheet_name, df in excel_data.items():
                sheet_result = self._process_excel_sheet(sheet_name, df)
                results["sheets_processed"] += 1
                results["records_imported"] += sheet_result.get("records", 0)
                
            # Compile validation results
            results["errors"] = self.validation_errors
            results["warnings"] = self.validation_warnings
            results["success"] = len(self.validation_errors) == 0
            
            # Generate import summary
            results["summary"] = self._generate_import_summary(results)
            
            logger.info(f"Excel import completed: {filename}, Success: {results['success']}")
            return results
            
        except Exception as e:
            logger.error(f"Excel import failed: {str(e)}")
            return {
                "success": False,
                "filename": filename,
                "error": f"Import failed: {str(e)}",
                "import_timestamp": datetime.now().isoformat()
            }
    
    def _process_excel_sheet(self, sheet_name: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Process individual Excel sheet based on its content type"""
        
        sheet_name_lower = sheet_name.lower()
        
        if 'inventory' in sheet_name_lower or 'stock' in sheet_name_lower:
            return self._import_inventory_data(df, sheet_name)
        elif 'sales' in sheet_name_lower or 'history' in sheet_name_lower:
            return self._import_sales_data(df, sheet_name)
        elif 'sku' in sheet_name_lower or 'product' in sheet_name_lower:
            return self._import_sku_data(df, sheet_name)
        elif 'stockout' in sheet_name_lower:
            return self._import_stockout_data(df, sheet_name)
        else:
            # Try to auto-detect content type
            return self._auto_detect_and_import(df, sheet_name)
    
    def _import_inventory_data(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """
        Import inventory levels data from Excel sheet with flexible column support

        Supports partial imports with either Burnaby-only, Kentucky-only, or both quantities.
        Missing quantity columns default to 0 to allow partial inventory updates.

        Args:
            df: DataFrame containing inventory data
            sheet_name: Name of the Excel sheet for error reporting

        Returns:
            Dict containing import results, record count, and any errors
        """

        # Required column is just sku_id, quantity columns are flexible
        required_columns = ['sku_id']
        optional_columns = ['burnaby_qty', 'kentucky_qty']
        result = {"type": "inventory", "records": 0, "errors": []}

        # Check for sku_id column (required)
        missing_required = self._validate_required_columns(df, required_columns, sheet_name)
        if missing_required:
            return result

        # Check which quantity columns are available
        available_cols = [col.lower() for col in df.columns]
        has_burnaby = any('burnaby' in col.lower() and 'qty' in col.lower() for col in df.columns)
        has_kentucky = any('kentucky' in col.lower() and 'qty' in col.lower() for col in df.columns)

        # At least one quantity column is required
        if not has_burnaby and not has_kentucky:
            self.validation_errors.append(
                f"Missing quantity columns in {sheet_name}: Need at least one of 'burnaby_qty' or 'kentucky_qty'"
            )
            return result

        # Create clean dataframe with available columns
        # Find the actual sku_id column name (case-insensitive)
        sku_id_col = next(col for col in df.columns if col.lower() == 'sku_id')
        columns_to_use = [sku_id_col]
        if has_burnaby:
            burnaby_col = next(col for col in df.columns if 'burnaby' in col.lower() and 'qty' in col.lower())
            columns_to_use.append(burnaby_col)
        if has_kentucky:
            kentucky_col = next(col for col in df.columns if 'kentucky' in col.lower() and 'qty' in col.lower())
            columns_to_use.append(kentucky_col)

        df_clean = df[columns_to_use].copy()
        df_clean = df_clean.dropna(subset=[sku_id_col])

        # Standardize column names and add missing columns with default values
        df_clean = df_clean.rename(columns={
            col: 'burnaby_qty' if 'burnaby' in col.lower() else 'kentucky_qty' if 'kentucky' in col.lower() else 'sku_id' if col.lower() == 'sku_id' else col
            for col in df_clean.columns
        })

        # Add missing quantity columns with default value 0
        if 'burnaby_qty' not in df_clean.columns:
            df_clean['burnaby_qty'] = 0
            self.validation_warnings.append(f"Burnaby quantities defaulted to 0 in {sheet_name}")
        if 'kentucky_qty' not in df_clean.columns:
            df_clean['kentucky_qty'] = 0
            self.validation_warnings.append(f"Kentucky quantities defaulted to 0 in {sheet_name}")

        # Convert quantities to integers
        for qty_col in ['burnaby_qty', 'kentucky_qty']:
            df_clean[qty_col] = pd.to_numeric(df_clean[qty_col], errors='coerce').fillna(0).astype(int)
        
        # Import to database
        try:
            db = database.get_database_connection()
            cursor = db.cursor()

            imported_count = 0
            skipped_skus = []
            for _, row in df_clean.iterrows():
                # Check which columns were actually provided (not defaulted to 0)
                update_burnaby = has_burnaby
                update_kentucky = has_kentucky
                update_both = update_burnaby and update_kentucky

                # Check if this is a new or existing SKU
                cursor.execute("SELECT sku_id FROM inventory_current WHERE sku_id = %s", (row['sku_id'],))
                exists = cursor.fetchone()

                if exists:
                    # Existing SKU - UPDATE only the provided warehouse columns
                    if update_both:
                        query = """
                        UPDATE inventory_current
                        SET burnaby_qty = %s, kentucky_qty = %s, last_updated = NOW()
                        WHERE sku_id = %s
                        """
                        cursor.execute(query, (row['burnaby_qty'], row['kentucky_qty'], row['sku_id']))
                    elif update_burnaby:
                        query = """
                        UPDATE inventory_current
                        SET burnaby_qty = %s, last_updated = NOW()
                        WHERE sku_id = %s
                        """
                        cursor.execute(query, (row['burnaby_qty'], row['sku_id']))
                    elif update_kentucky:
                        query = """
                        UPDATE inventory_current
                        SET kentucky_qty = %s, last_updated = NOW()
                        WHERE sku_id = %s
                        """
                        cursor.execute(query, (row['kentucky_qty'], row['sku_id']))
                    imported_count += 1
                else:
                    # New SKU - only insert if both quantities provided
                    if update_both:
                        query = """
                        INSERT INTO inventory_current (sku_id, burnaby_qty, kentucky_qty, last_updated)
                        VALUES (%s, %s, %s, NOW())
                        """
                        cursor.execute(query, (row['sku_id'], row['burnaby_qty'], row['kentucky_qty']))
                        imported_count += 1
                    else:
                        # Skip new SKU with partial data
                        skipped_skus.append(row['sku_id'])

            # Add warning for skipped SKUs if any
            if skipped_skus:
                self.validation_warnings.append(
                    f"New SKUs with partial data skipped: {', '.join(skipped_skus[:5])}" +
                    (f" and {len(skipped_skus)-5} more" if len(skipped_skus) > 5 else "")
                )
            
            db.commit()
            db.close()
            
            result["records"] = imported_count
            logger.info(f"Imported {imported_count} inventory records from {sheet_name}")
            
        except Exception as e:
            self.validation_errors.append(f"Database error in {sheet_name}: {str(e)}")
            logger.error(f"Database error importing inventory: {str(e)}")
        
        return result
    
    def _import_sales_data(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """Import sales history data with stockout days"""
        
        expected_columns = ['sku_id', 'year_month', 'burnaby_sales', 'kentucky_sales', 'kentucky_stockout_days']
        result = {"type": "sales", "records": 0, "errors": []}
        
        # Validate columns (allow some flexibility)
        available_cols = df.columns.tolist()
        missing_critical = []
        
        for col in ['sku_id', 'year_month']:
            if col not in available_cols:
                missing_critical.append(col)
        
        if missing_critical:
            error_msg = f"Missing critical columns in {sheet_name}: {', '.join(missing_critical)}"
            self.validation_errors.append(error_msg)
            return result
        
        # Handle optional columns
        df_clean = df.copy()
        for col in ['burnaby_sales', 'kentucky_sales', 'kentucky_stockout_days', 'burnaby_stockout_days']:
            if col not in df_clean.columns:
                df_clean[col] = 0
        
        # Clean and validate data
        df_clean = df_clean.dropna(subset=['sku_id', 'year_month'])
        
        # Convert numeric columns
        numeric_cols = ['burnaby_sales', 'kentucky_sales', 'kentucky_stockout_days', 'burnaby_stockout_days']
        for col in numeric_cols:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0).astype(int)
        
        # Validate stockout days (0-31)
        invalid_stockout = df_clean[
            (df_clean['kentucky_stockout_days'] < 0) | 
            (df_clean['kentucky_stockout_days'] > 31)
        ]
        
        if not invalid_stockout.empty:
            self.validation_warnings.append(
                f"Invalid stockout days found in {sheet_name} - should be 0-31 days"
            )
        
        # Import to database
        try:
            db = database.get_database_connection()
            cursor = db.cursor()
            
            imported_count = 0
            for _, row in df_clean.iterrows():
                # Upsert sales data
                query = """
                INSERT INTO monthly_sales
                (`sku_id`, `year_month`, `burnaby_sales`, `kentucky_sales`,
                 `burnaby_stockout_days`, `kentucky_stockout_days`)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `burnaby_sales` = VALUES(`burnaby_sales`),
                    `kentucky_sales` = VALUES(`kentucky_sales`),
                    `burnaby_stockout_days` = VALUES(`burnaby_stockout_days`),
                    `kentucky_stockout_days` = VALUES(`kentucky_stockout_days`)
                """
                cursor.execute(query, (
                    row['sku_id'], row['year_month'], row['burnaby_sales'], 
                    row['kentucky_sales'], row['burnaby_stockout_days'], 
                    row['kentucky_stockout_days']
                ))
                imported_count += 1
            
            db.commit()
            db.close()
            
            result["records"] = imported_count
            logger.info(f"Imported {imported_count} sales records from {sheet_name}")
            
        except Exception as e:
            self.validation_errors.append(f"Database error in {sheet_name}: {str(e)}")
            logger.error(f"Database error importing sales: {str(e)}")
        
        return result
    
    def _import_sku_data(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """
        Import SKU master data with flexible column detection

        Supports required and optional columns with intelligent detection.
        Category field is automatically detected if present.

        Args:
            df: DataFrame containing SKU data
            sheet_name: Name of the Excel sheet for error reporting

        Returns:
            Dict containing import results, record count, and any errors
        """

        # Required columns for SKU import
        required_columns = ['sku_id', 'description', 'supplier', 'cost_per_unit']

        # Optional columns that can be detected and imported
        optional_columns = ['status', 'transfer_multiple', 'abc_code', 'xyz_code', 'category']

        result = {"type": "sku", "records": 0, "errors": []}

        # Validate required columns
        missing_cols = self._validate_required_columns(df, required_columns, sheet_name)
        if missing_cols:
            return result

        # Start with required columns
        columns_to_use = required_columns.copy()

        # Detect available optional columns using case-insensitive matching
        available_cols_lower = {col.lower(): col for col in df.columns}

        # Check for each optional column
        for opt_col in optional_columns:
            # Check for exact match first
            if opt_col in df.columns:
                columns_to_use.append(opt_col)
            # Check for case-insensitive match
            elif opt_col.lower() in available_cols_lower:
                columns_to_use.append(available_cols_lower[opt_col.lower()])

        # Create clean dataframe with detected columns
        df_clean = df[columns_to_use].copy()
        df_clean = df_clean.dropna(subset=['sku_id'])

        # Standardize column names (in case of case differences)
        column_mapping = {}
        for col in df_clean.columns:
            col_lower = col.lower()
            for opt_col in optional_columns:
                if opt_col.lower() == col_lower and col != opt_col:
                    column_mapping[col] = opt_col

        if column_mapping:
            df_clean = df_clean.rename(columns=column_mapping)

        # Add default values for missing optional columns
        if 'status' not in df_clean.columns:
            df_clean['status'] = 'Active'
        if 'transfer_multiple' not in df_clean.columns:
            df_clean['transfer_multiple'] = 50
        if 'abc_code' not in df_clean.columns:
            df_clean['abc_code'] = 'C'
        if 'xyz_code' not in df_clean.columns:
            df_clean['xyz_code'] = 'Z'
        if 'category' not in df_clean.columns:
            df_clean['category'] = None

        # Log which optional columns were detected
        detected_optional = [col for col in optional_columns if col in df_clean.columns and df_clean[col].notna().any()]
        if detected_optional:
            self.validation_warnings.append(f"Detected optional columns in {sheet_name}: {', '.join(detected_optional)}")
            logger.info(f"SKU import detected optional columns: {detected_optional}")
        
        # Import to database
        try:
            db = database.get_database_connection()
            cursor = db.cursor()
            
            imported_count = 0
            for _, row in df_clean.iterrows():
                query = """
                INSERT INTO skus (sku_id, description, supplier, cost_per_unit, status, transfer_multiple, abc_code, xyz_code, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    description = VALUES(description),
                    supplier = VALUES(supplier),
                    cost_per_unit = VALUES(cost_per_unit),
                    status = VALUES(status),
                    transfer_multiple = VALUES(transfer_multiple),
                    abc_code = VALUES(abc_code),
                    xyz_code = VALUES(xyz_code),
                    category = VALUES(category)
                """
                cursor.execute(query, (
                    row['sku_id'],
                    row['description'],
                    row['supplier'],
                    row['cost_per_unit'],
                    row.get('status', 'Active'),
                    row.get('transfer_multiple', 50),
                    row.get('abc_code', 'C'),
                    row.get('xyz_code', 'Z'),
                    row.get('category', None)
                ))
                imported_count += 1
            
            db.commit()
            db.close()
            
            result["records"] = imported_count
            logger.info(f"Imported {imported_count} SKU records from {sheet_name}")
            
        except Exception as e:
            self.validation_errors.append(f"Database error in {sheet_name}: {str(e)}")
        
        return result
    
    def _auto_detect_and_import(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """Auto-detect sheet content type and import appropriately"""

        columns = [col.lower() for col in df.columns]

        # Check for inventory data - requires sku_id and at least one quantity column
        has_sku_id = 'sku_id' in columns
        has_burnaby_qty = any('burnaby' in col and 'qty' in col for col in columns)
        has_kentucky_qty = any('kentucky' in col and 'qty' in col for col in columns)

        if has_sku_id and (has_burnaby_qty or has_kentucky_qty):
            return self._import_inventory_data(df, sheet_name)
        elif 'year_month' in columns and any('sales' in col for col in columns):
            return self._import_sales_data(df, sheet_name)
        elif 'description' in columns and 'cost_per_unit' in columns:
            return self._import_sku_data(df, sheet_name)
        else:
            self.validation_warnings.append(f"Unknown sheet format: {sheet_name} - skipped")
            return {"type": "unknown", "records": 0}
    
    def _validate_required_columns(self, df: pd.DataFrame, required_cols: List[str], sheet_name: str) -> List[str]:
        """Validate that required columns exist in dataframe"""
        
        available_cols = [col.lower() for col in df.columns]
        missing_cols = []
        
        for col in required_cols:
            if col.lower() not in available_cols:
                missing_cols.append(col)
        
        if missing_cols:
            error_msg = f"Missing required columns in {sheet_name}: {', '.join(missing_cols)}"
            self.validation_errors.append(error_msg)
        
        return missing_cols
    
    def _generate_import_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive import summary"""
        
        return {
            "total_sheets": results["sheets_processed"],
            "total_records": results["records_imported"],
            "error_count": len(results["errors"]),
            "warning_count": len(results["warnings"]),
            "success_rate": "100%" if results["success"] else f"{max(0, 100 - len(results['errors']) * 10)}%"
        }
    
    # =============================================================================
    # EXCEL EXPORT FUNCTIONALITY
    # =============================================================================
    
    def export_transfer_recommendations_excel(self, recommendations: List[Dict]) -> bytes:
        """
        Export transfer recommendations to professionally formatted Excel file
        
        Args:
            recommendations: List of transfer recommendation dictionaries
            
        Returns:
            bytes: Excel file content ready for download
        """
        
        # Create workbook with multiple sheets
        wb = Workbook()
        
        # Remove default sheet
        wb.remove(wb.active)
        
        # Create Transfer Orders sheet
        self._create_transfer_orders_sheet(wb, recommendations)
        
        # Create Summary sheet
        self._create_summary_sheet(wb, recommendations)
        
        # Create Inventory Status sheet
        self._create_inventory_status_sheet(wb)
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return output.getvalue()
    
    def _create_transfer_orders_sheet(self, wb: Workbook, recommendations: List[Dict]):
        """Create the main transfer orders sheet with professional formatting"""
        
        ws = wb.create_sheet("Transfer Orders")
        
        # Define styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        priority_fills = {
            "CRITICAL": PatternFill(start_color="DC3545", end_color="DC3545", fill_type="solid"),
            "HIGH": PatternFill(start_color="FD7E14", end_color="FD7E14", fill_type="solid"),
            "MEDIUM": PatternFill(start_color="FFC107", end_color="FFC107", fill_type="solid"),
            "LOW": PatternFill(start_color="28A745", end_color="28A745", fill_type="solid")
        }
        
        # Headers
        headers = [
            "SKU", "Description", "Priority", "Current KY Qty", "Available CA Qty",
            "Monthly Demand", "Coverage (Months)", "Recommended Transfer", 
            "ABC/XYZ Class", "Reason", "Transfer Multiple"
        ]
        
        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Write data
        for row, rec in enumerate(recommendations, 2):
            ws.cell(row=row, column=1, value=rec['sku_id'])
            ws.cell(row=row, column=2, value=rec['description'])
            
            # Priority with color coding
            priority_cell = ws.cell(row=row, column=3, value=rec['priority'])
            if rec['priority'] in priority_fills:
                priority_cell.fill = priority_fills[rec['priority']]
                if rec['priority'] in ['CRITICAL', 'HIGH', 'LOW']:
                    priority_cell.font = Font(color="FFFFFF", bold=True)
                else:
                    priority_cell.font = Font(bold=True)
            
            ws.cell(row=row, column=4, value=rec['current_kentucky_qty'])
            ws.cell(row=row, column=5, value=rec['current_burnaby_qty'])
            ws.cell(row=row, column=6, value=round(rec['corrected_monthly_demand']))
            ws.cell(row=row, column=7, value=round(rec['coverage_months'], 1))
            ws.cell(row=row, column=8, value=rec['recommended_transfer_qty'])
            ws.cell(row=row, column=9, value=f"{rec['abc_class']}{rec['xyz_class']}")
            ws.cell(row=row, column=10, value=rec['reason'])
            ws.cell(row=row, column=11, value=rec['transfer_multiple'])
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Freeze header row
        ws.freeze_panes = "A2"
        
        # Add borders
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for row in ws.iter_rows(min_row=1, max_row=len(recommendations)+1):
            for cell in row:
                cell.border = thin_border
    
    def _create_summary_sheet(self, wb: Workbook, recommendations: List[Dict]):
        """Create summary statistics sheet"""
        
        ws = wb.create_sheet("Summary")
        
        # Calculate statistics
        total_items = len(recommendations)
        critical_items = len([r for r in recommendations if r['priority'] == 'CRITICAL'])
        high_items = len([r for r in recommendations if r['priority'] == 'HIGH'])
        total_transfer_qty = sum(r['recommended_transfer_qty'] for r in recommendations)
        avg_coverage = sum(r['coverage_months'] for r in recommendations) / total_items if total_items > 0 else 0
        
        # Summary data
        summary_data = [
            ["Transfer Planning Summary", ""],
            ["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""],
            ["Total SKUs Analyzed", total_items],
            ["Critical Priority Items", critical_items],
            ["High Priority Items", high_items],
            ["Total Transfer Quantity", total_transfer_qty],
            ["Average Coverage (Months)", round(avg_coverage, 1)],
            ["", ""],
            ["Priority Distribution", "Count"],
        ]
        
        # Count by priority
        priority_counts = {}
        for rec in recommendations:
            priority = rec['priority']
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        for priority, count in priority_counts.items():
            summary_data.append([f"  {priority}", count])
        
        # Write summary data
        for row, (label, value) in enumerate(summary_data, 1):
            ws.cell(row=row, column=1, value=label)
            ws.cell(row=row, column=2, value=value)
            
            # Format header row
            if row == 1:
                ws.cell(row=row, column=1).font = Font(bold=True, size=14)
                ws.cell(row=row, column=1).fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                ws.cell(row=row, column=1).font = Font(bold=True, color="FFFFFF", size=14)
        
        # Auto-adjust columns
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 15
    
    def _create_inventory_status_sheet(self, wb: Workbook):
        """Create current inventory status sheet"""
        
        ws = wb.create_sheet("Current Inventory")
        
        try:
            # Get current inventory data
            db = database.get_database_connection()
            cursor = db.cursor(pymysql.cursors.DictCursor)
            
            query = """
            SELECT 
                s.sku_id,
                s.description,
                s.supplier,
                ic.burnaby_qty,
                ic.kentucky_qty,
                (ic.burnaby_qty + ic.kentucky_qty) as total_qty,
                s.cost_per_unit,
                (ic.kentucky_qty * s.cost_per_unit) as kentucky_value,
                ic.last_updated
            FROM skus s
            LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
            WHERE s.status = 'Active'
            ORDER BY ic.kentucky_qty ASC, s.sku_id
            """
            
            cursor.execute(query)
            inventory_data = cursor.fetchall()
            db.close()
            
            # Headers
            headers = ["SKU", "Description", "Supplier", "Burnaby Qty", "Kentucky Qty", 
                      "Total Qty", "Unit Cost", "KY Value", "Last Updated"]
            
            # Write headers
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")
            
            # Write data
            for row, item in enumerate(inventory_data, 2):
                for col, header in enumerate(headers, 1):
                    key = header.lower().replace(' ', '_').replace('#', '').replace('/', '_')
                    if key == 'ky_value':
                        key = 'kentucky_value'
                    
                    value = item.get(key, '')
                    ws.cell(row=row, column=col, value=value)
                    
                    # Color code out of stock items
                    if col == 5 and value == 0:  # Kentucky Qty column
                        for c in range(1, len(headers) + 1):
                            ws.cell(row=row, column=c).fill = PatternFill(
                                start_color="FFEBEE", end_color="FFEBEE", fill_type="solid"
                            )
            
            # Auto-adjust columns
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 40)
                ws.column_dimensions[column_letter].width = adjusted_width
                
        except Exception as e:
            ws.cell(row=1, column=1, value=f"Error loading inventory data: {str(e)}")
            logger.error(f"Error creating inventory status sheet: {str(e)}")
    
    # =============================================================================
    # CSV IMPORT/EXPORT FUNCTIONALITY
    # =============================================================================
    
    def export_csv(self, data: List[Dict], filename_prefix: str = "export") -> bytes:
        """Export data to CSV format"""
        
        if not data:
            return b"No data to export"
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Convert to CSV
        output = io.StringIO()
        df.to_csv(output, index=False)
        
        return output.getvalue().encode('utf-8')
    
    def import_csv_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Import CSV file with validation"""
        
        try:
            # Read CSV
            df = pd.read_csv(io.StringIO(file_content.decode('utf-8')))
            
            # Process similar to Excel import
            return self._auto_detect_and_import(df, filename)
            
        except Exception as e:
            logger.error(f"CSV import failed: {str(e)}")
            return {
                "success": False,
                "filename": filename,
                "error": f"CSV import failed: {str(e)}",
                "import_timestamp": datetime.now().isoformat()
            }

# Global instance
import_export_manager = ImportExportManager()