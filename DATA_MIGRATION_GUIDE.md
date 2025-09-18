# Warehouse Transfer System - Complete Data Migration Guide

## Overview

This guide provides complete instructions for migrating your warehouse transfer data from development to production server. Use this when you're ready to deploy with all your data.

## Migration Timeline

### Phase 1: Server Preparation (Can do anytime)
- Set up production server
- Install dependencies
- Configure environment
- Test with empty database

### Phase 2: Data Migration (When data is ready)
- Export complete development database
- Transfer to production server
- Import and validate
- Start production system

---

## Pre-Migration Checklist

Before starting the migration, ensure you have:

### Development Environment
- [ ] All SKUs entered and verified
- [ ] Complete sales history imported
- [ ] Current inventory levels updated
- [ ] Pending orders added (if applicable)
- [ ] System configurations set correctly
- [ ] Test data removed or clearly marked
- [ ] Database optimized and indexes current

### Production Server
- [ ] Python 3.9+ installed
- [ ] MySQL 8.0+ or MariaDB 10.5+ installed
- [ ] Git installed
- [ ] Network connectivity confirmed
- [ ] Sufficient disk space (minimum 10GB)
- [ ] Firewall configured for port 8000

### Access Requirements
- [ ] MySQL root/admin access on development machine
- [ ] MySQL admin access on production server
- [ ] SSH/RDP access to production server
- [ ] File transfer method available (USB, network, cloud)

---

## Step-by-Step Migration Process

### Step 1: Prepare Production Server

#### 1.1 Clone Repository
```bash
cd /opt  # or your preferred directory
git clone https://github.com/arjayp-mv/warehouse-transfer-system.git
cd warehouse-transfer-system
```

#### 1.2 Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

#### 1.3 Configure Database
```sql
-- Connect to MySQL as root
CREATE DATABASE warehouse_transfer;
CREATE USER 'warehouse_user'@'localhost' IDENTIFIED BY 'YourSecurePassword123!';
GRANT ALL PRIVILEGES ON warehouse_transfer.* TO 'warehouse_user'@'localhost';
FLUSH PRIVILEGES;
```

#### 1.4 Configure Environment
```bash
cp .env.production .env
# Edit .env with your database credentials
nano .env
```

### Step 2: Export Development Database

#### 2.1 Run Export Script (Windows Development)
```cmd
cd scripts\migration_toolkit
export_database.bat
```

This creates:
- `warehouse_db_YYYYMMDD_HHMMSS.sql` - Complete database dump
- `warehouse_db_YYYYMMDD_HHMMSS.zip` - Compressed version

#### 2.2 Verify Export
Check that the export file contains:
- All table structures
- All data (SKUs, sales, inventory, etc.)
- Views and triggers
- Configuration data

### Step 3: Transfer Database File

Choose your preferred method:

#### Option A: USB Drive
1. Copy .zip file to USB drive
2. Transport to production server
3. Copy to server

#### Option B: Network Transfer (if on same network)
```bash
# From development machine
scp warehouse_db_*.zip user@production-server:/tmp/

# Or use Windows file sharing
```

#### Option C: Cloud Storage
1. Upload to Google Drive, Dropbox, etc.
2. Download on production server

### Step 4: Import to Production

#### 4.1 Create Pre-Import Backup (Safety)
```bash
cd scripts/migration_toolkit
./backup_production.sh
```

#### 4.2 Import Database
```bash
# Unzip the file
unzip warehouse_db_*.zip

# Import to MySQL
./import_to_server.sh warehouse_db_*.sql
```

#### 4.3 Verify Import
```bash
python verify_migration.py
```

Expected output:
```
=== Migration Verification Report ===
✓ Database connection successful
✓ All tables created (8 tables)
✓ All views created (5 views)
✓ All triggers created (2 triggers)
✓ SKU data: 1,247 records
✓ Sales data: 15,623 records
✓ Inventory data: 1,247 records
✓ Configuration data: 12 settings
=== Migration Successful! ===
```

