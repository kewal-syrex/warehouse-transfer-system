#!/usr/bin/env python3
"""
Test script to verify UUID import functionality
"""

import sys
import os

# Add the backend directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Test UUID import
try:
    import uuid
    print("SUCCESS: UUID import successful (global)")
    
    # Test uuid.uuid4() function
    test_uuid = str(uuid.uuid4())
    print(f"SUCCESS: UUID generation successful: {test_uuid}")
    
    # Test local import inside function
    def test_local_import():
        import uuid as local_uuid
        return str(local_uuid.uuid4())
    
    local_test = test_local_import()
    print(f"SUCCESS: Local UUID import successful: {local_test}")
    
    # Test the specific pattern used in the CSV import function
    def test_csv_import_pattern():
        import csv
        import io
        from datetime import datetime
        
        batch_id = str(uuid.uuid4())
        return batch_id
    
    batch_test = test_csv_import_pattern()
    print(f"SUCCESS: CSV import pattern successful: {batch_test}")
    
    print("\nAll UUID tests passed!")
    
except Exception as e:
    print(f"ERROR: UUID test failed: {e}")
    import traceback
    traceback.print_exc()