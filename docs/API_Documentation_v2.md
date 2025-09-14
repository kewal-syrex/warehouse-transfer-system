# Warehouse Transfer Planning System - API Documentation v2.0

## Overview

The Warehouse Transfer Planning System provides intelligent inventory transfer recommendations with advanced features including:

- **Pending Orders Management** - Track in-transit inventory and adjust recommendations
- **Stockout Override System** - Handle inventory accuracy issues with database-driven overrides
- **Enhanced Transfer Calculations** - Sophisticated algorithms with Burnaby retention logic
- **Configuration Management** - Flexible system settings and supplier-specific overrides
- **Comprehensive Import/Export** - Excel and CSV support with validation

## Base URL

```
Production: https://your-domain.com/api
Development: http://localhost:8000/api
```

## Authentication

Currently, the system operates without authentication. In production, implement appropriate authentication middleware.

---

## API Endpoints

### Core System Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-13T10:30:00Z",
  "database_connected": true,
  "version": "1.0.0"
}
```

---

### SKU Management

#### Get All SKUs
```http
GET /api/skus
```

**Query Parameters:**
- `status` (optional): Filter by status (Active, Discontinued, Death_Row)
- `limit` (optional): Limit results (default: 100)

**Response:**
```json
[
  {
    "sku_id": "CHG-001",
    "description": "Sample Product",
    "supplier": "Acme Corp",
    "cost_per_unit": 25.50,
    "status": "Active",
    "abc_code": "A",
    "xyz_code": "X",
    "transfer_multiple": 100,
    "category": "Electronics"
  }
]
```

#### Update SKU
```http
PUT /api/skus/{sku_id}
```

**Request Body:**
```json
{
  "description": "Updated Product Name",
  "supplier": "New Supplier",
  "cost_per_unit": 30.00,
  "status": "Active",
  "abc_code": "B",
  "xyz_code": "Y",
  "transfer_multiple": 50,
  "category": "Hardware"
}
```

---

### Transfer Recommendations

#### Get Transfer Recommendations
```http
GET /api/transfer-recommendations
```

**Query Parameters:**
- `enhanced` (optional): Use enhanced calculations with pending orders (true/false)
- `limit` (optional): Limit results
- `priority` (optional): Filter by priority (CRITICAL, HIGH, MEDIUM, LOW)

**Response:**
```json
[
  {
    "sku_id": "CHG-001",
    "description": "Sample Product",
    "priority": "HIGH",
    "current_kentucky_qty": 100,
    "current_burnaby_qty": 500,
    "pending_burnaby": 200,
    "pending_kentucky": 0,
    "burnaby_coverage_after": 4.2,
    "kentucky_coverage_after": 2.1,
    "corrected_monthly_demand": 150,
    "coverage_months": 0.67,
    "recommended_transfer_qty": 300,
    "abc_class": "A",
    "xyz_class": "X",
    "stockout_override_applied": false,
    "reason": "Kentucky coverage critical (0.67 months). High priority Class AX item.",
    "transfer_multiple": 100,
    "priority_score": 85.2
  }
]
```

---

### Pending Orders Management

#### Get All Pending Orders
```http
GET /api/pending-orders
```

**Query Parameters:**
- `status` (optional): Filter by status (ordered, shipped, pending, received, cancelled)
- `destination` (optional): Filter by destination (burnaby, kentucky)
- `overdue_only` (optional): Show only overdue orders (true/false)

**Response:**
```json
[
  {
    "id": 1,
    "sku_id": "CHG-001",
    "quantity": 500,
    "destination": "kentucky",
    "order_date": "2025-09-01",
    "expected_arrival": "2025-12-30",
    "lead_time_days": 120,
    "is_estimated": true,
    "order_type": "supplier",
    "status": "ordered",
    "notes": "Q4 replenishment order",
    "days_until_arrival": 108,
    "is_overdue": false
  }
]
```

#### Create Pending Order
```http
POST /api/pending-orders
```

**Request Body:**
```json
{
  "sku_id": "CHG-001",
  "quantity": 500,
  "destination": "kentucky",
  "order_date": "2025-09-01",
  "expected_arrival": "2025-12-30",
  "lead_time_days": 120,
  "is_estimated": false,
  "order_type": "supplier",
  "status": "ordered",
  "notes": "Q4 replenishment order"
}
```

#### Update Pending Order
```http
PUT /api/pending-orders/{order_id}
```

#### Delete Pending Order
```http
DELETE /api/pending-orders/{order_id}
```

#### Get Pending Orders Summary
```http
GET /api/pending-orders/summary
```

**Response:**
```json
{
  "total_pending_orders": 156,
  "total_pending_quantity": 45200,
  "orders_by_status": {
    "ordered": 89,
    "shipped": 45,
    "pending": 22
  },
  "orders_by_destination": {
    "burnaby": 78,
    "kentucky": 78
  },
  "overdue_orders": 12,
  "estimated_vs_confirmed": {
    "estimated": 134,
    "confirmed": 22
  },
  "upcoming_arrivals_30_days": 67
}
```

---

### Configuration Management

#### Get All Configuration Settings
```http
GET /api/config/settings
```

**Query Parameters:**
- `category` (optional): Filter by category (lead_times, coverage, business_rules, import_export)

**Response:**
```json
{
  "success": true,
  "settings": {
    "default_lead_time_days": {
      "value": 120,
      "raw_value": "120",
      "data_type": "int",
      "category": "lead_times",
      "description": "Default lead time in days for pending orders"
    },
    "burnaby_min_coverage_months": {
      "value": 2.0,
      "raw_value": "2.0",
      "data_type": "float",
      "category": "coverage",
      "description": "Never transfer below this coverage threshold"
    }
  },
  "categories": ["lead_times", "coverage", "business_rules"],
  "total_settings": 10
}
```

#### Update Configuration Setting
```http
PUT /api/config/settings/{key}
```

**Request Body:**
```json
{
  "key": "default_lead_time_days",
  "value": "150",
  "data_type": "int",
  "category": "lead_times",
  "description": "Default lead time in days for pending orders"
}
```

#### Get Supplier Lead Time Overrides
```http
GET /api/config/supplier-lead-times
```

**Response:**
```json
{
  "success": true,
  "supplier_lead_times": [
    {
      "supplier": "Acme Corp",
      "lead_time_days": 90,
      "destination": null,
      "notes": "Standard supplier with 3-month lead time",
      "created_at": "2025-09-01T10:00:00Z",
      "updated_at": "2025-09-01T10:00:00Z"
    }
  ],
  "total_overrides": 4
}
```

#### Create Supplier Lead Time Override
```http
POST /api/config/supplier-lead-times
```

**Request Body:**
```json
{
  "supplier": "FastShip LLC",
  "lead_time_days": 30,
  "destination": "burnaby",
  "notes": "Express shipping to Burnaby only"
}
```

#### Get Effective Lead Time
```http
GET /api/config/effective-lead-time?supplier=Acme%20Corp&destination=kentucky
```

**Response:**
```json
{
  "supplier": "Acme Corp",
  "destination": "kentucky",
  "effective_lead_time_days": 90,
  "source": "supplier_override"
}
```

---

### Import/Export Operations

#### Import Pending Orders CSV
```http
POST /api/import/pending-orders
```

**Content-Type:** `multipart/form-data`

**Form Data:**
- `file`: CSV file with pending orders data

**CSV Format:**
```csv
sku_id,quantity,destination,expected_date,order_type,notes
CHG-001,500,kentucky,2025-12-30,supplier,Q4 order
CBL-002,300,burnaby,,transfer,Internal transfer
```

**Response:**
```json
{
  "success": true,
  "filename": "pending_orders.csv",
  "import_timestamp": "2025-09-13T10:30:00Z",
  "records_imported": 15,
  "errors": [],
  "warnings": [
    "Found 3 empty date fields (will use default)",
    "Successfully parsed 12 expected dates"
  ],
  "summary": {
    "total_records": 15,
    "skus_processed": 12,
    "destinations": ["burnaby", "kentucky"],
    "confirmed_dates": 12,
    "estimated_dates": 3,
    "mixed_import": true,
    "lead_time_used": 120
  }
}
```

#### Export Transfer Orders to Excel
```http
GET /api/export/excel/transfer-orders
```

**Response:** Binary Excel file with multiple sheets:
- **Transfer Orders**: Enhanced recommendations with pending orders and coverage analysis
- **Pending Orders**: All current pending orders with detailed information
- **Coverage Analysis**: Current vs projected coverage with pending orders impact
- **Summary**: Key statistics and priority distribution
- **Inventory Status**: Complete inventory status report

---

### Stockout Management

#### Bulk Update Stockout Status
```http
POST /api/stockouts/bulk-update
```

**Request Body:**
```json
{
  "updates": [
    {
      "sku_id": "CHG-001",
      "warehouse": "kentucky",
      "status": "out_of_stock",
      "stockout_date": "2025-09-13",
      "notes": "Supplier delay"
    }
  ]
}
```

#### Get Current Stockouts
```http
GET /api/stockouts/current
```

**Query Parameters:**
- `warehouse` (optional): Filter by warehouse (burnaby, kentucky)

---

## Data Models

### Pending Order Model
```json
{
  "id": "integer",
  "sku_id": "string (required)",
  "quantity": "integer (required, > 0)",
  "destination": "string (required, 'burnaby' or 'kentucky')",
  "order_date": "date (optional, defaults to today)",
  "expected_arrival": "date (optional, calculated if missing)",
  "lead_time_days": "integer (optional, 1-365, defaults to 120)",
  "is_estimated": "boolean (auto-calculated)",
  "order_type": "string (optional, defaults to 'supplier')",
  "status": "string (required, defaults to 'pending')",
  "notes": "string (optional)"
}
```

### Configuration Setting Model
```json
{
  "key": "string (required)",
  "value": "string (required)",
  "data_type": "string (required, 'string'|'int'|'float'|'bool'|'json')",
  "category": "string (optional, defaults to 'general')",
  "description": "string (optional)",
  "is_system": "boolean (optional, defaults to false)"
}
```

### Supplier Lead Time Model
```json
{
  "supplier": "string (required)",
  "lead_time_days": "integer (required, 1-365)",
  "destination": "string (optional, 'burnaby' or 'kentucky')",
  "notes": "string (optional)"
}
```

---

## Business Logic

### Enhanced Transfer Calculations

The enhanced calculation engine incorporates:

1. **Pending Orders Integration**: Considers in-transit inventory when calculating transfer needs
2. **Burnaby Retention Logic**: Maintains minimum coverage thresholds
3. **Stockout Override System**: Overrides quantities for marked out-of-stock items
4. **Seasonal Pattern Detection**: Adjusts for seasonal demand patterns
5. **Priority Scoring**: Scientific 100-point scoring system

### Configuration Parameters

- `default_lead_time_days`: Default lead time for pending orders (120 days)
- `burnaby_min_coverage_months`: Minimum Burnaby coverage threshold (2.0 months)
- `burnaby_target_coverage_months`: Target Burnaby coverage (6.0 months)
- `burnaby_coverage_with_pending`: Reduced coverage when pending < 45 days (1.5 months)

### Import Validation Rules

1. **Required Fields**: sku_id, quantity, destination
2. **SKU Validation**: Must exist in active SKU database
3. **Destination Validation**: Must be 'burnaby' or 'kentucky'
4. **Quantity Validation**: Must be positive integer
5. **Date Handling**: Auto-calculates missing dates using default lead time
6. **Mixed Imports**: Supports rows with and without expected dates

---

## Error Handling

### HTTP Status Codes

- `200 OK`: Successful operation
- `400 Bad Request`: Invalid request data
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation errors
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
  "detail": "Detailed error message",
  "status_code": 400,
  "error_type": "ValidationError"
}
```

