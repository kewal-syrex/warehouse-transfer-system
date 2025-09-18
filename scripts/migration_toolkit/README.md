# Migration Toolkit - Warehouse Transfer System

This directory contains all the tools you need to migrate your warehouse transfer data from development to production server.

## 📁 Files in This Toolkit

| File | Purpose | Platform |
|------|---------|----------|
| **export_database.bat** | Export complete database from development | Windows |
| **import_to_server.sh** | Import database to production server | Linux/Mac |
| **backup_production.sh** | Create backup before migration | Linux/Mac |
| **verify_migration.py** | Verify migration was successful | Cross-platform |
| **README.md** | This documentation file | - |

## 🚀 Quick Migration Process

### Step 1: Export from Development (Windows)
```cmd
cd scripts\migration_toolkit
export_database.bat
```
**Output**: `warehouse_db_YYYYMMDD_HHMMSS.zip`

### Step 2: Transfer to Server
- Copy the .zip file to your production server
- Use USB drive, network share, or cloud storage

### Step 3: Import to Production (Linux/Server)
```bash
cd scripts/migration_toolkit
./backup_production.sh  # Create safety backup
./import_to_server.sh warehouse_db_YYYYMMDD_HHMMSS.zip
```

### Step 4: Verify Migration
```bash
python verify_migration.py
```

## 📋 Detailed Usage Instructions

### export_database.bat (Windows Development Machine)

**Purpose**: Export complete database with all data from your development environment.

**Requirements**:
- Windows with MySQL installed
- Development database with data ready to migrate
- MySQL user with export privileges

**Usage**:
```cmd
# Navigate to the toolkit directory
cd scripts\migration_toolkit

# Run the export script
export_database.bat
```

**What it does**:
- Exports complete database structure and data
- Creates timestamped backup file
- Compresses the backup for easy transfer
- Validates the export was successful

**Output files**:
- `warehouse_db_YYYYMMDD_HHMMSS.sql` - Full database dump
- `warehouse_db_YYYYMMDD_HHMMSS.zip` - Compressed version (preferred)

**Troubleshooting**:
- If "mysqldump not found": Add MySQL bin directory to PATH
- If export fails: Check MySQL is running and credentials are correct
- If file is very small: May indicate empty database or export error

### import_to_server.sh (Linux/Mac Production Server)

**Purpose**: Import the database backup to your production server.

**Requirements**:
- Linux/Mac server with MySQL installed
- Database user with import privileges
- Backup file from export step

**Usage**:
```bash
# Make script executable (first time only)
chmod +x import_to_server.sh

# Run the import
./import_to_server.sh backup_file.zip [database_name] [username]

# Examples:
./import_to_server.sh warehouse_db_20240914_143022.zip
./import_to_server.sh warehouse_db_20240914_143022.sql warehouse_transfer warehouse_user
```

**What it does**:
- Decompresses backup files automatically (.zip, .gz)
- Creates pre-import backup for safety
- Imports all data and structure
- Verifies import was successful
- Provides detailed progress and error reporting

**Supported file formats**:
- `.sql` - Plain SQL dump
- `.sql.gz` - Gzip compressed
- `.zip` - ZIP compressed

### backup_production.sh (Linux/Mac Production Server)

**Purpose**: Create a backup of existing production data before migration.

**Usage**:
```bash
# Create backup with defaults
./backup_production.sh

# Specify database and user
./backup_production.sh warehouse_transfer warehouse_user
```

**What it creates**:
- `production_backup_YYYYMMDD_HHMMSS.sql.gz` - Compressed backup
- Timestamped file for easy identification
- Can be used to rollback if migration fails

### verify_migration.py (Cross-platform)

**Purpose**: Comprehensive verification that migration was successful.

**Requirements**:
- Python 3.6+
- pymysql package (`pip install pymysql`)
- Access to production database

**Usage**:
```bash
# Verify with defaults
python verify_migration.py

# Specify database and user
python verify_migration.py warehouse_transfer warehouse_user
```

**What it checks**:
- ✅ Database connectivity
- ✅ All expected tables exist
- ✅ Table structures are correct
- ✅ Data counts in each table
- ✅ Database views and triggers
- ✅ Indexes for performance
- ✅ Configuration completeness
- ✅ Basic functional tests

