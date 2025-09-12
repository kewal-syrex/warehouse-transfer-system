# Warehouse Transfer System - Server Deployment Guide

## 🚀 Complete Installation Instructions for Your Developer

### Prerequisites Required
- **Python 3.9+** with pip installed
- **MySQL 8.0+** (or MariaDB 10.5+)
- **Git** installed
- **Modern web browser** (Chrome, Firefox, Safari, Edge)

### Step 1: Clone the Repository
```bash
git clone https://github.com/arjayp-mv/warehouse-transfer-system.git
cd warehouse-transfer-system
```

### Step 2: Set Up Python Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

### Step 3: Install Python Dependencies
```bash
pip install -r requirements.txt
```

**Required packages will be installed:**
- FastAPI (web framework)
- Uvicorn (ASGI server)
- Pandas (data processing)
- NumPy (calculations)
- SQLAlchemy (database ORM)
- PyMySQL (MySQL connector)
- OpenPyXL (Excel processing)
- Requests (HTTP client)

### Step 4: Database Setup

#### 4.1 Create MySQL Database
```sql
-- Connect to MySQL as root or admin user
CREATE DATABASE warehouse_transfer;
CREATE USER 'warehouse_user'@'localhost' IDENTIFIED BY 'secure_password_here';
GRANT ALL PRIVILEGES ON warehouse_transfer.* TO 'warehouse_user'@'localhost';
FLUSH PRIVILEGES;
```

#### 4.2 Import Database Schema
```bash
# Import the database structure
mysql -u warehouse_user -p warehouse_transfer < database/schema.sql

# Import sample data (optional - for testing)
mysql -u warehouse_user -p warehouse_transfer < database/sample_data.sql
```

### Step 5: Configure Environment Variables
```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your actual database credentials
# Use your preferred text editor (nano, vim, notepad++, etc.)
nano .env
```

**Update these values in .env:**
```env
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=warehouse_transfer
DATABASE_USER=warehouse_user
DATABASE_PASSWORD=secure_password_here
```

### Step 6: Start the Application

#### For Development/Testing:
```bash
uvicorn backend.main:app --reload --port 8000
```

#### For Production:
```bash
# Install Gunicorn
pip install gunicorn

# Start with multiple workers
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Step 7: Access the Application

Open your browser and navigate to:
- **Dashboard**: http://your-server-ip:8000/static/index.html
- **Transfer Planning**: http://your-server-ip:8000/static/transfer-planning.html
- **Data Management**: http://your-server-ip:8000/static/data-management.html
- **API Documentation**: http://your-server-ip:8000/api/docs

### Step 8: Verify Installation

#### 8.1 Check System Health
Visit: `http://your-server-ip:8000/health`
Should return: `{"status": "healthy", "database": "connected"}`

#### 8.2 Run Performance Test
```bash
cd backend
python performance_test.py
```

Expected output:
```
=== Warehouse Transfer Performance Test ===
Dashboard API: ✓ 1.23s
Transfer Recommendations: ✓ 2.45s
Excel Export: ✓ 3.67s
Concurrent Users (5): ✓ 4.12s
Memory Usage: 245MB ✓
All tests passed!
```

## 🔧 Production Configuration

### Reverse Proxy Setup (Nginx)
Create `/etc/nginx/sites-available/warehouse-transfer`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /path/to/warehouse-transfer-system/frontend/;
        expires 1d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL Certificate (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Systemd Service (Linux)
Create `/etc/systemd/system/warehouse-transfer.service`:
```ini
[Unit]
Description=Warehouse Transfer System
After=network.target

[Service]
Type=exec
User=warehouse-app
Group=warehouse-app
WorkingDirectory=/opt/warehouse-transfer-system
Environment=PATH=/opt/warehouse-transfer-system/venv/bin
ExecStart=/opt/warehouse-transfer-system/venv/bin/gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable warehouse-transfer
sudo systemctl start warehouse-transfer
```

## 📊 Data Import Instructions

### Excel File Formats Supported:

#### 1. Inventory Data Format:
| sku_id | burnaby_qty | kentucky_qty | description | unit_price |
|--------|-------------|--------------|-------------|------------|
| CHG-001 | 500 | 0 | USB-C Charger | 25.00 |
| CAB-002 | 200 | 150 | Lightning Cable | 15.00 |

#### 2. Sales Data Format:
| sku_id | year_month | kentucky_sales | kentucky_stockout_days |
|--------|------------|---------------|----------------------|
| CHG-001 | 2024-03 | 100 | 5 |
| CAB-002 | 2024-03 | 45 | 0 |

### Import Process:
1. Go to **Data Management** page
2. Drag and drop Excel files or use file picker
3. System auto-detects sheet content type
4. Review validation results
5. Confirm import

## 🔍 Troubleshooting

### Common Issues:

#### "Database connection failed"
- Check MySQL service is running: `sudo systemctl status mysql`
- Verify credentials in `.env` file
- Test connection: `mysql -u warehouse_user -p warehouse_transfer`

#### "Port 8000 already in use"
- Kill existing process: `sudo lsof -t -i tcp:8000 | xargs kill`
- Or use different port: `uvicorn backend.main:app --port 8001`

#### "Permission denied" errors
- Ensure proper file permissions: `chmod -R 755 warehouse-transfer-system/`
- Check user ownership: `chown -R warehouse-app:warehouse-app /opt/warehouse-transfer-system/`

#### Performance issues
- Increase MySQL memory settings
- Add database indexes if processing 10,000+ SKUs
- Monitor with: `htop` and `mysql processlist`

### Logs and Monitoring:
```bash
# View application logs
journalctl -u warehouse-transfer -f

# View MySQL slow query log
sudo tail -f /var/log/mysql/mysql-slow.log

# Monitor system resources
htop
```

## 📞 Support Information

### System Specifications:
- **Version**: 1.0.0
- **Framework**: FastAPI + Python 3.9+
- **Database**: MySQL 8.0+
- **Frontend**: Bootstrap 5 + DataTables
- **Performance**: Tested with 4,000+ SKUs

### Feature Set:
- ✅ Stockout-corrected demand forecasting
- ✅ ABC-XYZ inventory classification
- ✅ Intelligent transfer recommendations
- ✅ Professional Excel reporting
- ✅ Real-time dashboard with alerts
- ✅ Drag-and-drop data import
- ✅ Multi-format export (Excel, CSV)

### Security Features:
- Input validation and sanitization
- SQL injection protection (SQLAlchemy ORM)
- File upload validation
- Error handling without data exposure

---

## 🚀 Quick Start Commands Summary

```bash
# 1. Clone and setup
git clone https://github.com/arjayp-mv/warehouse-transfer-system.git
cd warehouse-transfer-system
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. Install and configure
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database credentials

# 3. Database setup
mysql -u root -p < database/schema.sql
mysql -u root -p < database/sample_data.sql

# 4. Start application
uvicorn backend.main:app --reload --port 8000

# 5. Access at: http://localhost:8000/static/index.html
```

**The system is production-ready and fully tested. Contact support if you encounter any issues during deployment.**