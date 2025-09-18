#!/bin/bash
# ===================================================================
# Warehouse Transfer System - Database Import Script
# Version: 1.0
# Purpose: Import database backup to production server
# Usage: ./import_to_server.sh backup_file.sql [database_name] [username]
# ===================================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get file size in human readable format
get_file_size() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        stat -f%z "$1" 2>/dev/null | awk '{
            if ($1 > 1073741824) printf "%.1f GB", $1/1073741824
            else if ($1 > 1048576) printf "%.1f MB", $1/1048576
            else if ($1 > 1024) printf "%.1f KB", $1/1024
            else printf "%d bytes", $1
        }'
    else
        # Linux
        stat --printf="%s" "$1" 2>/dev/null | awk '{
            if ($1 > 1073741824) printf "%.1f GB", $1/1073741824
            else if ($1 > 1048576) printf "%.1f MB", $1/1048576
            else if ($1 > 1024) printf "%.1f KB", $1/1024
            else printf "%d bytes", $1
        }'
    fi
}

echo
echo "=================================================="
echo "Warehouse Transfer Database Import Tool"
echo "=================================================="
echo

# Check parameters
if [ $# -lt 1 ]; then
    print_error "Usage: $0 <backup_file> [database_name] [username]"
    echo
    echo "Examples:"
    echo "  $0 warehouse_db_20240914_143022.sql"
    echo "  $0 warehouse_db_20240914_143022.sql.gz"
    echo "  $0 warehouse_db_20240914_143022.zip warehouse_transfer warehouse_user"
    echo
    exit 1
fi

# Set parameters with defaults
BACKUP_FILE="$1"
DATABASE_NAME="${2:-warehouse_transfer}"
USERNAME="${3:-warehouse_user}"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    print_error "Backup file not found: $BACKUP_FILE"
    echo
    echo "Please ensure the backup file exists and try again."
    echo "Current directory: $(pwd)"
    echo "Available files:"
    ls -la *.sql *.gz *.zip 2>/dev/null || echo "No backup files found in current directory"
    exit 1
fi

# Display file information
FILE_SIZE=$(get_file_size "$BACKUP_FILE")
print_info "Backup file: $BACKUP_FILE"
print_info "File size: $FILE_SIZE"
print_info "Target database: $DATABASE_NAME"
print_info "MySQL user: $USERNAME"
echo

# Check if mysql command is available
if ! command_exists mysql; then
    print_error "MySQL client not found!"
    echo
    echo "Please install MySQL client:"
    echo "  Ubuntu/Debian: sudo apt-get install mysql-client"
    echo "  CentOS/RHEL: sudo yum install mysql"
    echo "  macOS: brew install mysql-client"
    exit 1
fi

# Check if we need decompression tools
TEMP_SQL_FILE=""
ORIGINAL_FILE="$BACKUP_FILE"
NEEDS_CLEANUP=false

# Handle compressed files
if [[ "$BACKUP_FILE" == *.gz ]]; then
    print_info "Detected gzip compressed file"
    if ! command_exists gunzip; then
        print_error "gunzip not found! Please install gzip utilities."
        exit 1
    fi

    TEMP_SQL_FILE="${BACKUP_FILE%.gz}"
    print_info "Decompressing to: $TEMP_SQL_FILE"

    if ! gunzip -c "$BACKUP_FILE" > "$TEMP_SQL_FILE"; then
        print_error "Failed to decompress file!"
        exit 1
    fi

    BACKUP_FILE="$TEMP_SQL_FILE"
    NEEDS_CLEANUP=true
    print_status "File decompressed successfully"

elif [[ "$BACKUP_FILE" == *.zip ]]; then
    print_info "Detected ZIP compressed file"
    if ! command_exists unzip; then
        print_error "unzip not found! Please install unzip utilities."
        exit 1
    fi

    # List contents of zip file
    print_info "ZIP file contents:"
    unzip -l "$BACKUP_FILE"
    echo

    # Extract the zip file
    if ! unzip -o "$BACKUP_FILE"; then
        print_error "Failed to extract ZIP file!"
        exit 1
    fi

    # Find the extracted SQL file
    TEMP_SQL_FILE=$(find . -name "*.sql" -newer "$BACKUP_FILE" | head -1)
    if [ -z "$TEMP_SQL_FILE" ]; then
        print_error "No SQL file found after extraction!"
        exit 1
    fi

    BACKUP_FILE="$TEMP_SQL_FILE"
    NEEDS_CLEANUP=true
    print_status "File extracted successfully: $BACKUP_FILE"
fi

# Verify the SQL file looks valid
if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
    print_error "SQL file is missing or empty: $BACKUP_FILE"
    exit 1
fi

# Check if file contains MySQL dump header
if ! head -10 "$BACKUP_FILE" | grep -q "MySQL dump"; then
    print_warning "File doesn't appear to be a MySQL dump"
    echo "First few lines of file:"
    head -5 "$BACKUP_FILE"
    echo
    echo -n "Continue anyway? (y/N): "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_info "Import cancelled by user"
        exit 0
    fi
fi

# Get SQL file size for progress indication
SQL_SIZE=$(get_file_size "$BACKUP_FILE")
print_info "SQL file size: $SQL_SIZE"

echo
echo "=============================================="
echo "IMPORT PREPARATION"
echo "=============================================="

# Test MySQL connection
print_info "Testing MySQL connection..."
if ! mysql -u "$USERNAME" -p -e "SELECT 1;" >/dev/null 2>&1; then
    print_error "Failed to connect to MySQL"
    echo
    echo "Please check:"
    echo "1. MySQL server is running"
    echo "2. Username '$USERNAME' exists"
    echo "3. Password is correct"
    echo "4. User has necessary privileges"
    echo
    echo "Test connection manually:"
    echo "  mysql -u $USERNAME -p"
    exit 1
fi
print_status "MySQL connection successful"

# Check if database exists, create if not
print_info "Checking database '$DATABASE_NAME'..."
if mysql -u "$USERNAME" -p -e "USE $DATABASE_NAME;" >/dev/null 2>&1; then
    print_warning "Database '$DATABASE_NAME' already exists"
    echo
    echo "This will REPLACE all existing data in the database!"
    echo -n "Are you sure you want to continue? (y/N): "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_info "Import cancelled by user"
        if [ "$NEEDS_CLEANUP" = true ] && [ -f "$TEMP_SQL_FILE" ]; then
            rm -f "$TEMP_SQL_FILE"
        fi
        exit 0
    fi
else
    print_info "Database '$DATABASE_NAME' does not exist, creating..."
    if ! mysql -u "$USERNAME" -p -e "CREATE DATABASE $DATABASE_NAME;" 2>/dev/null; then
        print_error "Failed to create database '$DATABASE_NAME'"
        echo
        echo "You may need to create it manually as root:"
        echo "  mysql -u root -p -e \"CREATE DATABASE $DATABASE_NAME;\""
        echo "  mysql -u root -p -e \"GRANT ALL PRIVILEGES ON $DATABASE_NAME.* TO '$USERNAME'@'localhost';\""
        exit 1
    fi
    print_status "Database '$DATABASE_NAME' created successfully"
fi

# Create backup before import (if database has data)
BACKUP_CREATED=false
TABLE_COUNT=$(mysql -u "$USERNAME" -p "$DATABASE_NAME" -e "SHOW TABLES;" 2>/dev/null | wc -l)
if [ "$TABLE_COUNT" -gt 1 ]; then  # More than just header line
    print_info "Creating pre-import backup..."
    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    PRE_BACKUP_FILE="pre_import_backup_${BACKUP_TIMESTAMP}.sql"

    if mysqldump -u "$USERNAME" -p "$DATABASE_NAME" > "$PRE_BACKUP_FILE" 2>/dev/null; then
        print_status "Pre-import backup created: $PRE_BACKUP_FILE"
        BACKUP_CREATED=true
    else
        print_warning "Could not create pre-import backup (continuing anyway)"
    fi
fi

echo
echo "=============================================="
echo "IMPORTING DATABASE"
echo "=============================================="

print_info "Starting import of $BACKUP_FILE to database '$DATABASE_NAME'..."
print_info "This may take several minutes for large databases..."
echo

# Import with progress indication
START_TIME=$(date +%s)

# Show progress for large files
if command_exists pv && [ -f "$BACKUP_FILE" ]; then
    print_info "Importing with progress indicator..."
    if pv "$BACKUP_FILE" | mysql -u "$USERNAME" -p "$DATABASE_NAME"; then
        IMPORT_SUCCESS=true
    else
        IMPORT_SUCCESS=false
    fi
else
    # Standard import without progress
    if mysql -u "$USERNAME" -p "$DATABASE_NAME" < "$BACKUP_FILE"; then
        IMPORT_SUCCESS=true
    else
        IMPORT_SUCCESS=false
    fi
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo
if [ "$IMPORT_SUCCESS" = true ]; then
    print_status "Database import completed successfully!"
    print_info "Import duration: ${DURATION} seconds"
else
    print_error "Database import failed!"

    if [ "$BACKUP_CREATED" = true ]; then
        echo
        print_info "Restoring from pre-import backup..."
        if mysql -u "$USERNAME" -p "$DATABASE_NAME" < "$PRE_BACKUP_FILE"; then
            print_status "Database restored from backup"
        else
            print_error "Failed to restore from backup!"
        fi
    fi

    # Cleanup temp files
    if [ "$NEEDS_CLEANUP" = true ] && [ -f "$TEMP_SQL_FILE" ]; then
        rm -f "$TEMP_SQL_FILE"
    fi
    exit 1
fi

echo
echo "=============================================="
echo "VERIFYING IMPORT"
echo "=============================================="

# Basic verification
print_info "Verifying database structure..."

# Check if main tables exist
EXPECTED_TABLES=("skus" "inventory_current" "monthly_sales" "pending_inventory")
MISSING_TABLES=()

for table in "${EXPECTED_TABLES[@]}"; do
    if mysql -u "$USERNAME" -p "$DATABASE_NAME" -e "DESCRIBE $table;" >/dev/null 2>&1; then
        print_status "Table '$table' exists"
    else
        print_warning "Table '$table' not found"
        MISSING_TABLES+=("$table")
    fi
done

# Count records in main tables
print_info "Counting records in main tables..."
mysql -u "$USERNAME" -p "$DATABASE_NAME" -e "
    SELECT 'skus' as table_name, COUNT(*) as record_count FROM skus
    UNION ALL
    SELECT 'inventory_current', COUNT(*) FROM inventory_current
    UNION ALL
    SELECT 'monthly_sales', COUNT(*) FROM monthly_sales
    UNION ALL
    SELECT 'pending_inventory', COUNT(*) FROM pending_inventory;" 2>/dev/null

# Check for views
print_info "Checking database views..."
VIEW_COUNT=$(mysql -u "$USERNAME" -p "$DATABASE_NAME" -e "SHOW FULL TABLES WHERE Table_type = 'VIEW';" 2>/dev/null | wc -l)
if [ "$VIEW_COUNT" -gt 1 ]; then
    print_status "Found $((VIEW_COUNT - 1)) database views"
else
    print_info "No database views found (this may be normal)"
fi

# Check for triggers
print_info "Checking database triggers..."
TRIGGER_COUNT=$(mysql -u "$USERNAME" -p "$DATABASE_NAME" -e "SHOW TRIGGERS;" 2>/dev/null | wc -l)
if [ "$TRIGGER_COUNT" -gt 1 ]; then
    print_status "Found $((TRIGGER_COUNT - 1)) database triggers"
else
    print_info "No database triggers found (this may be normal)"
fi

echo
echo "=============================================="
echo "IMPORT SUMMARY"
echo "=============================================="

print_status "Import completed successfully!"
echo
echo "Import Details:"
echo "  Source file: $ORIGINAL_FILE"
echo "  Target database: $DATABASE_NAME"
echo "  Import duration: ${DURATION} seconds"
echo "  MySQL user: $USERNAME"

if [ ${#MISSING_TABLES[@]} -eq 0 ]; then
    print_status "All expected tables found"
else
    print_warning "Missing tables: ${MISSING_TABLES[*]}"
    echo "This may be normal if you're importing a partial backup"
fi

if [ "$BACKUP_CREATED" = true ]; then
    echo
    print_info "Pre-import backup saved as: $PRE_BACKUP_FILE"
    print_info "You can remove this file after verifying the import"
fi

echo
echo "Next Steps:"
echo "1. Run comprehensive verification:"
echo "   python scripts/migration_toolkit/verify_migration.py"
echo "2. Start the application:"
echo "   uvicorn backend.main:app --host 0.0.0.0 --port 8000"
echo "3. Test the web interface:"
echo "   http://$(hostname -I | awk '{print $1}'):8000/static/index.html"
echo
echo "Troubleshooting:"
echo "• Check application logs if there are connection issues"
echo "• Verify .env file has correct database credentials"
echo "• Ensure MySQL service is running"

# Cleanup temporary files
if [ "$NEEDS_CLEANUP" = true ] && [ -f "$TEMP_SQL_FILE" ]; then
    rm -f "$TEMP_SQL_FILE"
    print_status "Temporary files cleaned up"
fi

echo
print_status "Database import process completed!"
echo