### Step 5: Start Production System

#### 5.1 Test Application
```bash
cd /opt/warehouse-transfer-system
source venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 5.2 Access and Verify
Open browser to: `http://server-ip:8000/static/index.html`

Check:
- [ ] Dashboard loads with correct metrics
- [ ] Transfer planning shows SKUs
- [ ] Data management displays inventory
- [ ] All features working correctly

#### 5.3 Start Production Service
```bash
# For production use
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Or set up as system service (see deployment guide)
```

---

## Troubleshooting Common Issues

### Export Issues

**Problem**: `mysqldump: command not found`
**Solution**: Add MySQL bin directory to PATH or use full path:
```cmd
"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe" -u root -p warehouse_transfer > backup.sql
```

**Problem**: Export file is very large
**Solution**:
- Use compression: `--single-transaction --routines --triggers | gzip > backup.sql.gz`
- Consider data cleanup before export

### Import Issues

**Problem**: `ERROR 1045: Access denied for user`
**Solution**:
1. Verify database user exists and has permissions
2. Check password in .env file
3. Test connection: `mysql -u warehouse_user -p warehouse_transfer`

**Problem**: `ERROR 1049: Unknown database 'warehouse_transfer'`
**Solution**: Create database first:
```sql
CREATE DATABASE warehouse_transfer;
```

**Problem**: Import stops with foreign key errors
**Solution**: Import with foreign key checks disabled:
```sql
SET FOREIGN_KEY_CHECKS = 0;
SOURCE backup.sql;
SET FOREIGN_KEY_CHECKS = 1;
```

### Application Issues

**Problem**: Can't access from other computers
**Solution**:
1. Use `--host 0.0.0.0` not `--host localhost`
2. Check firewall allows port 8000
3. Verify server IP address

**Problem**: Database connection errors
**Solution**:
1. Verify MySQL service is running
2. Check .env database credentials
3. Test database connection manually

---

## Advanced Migration Options

### Option 1: Automated Migration Script

Use the automated migration tool:
```bash
python scripts/migration_toolkit/quick_migrate.py
```

This handles:
- Development database export
- File compression
- Production backup
- Import and validation
- Service restart

### Option 2: Selective Data Migration

To migrate only specific data:
```bash
# Export only SKUs and inventory
mysqldump -u root -p warehouse_transfer skus inventory_current > partial_backup.sql

# Import specific tables
mysql -u warehouse_user -p warehouse_transfer < partial_backup.sql
```

### Option 3: Network-Direct Migration

For servers on the same network:
```bash
# Direct MySQL-to-MySQL transfer
mysqldump -u root -p warehouse_transfer | mysql -h production-server -u warehouse_user -p warehouse_transfer
```

---

## Data Validation Procedures

### Automatic Validation
The `verify_migration.py` script checks:
- Table existence and structure
- Record counts match
- Data integrity constraints
- View and trigger functionality
- Configuration completeness

### Manual Validation
Additional checks you should perform:

#### 1. SKU Data Integrity
```sql
-- Check SKU count and basic data
SELECT COUNT(*) as total_skus,
       COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_skus,
       COUNT(CASE WHEN description IS NOT NULL THEN 1 END) as with_descriptions
FROM skus;
```

#### 2. Sales History Completeness
```sql
-- Check sales data coverage
SELECT MIN(year_month) as earliest_data,
       MAX(year_month) as latest_data,
       COUNT(DISTINCT sku_id) as skus_with_sales,
       COUNT(*) as total_sales_records
FROM monthly_sales;
```

#### 3. Inventory Accuracy
```sql
-- Verify inventory totals
SELECT SUM(burnaby_qty) as total_burnaby,
       SUM(kentucky_qty) as total_kentucky,
       COUNT(*) as total_sku_records
FROM inventory_current;
```

