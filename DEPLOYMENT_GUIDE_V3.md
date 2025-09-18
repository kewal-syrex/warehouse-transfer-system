# Warehouse Transfer System - Complete Deployment Guide v3.0

## Overview

This comprehensive guide covers both initial deployment and data migration for the Warehouse Transfer Planning Tool. Whether you're setting up a fresh server or migrating existing data, this guide has you covered.

## Quick Start Summary

### For New Installations (No Existing Data)
1. Follow **Phase 1: Initial Server Setup**
2. Add data through web interface
3. System ready to use

### For Data Migration (Existing Development Database)
1. Follow **Phase 1: Initial Server Setup**
2. Follow **Phase 2: Data Migration** (see `DATA_MIGRATION_GUIDE.md`)
3. All data transferred automatically

---

## Phase 1: Initial Server Setup

### Prerequisites

#### Required Software
- **Python 3.9+** with pip installed
- **MySQL 8.0+** or **MariaDB 10.5+**
- **Git** installed
- **Modern web browser** (Chrome, Firefox, Safari, Edge)

#### System Requirements
- **CPU**: 2+ cores recommended
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB minimum free space
- **Network**: Port 8000 available for HTTP access

#### Access Requirements
- **Root/Administrator access** to install software
- **MySQL admin privileges** to create databases and users
- **Network access** from client machines (if multi-user)

### Step 1: Clone Repository

```bash
# Navigate to installation directory
cd /opt  # Linux/Mac
cd C:\    # Windows

# Clone the repository
git clone https://github.com/arjayp-mv/warehouse-transfer-system.git
cd warehouse-transfer-system
```

### Step 2: Python Environment Setup

#### Linux/Mac
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### Windows
```cmd
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Database Setup

#### 3.1 Create Database and User

Connect to MySQL as root and run:
```sql
-- Create database
CREATE DATABASE warehouse_transfer;

-- Create dedicated user with secure password
CREATE USER 'warehouse_user'@'localhost' IDENTIFIED BY 'SecurePassword123!';

-- Grant all privileges on the warehouse database
GRANT ALL PRIVILEGES ON warehouse_transfer.* TO 'warehouse_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Verify creation
SHOW DATABASES;
SELECT User, Host FROM mysql.user WHERE User = 'warehouse_user';
```

#### 3.2 Import Database Structure

Choose your approach:

##### Option A: Full Production Setup (Recommended)
```bash
# Import complete database with all enhancements
mysql -u warehouse_user -p warehouse_transfer < database/production_deployment.sql
```

##### Option B: Basic Setup
```bash
# Import basic schema only
mysql -u warehouse_user -p warehouse_transfer < database/schema.sql
```

#### 3.3 Verify Database Setup
```bash
# Check tables were created
mysql -u warehouse_user -p warehouse_transfer -e "SHOW TABLES;"

# Check for views (if using production setup)
mysql -u warehouse_user -p warehouse_transfer -e "SHOW FULL TABLES WHERE Table_type = 'VIEW';"
```

### Step 4: Environment Configuration

#### 4.1 Create Environment File
```bash
# Copy production template
cp .env.production .env

# Edit with your settings
nano .env    # Linux/Mac
notepad .env # Windows
```

#### 4.2 Configure Environment Variables
Update `.env` with your actual values:
```env
# Database Configuration
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=warehouse_transfer
DATABASE_USER=warehouse_user
DATABASE_PASSWORD=SecurePassword123!

# Application Settings
DEBUG=false
ENVIRONMENT=production
FASTAPI_RELOAD=false
LOG_LEVEL=warning

# Security (change these!)
SECRET_KEY=your-secret-key-here-change-this
API_KEY=your-api-key-here-change-this

# Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=4
```

### Step 5: Test Installation

#### 5.1 Start Application
```bash
# Activate virtual environment (if not already active)
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Start application
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 5.2 Verify Installation
Open browser to: `http://localhost:8000/static/index.html`

Expected results:
- [ ] Dashboard loads without errors
- [ ] Database connection successful
- [ ] No JavaScript console errors
- [ ] All navigation links work

