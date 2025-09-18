#!/bin/bash
# ===================================================================
# Warehouse Transfer System - Production Backup Script
# Version: 1.0
# Purpose: Create backup of production database before migration
# Usage: ./backup_production.sh [database_name] [username]
# ===================================================================

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() {
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

echo
echo "=================================================="
echo "Warehouse Transfer Production Backup Tool"
echo "=================================================="
echo

# Set parameters with defaults
DATABASE_NAME="${1:-warehouse_transfer}"
USERNAME="${2:-warehouse_user}"

# Generate timestamp for backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="production_backup_${TIMESTAMP}.sql"
COMPRESSED_FILE="production_backup_${TIMESTAMP}.sql.gz"

print_info "Database: $DATABASE_NAME"
print_info "User: $USERNAME"
print_info "Backup file: $BACKUP_FILE"
echo

# Check if mysqldump is available
if ! command -v mysqldump >/dev/null 2>&1; then
    print_error "mysqldump not found!"
    echo
    echo "Please install MySQL client:"
    echo "  Ubuntu/Debian: sudo apt-get install mysql-client"
    echo "  CentOS/RHEL: sudo yum install mysql"
    echo "  macOS: brew install mysql-client"
    exit 1
fi

# Test MySQL connection
print_info "Testing database connection..."
if ! mysql -u "$USERNAME" -p -e "USE $DATABASE_NAME; SELECT 1;" >/dev/null 2>&1; then
    print_error "Failed to connect to database '$DATABASE_NAME'"
    echo
    echo "Please check:"
    echo "1. MySQL server is running"
    echo "2. Database '$DATABASE_NAME' exists"
    echo "3. User '$USERNAME' has access"
    echo "4. Password is correct"
    exit 1
fi
print_success "Database connection successful"

# Check if database has data
print_info "Checking database contents..."
TABLE_COUNT=$(mysql -u "$USERNAME" -p "$DATABASE_NAME" -e "SHOW TABLES;" 2>/dev/null | wc -l)
if [ "$TABLE_COUNT" -le 1 ]; then
    print_warning "Database appears to be empty (no tables found)"
    echo -n "Continue with backup anyway? (y/N): "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_info "Backup cancelled by user"
        exit 0
    fi
else
    print_success "Found $((TABLE_COUNT - 1)) tables in database"
fi

# Create backup
print_info "Creating backup..."
print_info "This may take a few minutes for large databases..."

START_TIME=$(date +%s)

# Create backup with all necessary options
if mysqldump -u "$USERNAME" -p \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --add-drop-table \
    --add-locks \
    --extended-insert \
    --quick \
    --lock-tables=false \
    "$DATABASE_NAME" > "$BACKUP_FILE" 2>/dev/null; then

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    print_success "Backup created successfully in ${DURATION} seconds"
else
    print_error "Backup failed!"
    exit 1
fi

# Check backup file size
if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
    print_error "Backup file is missing or empty"
    exit 1
fi

# Get file size
FILE_SIZE=$(stat --printf="%s" "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)
if [ "$FILE_SIZE" -gt 1048576 ]; then
    SIZE_MB=$((FILE_SIZE / 1048576))
    print_info "Backup size: ${SIZE_MB} MB"
else
    SIZE_KB=$((FILE_SIZE / 1024))
    print_info "Backup size: ${SIZE_KB} KB"
fi

# Compress backup
print_info "Compressing backup..."
if command -v gzip >/dev/null 2>&1; then
    if gzip "$BACKUP_FILE"; then
        print_success "Backup compressed: $COMPRESSED_FILE"

        # Show compressed size
        COMPRESSED_SIZE=$(stat --printf="%s" "$COMPRESSED_FILE" 2>/dev/null || stat -f%z "$COMPRESSED_FILE" 2>/dev/null)
        if [ "$COMPRESSED_SIZE" -gt 1048576 ]; then
            COMP_SIZE_MB=$((COMPRESSED_SIZE / 1048576))
            print_info "Compressed size: ${COMP_SIZE_MB} MB"
        else
            COMP_SIZE_KB=$((COMPRESSED_SIZE / 1024))
            print_info "Compressed size: ${COMP_SIZE_KB} KB"
        fi

        FINAL_FILE="$COMPRESSED_FILE"
    else
        print_warning "Compression failed, keeping uncompressed file"
        FINAL_FILE="$BACKUP_FILE"
    fi
else
    print_warning "gzip not available, keeping uncompressed file"
    FINAL_FILE="$BACKUP_FILE"
fi

echo
echo "=================================================="
echo "BACKUP COMPLETED SUCCESSFULLY"
echo "=================================================="
echo
echo "Backup Details:"
echo "  Database: $DATABASE_NAME"
echo "  Timestamp: $(date)"
echo "  Backup File: $FINAL_FILE"
echo "  Location: $(pwd)/$FINAL_FILE"

# Verify backup integrity
print_info "Verifying backup integrity..."
if [[ "$FINAL_FILE" == *.gz ]]; then
    if zcat "$FINAL_FILE" | head -10 | grep -q "MySQL dump"; then
        print_success "Backup integrity verified"
    else
        print_warning "Backup integrity check failed"
    fi
else
    if head -10 "$FINAL_FILE" | grep -q "MySQL dump"; then
        print_success "Backup integrity verified"
    else
        print_warning "Backup integrity check failed"
    fi
fi

echo
echo "Next Steps:"
echo "1. Keep this backup file safe until migration is complete"
echo "2. This backup can be used to restore if migration fails"
echo "3. Restore command: mysql -u $USERNAME -p $DATABASE_NAME < $FINAL_FILE"
echo

if [ "$FILE_SIZE" -lt 10240 ]; then
    print_warning "Small backup size detected (less than 10KB)"
    print_warning "This might indicate an empty database or backup issue"
fi

print_success "Production backup completed successfully!"
echo