### Import Error Format
```json
{
  "success": false,
  "filename": "import_file.csv",
  "errors": [
    "Row 3: SKU 'INVALID-001' not found",
    "Row 5: Invalid destination 'mars_warehouse'"
  ],
  "warnings": [
    "3 records had estimated dates calculated"
  ],
  "records_imported": 12,
  "error_count": 2
}
```

---

## Rate Limits

Currently no rate limits are implemented. In production, consider implementing:
- API rate limiting per client
- Import file size limits (recommended: 10MB max)
- Concurrent operation limits

---

## Changelog

### v2.0 (September 2025)
- Added comprehensive pending orders management
- Implemented configuration management system
- Enhanced Excel export with pending orders analysis
- Added supplier-specific lead time overrides
- Improved import validation with mixed date support
- Added comprehensive OpenAPI documentation

### v1.0 (August 2025)
- Initial release with basic transfer recommendations
- SKU management and inventory tracking
- Basic import/export functionality
- Stockout detection and correction

---

## Support

For technical support or feature requests:
- Review the interactive API documentation at `/api/docs`
- Check the ReDoc documentation at `/api/redoc`
- Refer to the system health endpoint at `/health`

---

*This documentation is automatically generated from the OpenAPI schema. For the most up-to-date interactive documentation, visit `/api/docs` in your browser.*