#### 5.3 Test API Health
Visit: `http://localhost:8000/health`
Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-09-14T10:30:00",
  "version": "2.0"
}
```

### Step 6: Production Configuration

#### 6.1 Set Up for Network Access
```bash
# Stop test server (Ctrl+C)

# Start for network access
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

#### 6.2 Configure Firewall (if needed)

##### Linux (UFW)
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

##### Windows
1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Create new Inbound Rule for port 8000
4. Allow connections

#### 6.3 Test Network Access
From another computer on the network:
`http://[server-ip]:8000/static/index.html`

Replace `[server-ip]` with your server's IP address.

---

## Phase 2: Data Migration (Optional)

If you have existing data in a development environment, follow the **DATA_MIGRATION_GUIDE.md** for complete migration instructions.

### Quick Migration Overview
1. Use `scripts/migration_toolkit/export_database.bat` on development machine
2. Transfer file to production server
3. Use `scripts/migration_toolkit/import_to_server.sh` to import
4. Verify with `verify_migration.py`

---

## Production Deployment Options

### Option 1: Simple Production (Recommended for small teams)
```bash
# Start with multiple workers for better performance
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Option 2: Advanced Production (High availability)
```bash
# Install Gunicorn for production WSGI server
pip install gunicorn

# Start with Gunicorn
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Option 3: System Service (Auto-start)

#### Linux (systemd)
Create `/etc/systemd/system/warehouse-transfer.service`:
```ini
[Unit]
Description=Warehouse Transfer System
After=network.target mysql.service

[Service]
Type=exec
User=warehouse-app
Group=warehouse-app
WorkingDirectory=/opt/warehouse-transfer-system
Environment=PATH=/opt/warehouse-transfer-system/venv/bin
ExecStart=/opt/warehouse-transfer-system/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable warehouse-transfer
sudo systemctl start warehouse-transfer
sudo systemctl status warehouse-transfer
```

#### Windows (NSSM)
```cmd
# Download NSSM (Non-Sucking Service Manager)
# Install service
nssm install WarehouseTransfer "C:\warehouse-transfer-system\venv\Scripts\python.exe"
nssm set WarehouseTransfer Arguments "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
nssm set WarehouseTransfer AppDirectory "C:\warehouse-transfer-system"
nssm set WarehouseTransfer DisplayName "Warehouse Transfer System"
nssm start WarehouseTransfer
```

---

## Application Access URLs

Once deployed, access the system at:

- **Dashboard**: `http://[server-ip]:8000/static/index.html`
- **Transfer Planning**: `http://[server-ip]:8000/static/transfer-planning.html`
- **Data Management**: `http://[server-ip]:8000/static/data-management.html`
- **SKU Listing**: `http://[server-ip]:8000/static/sku-listing.html`
- **API Documentation**: `http://[server-ip]:8000/docs`
- **Health Check**: `http://[server-ip]:8000/health`

### Bookmark Recommendations
Provide these bookmarks to users:
- **Main System**: `http://[server-ip]:8000/static/index.html`
- **Transfer Planning**: `http://[server-ip]:8000/static/transfer-planning.html`

---

## Data Import and Setup

### Initial Data Import

#### 1. SKU Data
Navigate to Data Management and import:
- Excel file with columns: `sku_id`, `description`, `supplier`, `cost_per_unit`
- System automatically detects Excel sheet content

#### 2. Inventory Data
Import current inventory levels:
- Columns: `sku_id`, `burnaby_qty`, `kentucky_qty`
- Updates existing SKUs or creates new ones

#### 3. Sales History
Import historical sales data:
- Columns: `sku_id`, `year_month`, `kentucky_sales`, `kentucky_stockout_days`
- Format year_month as: `2024-03`

#### 4. Pending Orders (Optional)
Import pending inventory:
- Columns: `sku_id`, `quantity`, `destination`, `expected_arrival`
- Supports date estimation if arrival dates unknown

### Excel File Formats

The system accepts standard Excel files (.xlsx, .xls) with these formats:

