"""
Supplier Shipment Import Module

This module handles CSV import and validation for supplier shipment history data.
It provides robust validation, error reporting, and data normalization capabilities
for importing historical PO data into the supplier_shipments table.

Key Features:
- CSV file parsing with flexible column detection
- Comprehensive data validation and error reporting
- Supplier name normalization for consistency
- Duplicate PO handling with update logic
- Detailed import results with statistics
- Error categorization (errors vs warnings)

Business Logic:
- PO numbers must be unique
- Received date must be >= order_date
- Supplier names are normalized (UPPER/TRIM)
- Destinations must be 'burnaby' or 'kentucky'
- Lead times are calculated automatically
"""

import csv
import io
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date
import logging

try:
    from . import database
except ImportError:
    import database

logger = logging.getLogger(__name__)


class SupplierImportError(Exception):
    """Custom exception for supplier import operations"""
    pass


class SupplierImporter:
    """
    Main class for importing supplier shipment data from CSV files

    This class provides methods to parse, validate, and import supplier
    shipment history from CSV files with comprehensive error handling
    and data normalization.

    Attributes:
        required_columns: List of required CSV column names
        optional_columns: List of optional CSV column names

    Example:
        importer = SupplierImporter()
        result = importer.import_csv_data(csv_content, 'admin')
    """

    # Required columns for import (case-insensitive matching)
    REQUIRED_COLUMNS = [
        'po_number',
        'supplier',
        'order_date',
        'received_date',
        'destination'
    ]

    # Optional columns
    OPTIONAL_COLUMNS = [
        'was_partial',
        'notes'
    ]

    # Valid destination values
    VALID_DESTINATIONS = ['burnaby', 'kentucky']

    def __init__(self):
        """Initialize the supplier importer"""
        self.validation_errors = []
        self.validation_warnings = []
        self.import_stats = {
            'total_rows': 0,
            'successful_imports': 0,
            'duplicate_updates': 0,
            'skipped_rows': 0,
            'error_rows': 0
        }

    def import_csv_data(self, csv_content: str, uploaded_by: str = 'system') -> Dict[str, Any]:
        """
        Import supplier shipment data from CSV content

        Parses CSV data, validates all records, and imports valid shipments
        into the database with comprehensive error reporting.

        Args:
            csv_content: Raw CSV file content as string
            uploaded_by: Username of person uploading data

        Returns:
            Dict containing:
                - success: Boolean indicating overall success
                - stats: Import statistics (counts of various outcomes)
                - errors: List of validation errors
                - warnings: List of validation warnings
                - imported_records: Number of successfully imported records

        Raises:
            SupplierImportError: If CSV parsing fails or critical errors occur
            DatabaseError: If database operations fail
        """
        try:
            # Reset statistics for new import
            self._reset_import_stats()

            # Parse CSV content
            parsed_data = self._parse_csv_content(csv_content)

            if not parsed_data:
                raise SupplierImportError("No valid data found in CSV file")

            # Validate all records
            validated_records = []
            for row_num, record in enumerate(parsed_data, start=2):  # Start at 2 for header
                try:
                    validated_record = self._validate_record(record, row_num)
                    if validated_record:
                        validated_records.append(validated_record)

                except Exception as e:
                    self._add_error(f"Row {row_num}: {str(e)}")
                    self.import_stats['error_rows'] += 1

            # Import validated records
            if validated_records:
                imported_count = self._import_validated_records(validated_records, uploaded_by)
                self.import_stats['successful_imports'] = imported_count

            # Compile results
            result = {
                'success': self.import_stats['error_rows'] == 0,
                'stats': self.import_stats.copy(),
                'errors': self.validation_errors.copy(),
                'warnings': self.validation_warnings.copy(),
                'imported_records': self.import_stats['successful_imports'],
                'total_processed': self.import_stats['total_rows']
            }

            logger.info(f"CSV import completed: {result['imported_records']} records imported, {len(result['errors'])} errors")
            return result

        except Exception as e:
            logger.error(f"CSV import failed: {str(e)}")
            raise SupplierImportError(f"Import failed: {str(e)}")

    def validate_csv_format(self, csv_content: str) -> Dict[str, Any]:
        """
        Validate CSV format without importing data

        Checks CSV structure, column headers, and data format
        without performing database operations.

        Args:
            csv_content: Raw CSV file content as string

        Returns:
            Dict containing validation results and format information

        Raises:
            SupplierImportError: If CSV format is invalid
        """
        try:
            # Reset validation state
            self._reset_import_stats()

            # Parse headers only
            csv_file = io.StringIO(csv_content)
            csv_reader = csv.DictReader(csv_file)

            if not csv_reader.fieldnames:
                raise SupplierImportError("CSV file appears to be empty or invalid")

            # Validate column headers
            header_validation = self._validate_headers(csv_reader.fieldnames)

            # Sample validation (first 10 rows)
            sample_errors = []
            sample_warnings = []
            row_count = 0

            for row_num, record in enumerate(csv_reader, start=2):
                row_count += 1
                if row_count > 10:  # Only validate first 10 rows
                    break

                try:
                    self._validate_record_format(record, row_num)
                except Exception as e:
                    sample_errors.append(f"Row {row_num}: {str(e)}")

            # Count total rows
            csv_file.seek(0)
            total_rows = sum(1 for line in csv_file) - 1  # Subtract header

            result = {
                'valid_format': len(sample_errors) == 0,
                'headers': header_validation,
                'total_rows': total_rows,
                'sample_errors': sample_errors[:5],  # First 5 errors only
                'estimated_import_time': self._estimate_import_time(total_rows)
            }

            return result

        except Exception as e:
            logger.error(f"CSV format validation failed: {str(e)}")
            raise SupplierImportError(f"Format validation failed: {str(e)}")

    def _parse_csv_content(self, csv_content: str) -> List[Dict[str, Any]]:
        """
        Parse CSV content into list of dictionaries

        Args:
            csv_content: Raw CSV content

        Returns:
            List of parsed records

        Raises:
            SupplierImportError: If CSV parsing fails
        """
        try:
            csv_file = io.StringIO(csv_content)
            csv_reader = csv.DictReader(csv_file)

            if not csv_reader.fieldnames:
                raise SupplierImportError("CSV file has no headers")

            # Validate headers
            self._validate_headers(csv_reader.fieldnames)

            # Parse all rows
            records = []
            for row_num, record in enumerate(csv_reader, start=2):
                self.import_stats['total_rows'] += 1

                # Skip empty rows
                if not any(record.values()):
                    continue

                records.append(record)

            return records

        except csv.Error as e:
            raise SupplierImportError(f"CSV parsing error: {str(e)}")

    def _validate_headers(self, headers: List[str]) -> Dict[str, Any]:
        """
        Validate CSV column headers

        Args:
            headers: List of column headers from CSV

        Returns:
            Dict with header validation results

        Raises:
            SupplierImportError: If required headers are missing
        """
        # Normalize headers for case-insensitive comparison
        normalized_headers = {header.lower().strip(): header for header in headers}

        # Check required columns
        missing_columns = []
        for required_col in self.REQUIRED_COLUMNS:
            if required_col.lower() not in normalized_headers:
                missing_columns.append(required_col)

        if missing_columns:
            raise SupplierImportError(f"Missing required columns: {', '.join(missing_columns)}")

        # Map normalized column names to actual headers
        column_mapping = {}
        for col in self.REQUIRED_COLUMNS + self.OPTIONAL_COLUMNS:
            col_lower = col.lower()
            if col_lower in normalized_headers:
                column_mapping[col] = normalized_headers[col_lower]

        return {
            'valid': True,
            'column_mapping': column_mapping,
            'extra_columns': [h for h in headers if h.lower() not in [c.lower() for c in self.REQUIRED_COLUMNS + self.OPTIONAL_COLUMNS]]
        }

    def _validate_record(self, record: Dict[str, str], row_num: int) -> Optional[Dict[str, Any]]:
        """
        Validate and normalize a single CSV record

        Args:
            record: Raw CSV record dictionary
            row_num: Row number for error reporting

        Returns:
            Validated and normalized record, or None if validation fails

        Raises:
            ValueError: If validation fails
        """
        # Normalize column names (case-insensitive access)
        normalized_record = {k.lower().strip(): v for k, v in record.items()}

        # Extract and validate required fields
        po_number = self._validate_po_number(normalized_record.get('po_number', ''), row_num)
        supplier = self._validate_supplier(normalized_record.get('supplier', ''), row_num)
        order_date = self._validate_date(normalized_record.get('order_date', ''), 'order_date', row_num)
        received_date = self._validate_date(normalized_record.get('received_date', ''), 'received_date', row_num)
        destination = self._validate_destination(normalized_record.get('destination', ''), row_num)

        # Extract optional fields
        was_partial = self._validate_boolean(normalized_record.get('was_partial', ''), 'was_partial', row_num, default=False)
        notes = normalized_record.get('notes', '').strip()

        # Create initial validated record
        validated_record = {
            'po_number': po_number,
            'supplier': supplier,
            'order_date': order_date,
            'received_date': received_date,
            'destination': destination,
            'was_partial': was_partial,
            'notes': notes if notes else None
        }

        # Apply business rule validation and enhancements
        validated_record = self._validate_business_rules(validated_record, row_num)

        return validated_record

    def _validate_record_format(self, record: Dict[str, str], row_num: int) -> bool:
        """
        Validate record format without full processing (for format checking)

        Args:
            record: CSV record to validate
            row_num: Row number for error reporting

        Returns:
            True if format is valid

        Raises:
            ValueError: If format validation fails
        """
        normalized_record = {k.lower().strip(): v for k, v in record.items()}

        # Basic format checks
        if not normalized_record.get('po_number', '').strip():
            raise ValueError("PO number is required")

        if not normalized_record.get('supplier', '').strip():
            raise ValueError("Supplier is required")

        # Date format validation
        self._validate_date(normalized_record.get('order_date', ''), 'order_date', row_num)
        self._validate_date(normalized_record.get('received_date', ''), 'received_date', row_num)

        return True

    def _validate_po_number(self, po_number: str, row_num: int) -> str:
        """
        Validate PO number field with enhanced business rules

        Args:
            po_number: Raw PO number value
            row_num: Row number for error reporting

        Returns:
            Cleaned PO number

        Raises:
            ValueError: If PO number is invalid
        """
        po_number = po_number.strip()

        if not po_number:
            raise ValueError("PO number is required")

        if len(po_number) > 50:
            raise ValueError("PO number too long (max 50 characters)")

        # Enhanced validation: Check for reasonable PO format
        if len(po_number) < 3:
            self._add_warning(f"Row {row_num}: PO number '{po_number}' is very short")

        # Check for common invalid patterns
        if po_number.lower() in ['n/a', 'na', 'none', 'null', 'unknown', 'tbd', 'pending']:
            raise ValueError(f"Invalid PO number: '{po_number}' is not a valid purchase order number")

        # Check for special characters that might cause issues
        if re.search(r'[<>"\'\\\n\r\t]', po_number):
            raise ValueError(f"PO number contains invalid characters: '{po_number}'")

        return po_number

    def _validate_supplier(self, supplier: str, row_num: int) -> str:
        """
        Validate and normalize supplier name with enhanced business rules

        Args:
            supplier: Raw supplier name
            row_num: Row number for error reporting

        Returns:
            Normalized supplier name (trimmed, proper case)

        Raises:
            ValueError: If supplier name is invalid
        """
        supplier = supplier.strip()

        if not supplier:
            raise ValueError("Supplier name is required")

        if len(supplier) > 100:
            raise ValueError("Supplier name too long (max 100 characters)")

        # Enhanced validation: Check for placeholder names
        if supplier.lower() in ['n/a', 'na', 'none', 'null', 'unknown', 'tbd', 'pending', 'supplier', 'vendor']:
            raise ValueError(f"Invalid supplier name: '{supplier}' is not a valid supplier")

        # Check minimum length
        if len(supplier) < 2:
            raise ValueError(f"Supplier name too short: '{supplier}'")

        # Check for suspicious patterns
        if re.match(r'^[\d\s\-_\.]+$', supplier):
            self._add_warning(f"Row {row_num}: Supplier name '{supplier}' appears to be numeric/code only")

        # Check for special characters that might cause issues
        if re.search(r'[<>"\'\\\n\r\t]', supplier):
            raise ValueError(f"Supplier name contains invalid characters: '{supplier}'")

        # Normalize for consistency but preserve original casing for display
        return supplier

    def _validate_date(self, date_str: str, field_name: str, row_num: int) -> date:
        """
        Validate and parse date field

        Args:
            date_str: Raw date string
            field_name: Name of date field for error reporting
            row_num: Row number for error reporting

        Returns:
            Parsed date object

        Raises:
            ValueError: If date is invalid
        """
        date_str = date_str.strip()

        if not date_str:
            raise ValueError(f"{field_name} is required")

        # Try common date formats
        date_formats = [
            '%Y-%m-%d',      # 2024-01-15
            '%m/%d/%Y',      # 01/15/2024
            '%d/%m/%Y',      # 15/01/2024
            '%Y/%m/%d',      # 2024/01/15
            '%m-%d-%Y',      # 01-15-2024
            '%d-%m-%Y'       # 15-01-2024
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()

                # Validate date range (not too far in past or future)
                if parsed_date.year < 2000:
                    self._add_warning(f"Row {row_num}: {field_name} is very old ({parsed_date})")
                elif parsed_date > date.today():
                    raise ValueError(f"{field_name} cannot be in the future")

                return parsed_date

            except ValueError:
                continue

        raise ValueError(f"Invalid date format for {field_name}: '{date_str}'. Expected formats: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, etc.")

    def _validate_destination(self, destination: str, row_num: int) -> str:
        """
        Validate destination field

        Args:
            destination: Raw destination value
            row_num: Row number for error reporting

        Returns:
            Normalized destination (lowercase)

        Raises:
            ValueError: If destination is invalid
        """
        destination = destination.strip().lower()

        if not destination:
            raise ValueError("Destination is required")

        if destination not in self.VALID_DESTINATIONS:
            raise ValueError(f"Invalid destination '{destination}'. Must be one of: {', '.join(self.VALID_DESTINATIONS)}")

        return destination

    def _validate_business_rules(self, record: Dict[str, Any], row_num: int) -> Dict[str, Any]:
        """
        Validate business logic and data quality constraints

        Args:
            record: Validated record data
            row_num: Row number for error reporting

        Returns:
            Record with additional validations

        Raises:
            ValueError: If business rules are violated
        """
        # Calculate lead time for validation
        order_date = record['order_date']
        received_date = record['received_date']
        lead_time = (received_date - order_date).days

        # Business rule: Lead time must be reasonable (0-365 days)
        if lead_time < 0:
            raise ValueError("Received date cannot be before order date")

        if lead_time > 365:
            self._add_warning(f"Row {row_num}: Very long lead time ({lead_time} days) - please verify dates")

        if lead_time == 0:
            self._add_warning(f"Row {row_num}: Same-day delivery (lead time 0 days)")

        # Business rule: Reasonable date ranges
        current_date = date.today()
        if order_date > current_date:
            raise ValueError("Order date cannot be in the future")

        if received_date > current_date:
            self._add_warning(f"Row {row_num}: Received date is in the future - using current date for calculations")

        # Data quality: Very old records
        days_since_order = (current_date - order_date).days
        if days_since_order > 2 * 365:  # 2 years
            self._add_warning(f"Row {row_num}: Very old order date ({order_date}) - may affect trend analysis")

        # Add calculated lead time to record
        record['calculated_lead_time'] = lead_time

        return record

    def _validate_boolean(self, value: str, field_name: str, row_num: int, default: bool = False) -> bool:
        """
        Validate boolean field

        Args:
            value: Raw boolean value
            field_name: Field name for error reporting
            row_num: Row number for error reporting
            default: Default value if empty

        Returns:
            Boolean value

        Raises:
            ValueError: If boolean value is invalid
        """
        if not value.strip():
            return default

        value = value.strip().lower()

        if value in ['true', 'yes', '1', 'y', 't']:
            return True
        elif value in ['false', 'no', '0', 'n', 'f']:
            return False
        else:
            raise ValueError(f"Invalid boolean value for {field_name}: '{value}'. Use true/false, yes/no, or 1/0")

    def _import_validated_records(self, records: List[Dict[str, Any]], uploaded_by: str) -> int:
        """
        Import validated records into database

        Args:
            records: List of validated records
            uploaded_by: Username of uploader

        Returns:
            Number of successfully imported records

        Raises:
            DatabaseError: If database operations fail
        """
        imported_count = 0

        try:
            connection = database.get_database_connection()

            for record in records:
                try:
                    # Check if PO already exists
                    with connection.cursor() as cursor:
                        check_query = "SELECT id FROM supplier_shipments WHERE po_number = %s"
                        cursor.execute(check_query, (record['po_number'],))
                        existing = cursor.fetchone()

                        if existing:
                            # Update existing record
                            update_query = """
                                UPDATE supplier_shipments SET
                                    supplier = %s,
                                    order_date = %s,
                                    received_date = %s,
                                    destination = %s,
                                    was_partial = %s,
                                    notes = %s,
                                    uploaded_at = CURRENT_TIMESTAMP,
                                    uploaded_by = %s
                                WHERE id = %s
                            """
                            cursor.execute(update_query, (
                                record['supplier'],
                                record['order_date'],
                                record['received_date'],
                                record['destination'],
                                record['was_partial'],
                                record['notes'],
                                uploaded_by,
                                existing[0]
                            ))
                            self.import_stats['duplicate_updates'] += 1
                        else:
                            # Insert new record
                            insert_query = """
                                INSERT INTO supplier_shipments (
                                    po_number, supplier, order_date, received_date,
                                    destination, was_partial, notes, uploaded_by
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            cursor.execute(insert_query, (
                                record['po_number'],
                                record['supplier'],
                                record['order_date'],
                                record['received_date'],
                                record['destination'],
                                record['was_partial'],
                                record['notes'],
                                uploaded_by
                            ))

                        imported_count += 1

                except Exception as e:
                    logger.warning(f"Failed to import record {record.get('po_number', 'unknown')}: {str(e)}")
                    continue

            connection.commit()
            logger.info(f"Successfully imported {imported_count} supplier shipment records")

        except Exception as e:
            logger.error(f"Database import failed: {str(e)}")
            raise

        return imported_count

    def _reset_import_stats(self):
        """Reset import statistics for new import operation"""
        self.validation_errors = []
        self.validation_warnings = []
        self.import_stats = {
            'total_rows': 0,
            'successful_imports': 0,
            'duplicate_updates': 0,
            'skipped_rows': 0,
            'error_rows': 0
        }

    def _add_error(self, message: str):
        """Add validation error message"""
        self.validation_errors.append(message)
        logger.warning(f"Validation error: {message}")

    def _add_warning(self, message: str):
        """Add validation warning message"""
        self.validation_warnings.append(message)

    def _estimate_import_time(self, row_count: int) -> str:
        """
        Estimate import time based on row count

        Args:
            row_count: Number of rows to import

        Returns:
            Estimated time string
        """
        # Rough estimate: ~100 records per second
        seconds = max(1, row_count // 100)

        if seconds < 60:
            return f"~{seconds} seconds"
        elif seconds < 3600:
            return f"~{seconds // 60} minutes"
        else:
            return f"~{seconds // 3600} hours"


def get_supplier_importer() -> SupplierImporter:
    """
    Factory function to create SupplierImporter instance

    Returns:
        Configured SupplierImporter instance
    """
    return SupplierImporter()