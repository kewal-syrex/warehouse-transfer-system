#!/usr/bin/env python3
"""
Database connection test and schema setup for Warehouse Transfer Planning Tool
"""
import pymysql
import sys
from pathlib import Path

def test_mysql_connection():
    """Test MySQL connection and create database if needed"""
    try:
        # Connect to MySQL server (without specific database)
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',  # Default XAMPP has no root password
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print("Connected to MySQL server successfully!")
        
        with connection.cursor() as cursor:
            # Create database if it doesn't exist
            cursor.execute("CREATE DATABASE IF NOT EXISTS warehouse_transfer")
            print("Database 'warehouse_transfer' created/verified")
            
            # Switch to the database
            cursor.execute("USE warehouse_transfer")
            
            # Show existing tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            if tables:
                print(f"Found {len(tables)} existing tables:")
                for table in tables:
                    print(f"   - {list(table.values())[0]}")
            else:
                print("No tables found in database (empty database)")
            
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"MySQL connection error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def create_schema():
    """Execute the schema.sql file to create all tables"""
    try:
        # Read the schema file
        schema_path = Path(__file__).parent / 'schema.sql'
        if not schema_path.exists():
            print("❌ schema.sql file not found")
            return False
            
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Connect to MySQL and execute schema
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            database='warehouse_transfer',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print("🔧 Executing schema.sql...")
        
        # Split SQL statements and execute them one by one
        # Note: This is a simplified approach - in production, use proper SQL parsing
        statements = schema_sql.split(';')
        executed = 0
        
        with connection.cursor() as cursor:
            for statement in statements:
                statement = statement.strip()
                if statement and not statement.startswith('--') and statement.upper() != 'COMMIT':
                    try:
                        cursor.execute(statement)
                        executed += 1
                    except pymysql.Error as e:
                        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                            continue  # Ignore duplicate errors
                        else:
                            print(f"⚠️  SQL Error: {e}")
                            print(f"   Statement: {statement[:100]}...")
        
        connection.commit()
        connection.close()
        
        print(f"✅ Schema executed successfully! {executed} statements processed")
        return True
        
    except Exception as e:
        print(f"❌ Schema creation error: {e}")
        return False

def verify_schema():
    """Verify that all expected tables were created"""
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            database='warehouse_transfer',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Get list of tables
            cursor.execute("SHOW TABLES")
            tables = [list(table.values())[0] for table in cursor.fetchall()]
            
            expected_tables = [
                'skus', 'inventory_current', 'monthly_sales', 
                'stockout_dates', 'pending_inventory', 'transfer_history'
            ]
            
            print(f"📊 Database verification:")
            print(f"   Expected tables: {len(expected_tables)}")
            print(f"   Found tables: {len(tables)}")
            
            missing = set(expected_tables) - set(tables)
            extra = set(tables) - set(expected_tables) - {'v_current_stock_status', 'v_latest_sales', 'v_current_stockouts'}
            
            if missing:
                print(f"❌ Missing tables: {missing}")
            else:
                print("✅ All expected tables found")
                
            if extra:
                print(f"ℹ️  Extra tables: {extra}")
                
            # Test sample data
            cursor.execute("SELECT COUNT(*) as count FROM skus")
            sku_count = cursor.fetchone()['count']
            print(f"   Sample SKUs: {sku_count}")
            
            cursor.execute("SELECT COUNT(*) as count FROM monthly_sales")
            sales_count = cursor.fetchone()['count']
            print(f"   Sample sales records: {sales_count}")
            
        connection.close()
        return len(missing) == 0
        
    except Exception as e:
        print(f"❌ Schema verification error: {e}")
        return False

if __name__ == "__main__":
    print("Warehouse Transfer Planning Tool - Database Setup")
    print("=" * 60)
    
    # Test connection
    if not test_mysql_connection():
        print("\nDatabase connection failed. Please check:")
        print("   1. XAMPP is running")
        print("   2. MySQL service is started")
        print("   3. Default root password is empty")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Create schema
    if create_schema():
        print("\n" + "=" * 60)
        # Verify schema
        if verify_schema():
            print("\nDatabase setup completed successfully!")
            print("   You can now start the FastAPI application")
        else:
            print("\nSchema verification had issues")
    else:
        print("\nSchema creation failed")
        sys.exit(1)