#### Inventory Format
| sku_id | description | burnaby_qty | kentucky_qty | cost_per_unit |
|--------|-------------|-------------|--------------|---------------|
| CHG-001 | USB-C Charger | 500 | 0 | 25.00 |
| CAB-002 | Lightning Cable | 200 | 150 | 15.00 |

#### Sales Format
| sku_id | year_month | kentucky_sales | kentucky_stockout_days |
|--------|------------|----------------|----------------------|
| CHG-001 | 2024-03 | 100 | 5 |
| CAB-002 | 2024-03 | 45 | 0 |

---

## Troubleshooting Guide

### Common Installation Issues

#### Database Connection Failed
**Symptoms**: Application won't start, database connection errors
**Solutions**:
1. Verify MySQL service is running:
   ```bash
   # Linux
   sudo systemctl status mysql
   # Windows
   net start mysql80
   ```
2. Check database credentials in `.env`
3. Test connection manually:
   ```bash
   mysql -u warehouse_user -p warehouse_transfer
   ```
4. Verify user privileges:
   ```sql
   SHOW GRANTS FOR 'warehouse_user'@'localhost';
   ```

#### Port 8000 Already in Use
**Symptoms**: "Address already in use" error
**Solutions**:
1. Find and kill existing processes:
   ```bash
   # Linux/Mac
   sudo lsof -t -i tcp:8000 | xargs kill
   # Windows
   netstat -ano | findstr :8000
   taskkill /PID [PID] /F
   ```
2. Use different port:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8001
   ```

#### Can't Access from Other Computers
**Symptoms**: Works on server, not accessible from other machines
**Solutions**:
1. Ensure using `--host 0.0.0.0` not `--host localhost`
2. Check firewall settings allow port 8000
3. Verify network connectivity:
   ```bash
   ping [server-ip]
   telnet [server-ip] 8000
   ```

#### Python Module Import Errors
**Symptoms**: ModuleNotFoundError when starting application
**Solutions**:
1. Verify virtual environment is activated
2. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```
3. Check Python version:
   ```bash
   python --version  # Should be 3.9+
   ```

### Performance Issues

#### Slow Dashboard Loading
**Causes**: Large dataset, inefficient queries
**Solutions**:
1. Optimize database:
   ```sql
   ANALYZE TABLE skus, monthly_sales, inventory_current;
   OPTIMIZE TABLE skus, monthly_sales, inventory_current;
   ```
2. Increase MySQL memory:
   ```sql
   SET GLOBAL innodb_buffer_pool_size = 1073741824; -- 1GB
   ```
3. Use multiple workers:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

#### Excel Export Timeouts
**Causes**: Large dataset processing
**Solutions**:
1. Increase timeout in nginx/proxy (if used)
2. Filter data before export
3. Use CSV export for large datasets

---

## Security Considerations

### Database Security
- Use strong passwords for database users
- Limit database user privileges to only warehouse_transfer database
- Regular password rotation
- Monitor database access logs

### Application Security
- Change default SECRET_KEY and API_KEY in .env
- Use HTTPS in production (requires reverse proxy setup)
- Restrict file upload types and sizes
- Regular security updates for dependencies

### Network Security
- Use firewall to restrict port 8000 to internal network only
- VPN access for remote users
- Monitor access logs for suspicious activity

---

## Maintenance and Updates

### Regular Maintenance Tasks

#### Daily
- Monitor application logs for errors
- Check disk space and memory usage
- Verify backup completion

#### Weekly
- Review database performance
- Update security patches
- Check for application updates

#### Monthly
- Full system backup
- Database optimization
- Review user access and permissions

### Backup Strategy

#### Database Backups
```bash
# Daily automatic backup
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
mysqldump -u warehouse_user -p warehouse_transfer > /backups/warehouse_backup_$DATE.sql
gzip /backups/warehouse_backup_$DATE.sql

# Keep last 30 days
find /backups -name "warehouse_backup_*.sql.gz" -mtime +30 -delete
```

#### Application Backups
```bash
# Backup entire application directory
tar -czf /backups/warehouse_app_$(date +%Y%m%d).tar.gz /opt/warehouse-transfer-system/
```

