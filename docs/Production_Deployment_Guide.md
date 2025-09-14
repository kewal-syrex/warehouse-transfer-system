# Production Deployment Guide - Pending Orders System v2.0

## Overview

This guide provides step-by-step instructions for deploying the enhanced warehouse transfer system with pending orders management to production.

## 🎯 What's Being Deployed

### New Features
- **Pending Orders Management** - Complete CSV import/export system
- **Enhanced Transfer Calculations** - Burnaby retention logic with pending orders integration
- **Configuration Management** - System settings and supplier-specific overrides
- **Excel Export Enhancements** - Multi-sheet reports with coverage analysis
- **Comprehensive API Documentation** - OpenAPI specs with interactive docs

### System Requirements
- **Database**: MySQL 8.0+ or MariaDB 10.5+
- **Python**: 3.9+
- **Storage**: Additional 100MB for new features
- **Memory**: No additional requirements
- **Network**: Existing ports (8000 for development, 80/443 for production)

---

## 🚨 Pre-Deployment Checklist

### 1. Backup Strategy
```bash
# Create full database backup
mysqldump -u [username] -p warehouse_transfer > warehouse_transfer_backup_$(date +%Y%m%d).sql

# Backup application files
tar -czf warehouse_transfer_app_backup_$(date +%Y%m%d).tar.gz /path/to/warehouse-transfer/
```

### 2. Test Environment Validation
- [ ] All new features tested in staging
- [ ] Performance benchmarks met (response time <5 seconds)
- [ ] CSV import tested with various file formats
- [ ] Excel export generates correctly
- [ ] Configuration system working
- [ ] Playwright test suite passes

### 3. Dependency Check
```bash
# Verify Python packages
pip install -r requirements.txt

# Verify database connectivity
python -c "import pymysql; print('PyMySQL available')"
```

---

## 📋 Deployment Steps

### Step 1: Stop Application Services
```bash
# Stop the application (adjust for your deployment)
sudo systemctl stop warehouse-transfer
# or
pkill -f "uvicorn.*main:app"
```

### Step 2: Deploy Application Code
```bash
# Update codebase
cd /path/to/warehouse-transfer
git pull origin main

# Update Python dependencies
pip install -r requirements.txt

# Verify new modules are available
python -c "import settings; print('Settings module loaded successfully')"
```

### Step 3: Database Migration
```bash
# Run the production deployment script
mysql -u [username] -p warehouse_transfer < database/production_deployment.sql

# Verify migration success
mysql -u [username] -p warehouse_transfer -e "
SELECT 'Configuration Settings' as CHECK_TYPE, COUNT(*) as COUNT FROM system_config
UNION ALL
SELECT 'Supplier Lead Times' as CHECK_TYPE, COUNT(*) as COUNT FROM supplier_lead_times;"
```

**Expected Output:**
```
CHECK_TYPE              COUNT
Configuration Settings    10
Supplier Lead Times        4
```

### Step 4: Validate Database Changes
```bash
# Check new tables exist
mysql -u [username] -p warehouse_transfer -e "SHOW TABLES LIKE '%config%'; SHOW TABLES LIKE '%supplier%';"

# Check new columns added
mysql -u [username] -p warehouse_transfer -e "DESCRIBE pending_inventory; DESCRIBE skus;"

# Verify views created
mysql -u [username] -p warehouse_transfer -e "SHOW FULL TABLES WHERE Table_type = 'VIEW';"
```

### Step 5: Configuration Verification
```bash
# Test configuration management
curl -s http://localhost:8000/api/config/settings | jq '.'

# Test effective lead time calculation
curl -s "http://localhost:8000/api/config/effective-lead-time?supplier=Acme%20Corp" | jq '.'
```

### Step 6: Start Application Services
```bash
# Start application (adjust for your deployment)
sudo systemctl start warehouse-transfer
# or for development
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

### Step 7: Smoke Tests
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test new pending orders endpoint
curl http://localhost:8000/api/pending-orders

# Test enhanced transfer recommendations
curl "http://localhost:8000/api/transfer-recommendations?enhanced=true&limit=3"

# Test configuration endpoints
curl http://localhost:8000/api/config/settings
```