**Output**:
- Colored console output with pass/fail status
- Detailed verification report (JSON file)
- Summary of any errors or warnings
- Recommendations for next steps

## 🔧 Advanced Usage

### Network Direct Migration

If your development and production machines are on the same network:

```bash
# Export and transfer in one step
mysqldump -u root -p warehouse_transfer | ssh user@production-server "mysql -u warehouse_user -p warehouse_transfer"
```

### Selective Data Migration

To migrate only specific tables:

```bash
# Export specific tables only
mysqldump -u root -p warehouse_transfer skus inventory_current > partial_backup.sql

# Import specific tables
mysql -u warehouse_user -p warehouse_transfer < partial_backup.sql
```

### Large Database Optimization

For databases with >100,000 records:

```bash
# Export with additional optimization
mysqldump -u root -p --single-transaction --quick --lock-tables=false warehouse_transfer > backup.sql

# Import with progress monitoring
pv backup.sql | mysql -u warehouse_user -p warehouse_transfer
```

## 🚨 Troubleshooting Guide

### Common Export Issues

**Problem**: `mysqldump: command not found`
**Solution**:
- Windows: Add MySQL bin directory to PATH
- Or use full path: `"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"`

**Problem**: Export file is empty or very small
**Solutions**:
- Check if development database has data
- Verify MySQL user has SELECT privileges
- Check for MySQL connection errors

### Common Import Issues

**Problem**: `ERROR 1045: Access denied`
**Solutions**:
- Verify MySQL user exists: `SELECT User FROM mysql.user WHERE User = 'warehouse_user';`
- Check user privileges: `SHOW GRANTS FOR 'warehouse_user'@'localhost';`
- Verify password is correct

**Problem**: `ERROR 1049: Unknown database`
**Solutions**:
- Create database first: `CREATE DATABASE warehouse_transfer;`
- Grant privileges: `GRANT ALL PRIVILEGES ON warehouse_transfer.* TO 'warehouse_user'@'localhost';`

**Problem**: Import stops with foreign key errors
**Solutions**:
- Disable foreign key checks temporarily:
  ```sql
  SET FOREIGN_KEY_CHECKS = 0;
  SOURCE backup.sql;
  SET FOREIGN_KEY_CHECKS = 1;
  ```

### Application Connection Issues

**Problem**: Application can't connect after migration
**Solutions**:
- Check `.env` file has correct database credentials
- Verify MySQL service is running: `systemctl status mysql`
- Test connection manually: `mysql -u warehouse_user -p warehouse_transfer`

## 📊 File Size Guidelines

| Database Content | Expected Size | Notes |
|------------------|---------------|--------|
| Structure only | 10-50 KB | Tables, views, triggers |
| Small dataset (100 SKUs) | 50-200 KB | Basic test data |
| Medium dataset (1000 SKUs) | 500KB-2MB | Typical small business |
| Large dataset (10000+ SKUs) | 5-50MB | Enterprise scale |

## 🔒 Security Notes

- **Never commit database backups to version control**
- **Backup files contain sensitive business data**
- **Use secure transfer methods (SFTP, encrypted USB, etc.)**
- **Delete temporary files after successful migration**
- **Change default passwords before production use**

## 📞 Support

If you encounter issues:

1. **Check the logs**: Scripts provide detailed error messages
2. **Verify prerequisites**: MySQL installed, users created, permissions granted
3. **Test connectivity**: Can you connect manually to both databases?
4. **Review file permissions**: Scripts need execute permissions on Linux/Mac
5. **Check disk space**: Ensure sufficient space for backups and imports

## 🎯 Success Criteria

Migration is successful when:

- ✅ `verify_migration.py` reports all tests passed
- ✅ Web application starts without errors
- ✅ Dashboard displays correct data
- ✅ All features work as expected
- ✅ No data loss or corruption

## 📝 Version History

- **v1.0** - Initial release with complete migration toolkit
- Supports Windows development to Linux/Mac production
- Handles compressed and uncompressed backups
- Comprehensive verification and error handling

---

**Migration Toolkit for Warehouse Transfer System v2.0**
**Created: September 2025**

This toolkit ensures a smooth, reliable migration of your warehouse transfer data from development to production with zero data loss and minimal downtime.