#### 4. Configuration Settings
```sql
-- Check system configuration
SELECT category, COUNT(*) as setting_count
FROM system_config
GROUP BY category;
```

---

## Rollback Procedures

If migration fails or issues are discovered:

### Immediate Rollback
```bash
# Stop application
pkill -f "uvicorn.*main:app"

# Restore from backup
cd scripts/migration_toolkit
./restore_backup.sh backup_YYYYMMDD_HHMMSS.sql

# Restart with restored data
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Partial Rollback
To rollback only specific tables:
```sql
-- Drop problematic tables
DROP TABLE monthly_sales;

-- Restore specific table from backup
mysql -u warehouse_user -p warehouse_transfer < backup_YYYYMMDD_HHMMSS.sql
```

---

## Performance Optimization

### After Migration
Run these optimization commands:

```sql
-- Update table statistics
ANALYZE TABLE skus, monthly_sales, inventory_current, pending_inventory;

-- Optimize tables
OPTIMIZE TABLE skus, monthly_sales, inventory_current, pending_inventory;

-- Check index usage
SHOW INDEX FROM skus;
SHOW INDEX FROM monthly_sales;
```

### Large Dataset Considerations
For databases with >100,000 records:

1. **Increase MySQL memory**:
```sql
SET GLOBAL innodb_buffer_pool_size = 1073741824; -- 1GB
```

2. **Use MyISAM for read-heavy tables** (optional):
```sql
ALTER TABLE monthly_sales ENGINE=MyISAM;
```

3. **Add monitoring**:
```bash
# Monitor during import
watch 'mysql -u warehouse_user -p warehouse_transfer -e "SELECT COUNT(*) FROM monthly_sales"'
```

---

## Post-Migration Tasks

### 1. Update Documentation
- [ ] Update system documentation with production details
- [ ] Record migration date and any customizations
- [ ] Update user access instructions

### 2. User Training
- [ ] Provide production server access details
- [ ] Train users on new URL/bookmarks
- [ ] Verify all user workflows function correctly

### 3. Monitoring Setup
- [ ] Set up log monitoring
- [ ] Configure backup schedules
- [ ] Test disaster recovery procedures

### 4. Security Review
- [ ] Change default passwords
- [ ] Restrict database access
- [ ] Configure firewall rules
- [ ] Review user permissions

---

## Support and Maintenance

### Regular Maintenance Tasks
- **Daily**: Monitor application logs
- **Weekly**: Check database performance
- **Monthly**: Update dependencies and backup validation
- **Quarterly**: Full system backup and disaster recovery test

### Getting Help
1. Check logs in `/var/log/warehouse-transfer/` or application logs
2. Review this guide for common issues
3. Verify database connectivity and permissions
4. Check system resources (disk space, memory)

### Backup Strategy
- **Automatic daily backups**: Set up cron job for database backup
- **Pre-change backups**: Before any system updates
- **Full system backup**: Monthly complete system backup
- **Test restores**: Quarterly backup restoration test

---

## Migration Checklist Summary

Print this checklist for your migration day:

### Pre-Migration (Development)
- [ ] All data entered and verified
- [ ] Test data removed
- [ ] Database optimized
- [ ] Export scripts tested

### Migration Day
- [ ] Production server prepared
- [ ] Pre-migration backup created
- [ ] Development database exported
- [ ] Files transferred to production
- [ ] Database imported successfully
- [ ] Migration verification passed
- [ ] Application started and tested
- [ ] User access verified

### Post-Migration
- [ ] Documentation updated
- [ ] Users notified of new access details
- [ ] Monitoring configured
- [ ] Backup schedule established
- [ ] Migration completed successfully!

---

**Migration Guide Version 1.0 - Created September 2025**
**For Warehouse Transfer System v2.0**

This guide ensures a smooth, reliable migration of your warehouse transfer data from development to production with zero data loss and minimal downtime.