### Step 8: Comprehensive Testing
```bash
# Run the automated test suite
cd tests
python playwright_pending_orders_test.py
```

**Expected Results:**
- API Tests: 8-12 passed, 0 failed
- UI Tests: 3-5 passed, 0 failed
- Success Rate: >90%

---

## 🧪 Post-Deployment Validation

### 1. Feature Testing Checklist

#### Pending Orders Management ✅
- [ ] Navigate to Data Management page
- [ ] Import sample CSV file with pending orders
- [ ] Verify data appears in preview table
- [ ] Check mixed imports (with/without dates) work correctly
- [ ] Confirm auto-date calculation (Today + 120 days)

#### Enhanced Transfer Calculations ✅
- [ ] Access Transfer Planning page
- [ ] Verify new columns: Pending CA, Pending KY, Coverage After
- [ ] Check transfer reasons mention pending orders
- [ ] Confirm Burnaby retention logic prevents over-transferring

#### Excel Export Enhancement ✅
- [ ] Generate Excel export of transfer orders
- [ ] Verify file contains 5 sheets: Transfer Orders, Pending Orders, Coverage Analysis, Summary, Inventory Status
- [ ] Check pending orders data appears in Transfer Orders sheet
- [ ] Confirm coverage projections are calculated

#### Configuration Management ✅
- [ ] Access `/api/docs` and verify Configuration section
- [ ] Test updating a configuration setting
- [ ] Add supplier-specific lead time override
- [ ] Verify effective lead time calculation uses override

### 2. Performance Validation
```bash
# Test with large dataset (4K+ SKUs)
time curl -s "http://localhost:8000/api/transfer-recommendations?enhanced=true" | jq length

# Expected: Response time < 5 seconds, returns >100 recommendations

# Test Excel export performance
time curl -s -o test_export.xlsx "http://localhost:8000/api/export/excel/transfer-orders"

# Expected: File generated in < 10 seconds, size 200KB-2MB
```

### 3. Data Integrity Checks
```sql
-- Verify pending orders integration
SELECT
    pi.sku_id,
    pi.quantity,
    pi.destination,
    pi.expected_arrival,
    pi.is_estimated,
    s.description
FROM pending_inventory pi
JOIN skus s ON pi.sku_id = s.sku_id
WHERE pi.status = 'pending'
LIMIT 5;

-- Check configuration defaults
SELECT config_key, config_value, category
FROM system_config
WHERE category IN ('lead_times', 'coverage')
ORDER BY category, config_key;

-- Verify supplier overrides
SELECT supplier, lead_time_days, destination, notes
FROM supplier_lead_times
ORDER BY supplier;
```

---

## 🔧 Configuration Guide

### 1. System Configuration
Access configuration at: `/api/config/settings`

**Key Settings to Review:**
```json
{
  "default_lead_time_days": 120,
  "burnaby_min_coverage_months": 2.0,
  "burnaby_target_coverage_months": 6.0,
  "burnaby_coverage_with_pending": 1.5,
  "enable_stockout_override": true
}
```

### 2. Supplier Lead Time Setup
**Common Configurations:**
- **Local suppliers**: 7-30 days
- **Domestic suppliers**: 30-90 days
- **International suppliers**: 90-180 days
- **Express shipping**: 1-7 days

**API Example:**
```bash
curl -X POST "http://localhost:8000/api/config/supplier-lead-times" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier": "FastShip Express",
    "lead_time_days": 7,
    "destination": "burnaby",
    "notes": "Express shipping to Burnaby warehouse"
  }'
```

### 3. User Training Materials
- **API Documentation**: Available at `/api/docs`
- **User Guide**: `docs/Pending_Orders_User_Guide.md`
- **Import Templates**: Create sample CSV files for users

---

## 🚨 Rollback Procedures

### If Issues Arise:

#### 1. Application Rollback
```bash
# Stop current version
sudo systemctl stop warehouse-transfer

# Restore previous version
cd /path/to/warehouse-transfer
git checkout [previous-commit-hash]
pip install -r requirements.txt

# Start previous version
sudo systemctl start warehouse-transfer
```