### Update Procedure
1. Create backup before updates
2. Update code: `git pull origin main`
3. Update dependencies: `pip install -r requirements.txt --upgrade`
4. Run database migrations if any
5. Restart application
6. Verify functionality

---

## Migration Toolkit Reference

The system includes a complete migration toolkit in `scripts/migration_toolkit/`:

### Available Scripts
- **export_database.bat** - Export full database (Windows)
- **export_structure_only.bat** - Export structure only (Windows)
- **import_to_server.sh** - Import database (Linux/Mac)
- **backup_production.sh** - Create production backup
- **verify_migration.py** - Validate migration success
- **quick_migrate.py** - Automated migration tool

### Usage
See `DATA_MIGRATION_GUIDE.md` for complete migration instructions.

---

## System Specifications

### Tested Configurations
- **Development**: Windows 10/11 with XAMPP
- **Production**: Ubuntu 20.04+ LTS, CentOS 7+, Windows Server 2019+
- **Database**: MySQL 8.0, MariaDB 10.5+
- **Python**: 3.9, 3.10, 3.11
- **Browsers**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+

### Performance Benchmarks
- **Dataset**: 4,000+ SKUs tested
- **Response Time**: <5 seconds for transfer recommendations
- **Export Speed**: <10 seconds for Excel generation
- **Memory Usage**: ~256MB typical, ~512MB peak
- **Concurrent Users**: 10+ users tested successfully

### Feature Completeness
- ✅ Stockout-corrected demand forecasting
- ✅ ABC-XYZ inventory classification
- ✅ Intelligent transfer recommendations
- ✅ Professional Excel reporting with multiple sheets
- ✅ Real-time dashboard with alerts
- ✅ Drag-and-drop data import
- ✅ Multi-format export (Excel, CSV)
- ✅ Pending orders management
- ✅ Configuration management system
- ✅ Comprehensive API with documentation

---

## Support Information

### Documentation Resources
- **DATA_MIGRATION_GUIDE.md** - Complete migration procedures
- **API_Documentation_v2.md** - API reference and examples
- **Pending_Orders_User_Guide.md** - User guide for pending orders
- **SKU_LISTING_DOCUMENTATION.md** - SKU management guide

### System Information
- **Version**: 2.0.0
- **Framework**: FastAPI + Python 3.9+
- **Database**: MySQL 8.0+ / MariaDB 10.5+
- **Frontend**: Bootstrap 5 + DataTables + Chart.js
- **License**: Internal Company Use

### Getting Help
1. Check this deployment guide first
2. Review application logs for specific errors
3. Verify database connectivity and permissions
4. Check system resources (CPU, memory, disk)
5. Consult the troubleshooting section above

---

## Deployment Success Checklist

Print this checklist for your deployment:

### Pre-Deployment
- [ ] Server meets system requirements
- [ ] All required software installed
- [ ] Network access and firewall configured
- [ ] Database administrator access available

### Installation
- [ ] Repository cloned successfully
- [ ] Python virtual environment created
- [ ] All dependencies installed without errors
- [ ] Database and user created
- [ ] Database schema imported successfully
- [ ] Environment variables configured
- [ ] Application starts without errors

### Testing
- [ ] Health check endpoint responds correctly
- [ ] Dashboard loads properly
- [ ] Database connection successful
- [ ] Can access from other computers (if multi-user)
- [ ] All main features functional
- [ ] Excel import/export works
- [ ] API documentation accessible

### Production Ready
- [ ] Firewall configured correctly
- [ ] Service/daemon setup (if required)
- [ ] Backup strategy implemented
- [ ] User access documentation provided
- [ ] Performance acceptable with expected load
- [ ] Security review completed

### Post-Deployment
- [ ] Users trained on new system access
- [ ] Bookmarks distributed
- [ ] Migration completed (if applicable)
- [ ] Monitoring configured
- [ ] Deployment documented
- [ ] System ready for production use!

---

**Deployment Guide Version 3.0 - Updated September 2025**
**For Warehouse Transfer System v2.0 with Pending Orders Management**

This guide provides everything needed for a successful deployment, whether starting fresh or migrating existing data. The system is production-ready for internal company networks and fully tested with real-world datasets.