#### 2. Database Rollback
```bash
# Restore database backup
mysql -u [username] -p warehouse_transfer < warehouse_transfer_backup_YYYYMMDD.sql
```

#### 3. Selective Rollback
If only specific features are problematic:
```sql
-- Disable enhanced calculations (fallback to basic mode)
UPDATE system_config
SET config_value = 'false'
WHERE config_key = 'enable_enhanced_calculations';

-- Remove problematic pending orders
DELETE FROM pending_inventory WHERE created_at > '[deployment-date]';
```

---

## 📊 Monitoring & Maintenance

### 1. Key Metrics to Monitor
- **API Response Times**: Target <5 seconds for enhanced calculations
- **Import Success Rate**: Target >95% for CSV imports
- **Error Rates**: Monitor application logs for 500 errors
- **Database Performance**: Watch for slow queries on new views

### 2. Log Monitoring
```bash
# Monitor application logs
tail -f app.log | grep -E "(ERROR|WARN|pending|config)"

# Database slow query log
mysql -u [username] -p -e "SHOW PROCESSLIST;"
```

### 3. Regular Maintenance Tasks
- **Weekly**: Review pending orders for completed/cancelled items
- **Monthly**: Analyze configuration usage and optimize settings
- **Quarterly**: Performance review and index optimization

### 4. Health Check Script
Create a monitoring script:
```bash
#!/bin/bash
# health_check.sh

echo "=== Warehouse Transfer System Health Check ==="

# API Health
API_STATUS=$(curl -s http://localhost:8000/health | jq -r '.status')
echo "API Status: $API_STATUS"

# Database connectivity
DB_STATUS=$(mysql -u [username] -p[password] warehouse_transfer -e "SELECT 1" 2>/dev/null && echo "OK" || echo "ERROR")
echo "Database Status: $DB_STATUS"

# Configuration check
CONFIG_COUNT=$(curl -s http://localhost:8000/api/config/settings | jq '.total_settings')
echo "Configuration Settings: $CONFIG_COUNT"

# Pending orders check
PENDING_COUNT=$(curl -s http://localhost:8000/api/pending-orders | jq 'length')
echo "Pending Orders: $PENDING_COUNT"

echo "Health check completed: $(date)"
```

---

## 📞 Support & Troubleshooting

### Common Issues

**Issue**: CSV import fails with "SKU not found" errors
**Solution**: Verify SKU IDs match database exactly (case-sensitive)
**Check**: `SELECT sku_id FROM skus WHERE status = 'Active' LIMIT 10;`

**Issue**: Enhanced calculations not showing pending orders
**Solution**: Verify pending orders have status 'pending', 'ordered', or 'shipped'
**Check**: `SELECT status, COUNT(*) FROM pending_inventory GROUP BY status;`

**Issue**: Configuration changes not taking effect
**Solution**: Restart application services
**Check**: Monitor logs for configuration loading messages

**Issue**: Excel export fails or incomplete
**Solution**: Check database connections and verify all views exist
**Check**: `SHOW FULL TABLES WHERE Table_type = 'VIEW';`

### Support Contacts
- **Technical Issues**: System Administrator
- **Configuration Changes**: Database Administrator
- **User Training**: Department Manager
- **Emergency Rollback**: On-call Engineer

### Documentation Links
- **API Documentation**: `/api/docs`
- **User Guide**: `docs/Pending_Orders_User_Guide.md`
- **Technical Specs**: `docs/API_Documentation_v2.md`

---

## ✅ Deployment Success Criteria

Mark deployment as successful when:

- [ ] All automated tests pass (>90% success rate)
- [ ] API endpoints respond within performance targets
- [ ] CSV import processes sample files without errors
- [ ] Excel export generates complete multi-sheet reports
- [ ] Configuration management functions correctly
- [ ] Users can access and use new features without training
- [ ] No increase in error rates or performance degradation
- [ ] Database queries perform within acceptable limits

---

*Deployment Guide Version 2.0 - Last Updated: September 2025*