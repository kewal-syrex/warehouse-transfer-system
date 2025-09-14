"""
Configuration Management Module

Handles system settings for the warehouse transfer system including:
- Default lead times
- Supplier-specific overrides
- Coverage target configurations
- Business rule parameters
"""

import logging
import database
import pymysql
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class ConfigurationValue(BaseModel):
    """Configuration value with validation"""
    key: str = Field(..., description="Configuration key")
    value: str = Field(..., description="Configuration value as string")
    data_type: str = Field(default="string", description="Data type: string, int, float, bool, json")
    category: str = Field(default="general", description="Configuration category")
    description: Optional[str] = Field(None, description="Human-readable description")
    is_system: bool = Field(default=False, description="System setting (read-only)")

    @validator('data_type')
    def validate_data_type(cls, v):
        allowed_types = ['string', 'int', 'float', 'bool', 'json']
        if v not in allowed_types:
            raise ValueError(f'Data type must be one of: {allowed_types}')
        return v

class SupplierLeadTime(BaseModel):
    """Supplier-specific lead time override"""
    supplier: str = Field(..., description="Supplier name")
    lead_time_days: int = Field(..., ge=1, le=365, description="Lead time in days (1-365)")
    destination: Optional[str] = Field(None, description="Specific destination (burnaby/kentucky)")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('destination')
    def validate_destination(cls, v):
        if v is not None and v not in ['burnaby', 'kentucky']:
            raise ValueError('Destination must be burnaby or kentucky')
        return v

class ConfigurationManager:
    """Manages system configuration settings"""

    def __init__(self):
        self.default_settings = {
            # Lead time settings
            'default_lead_time_days': {'value': '120', 'type': 'int', 'category': 'lead_times',
                                     'description': 'Default lead time in days for pending orders'},
            'min_lead_time_days': {'value': '1', 'type': 'int', 'category': 'lead_times',
                                 'description': 'Minimum allowed lead time'},
            'max_lead_time_days': {'value': '365', 'type': 'int', 'category': 'lead_times',
                                 'description': 'Maximum allowed lead time'},

            # Burnaby retention settings
            'burnaby_min_coverage_months': {'value': '2.0', 'type': 'float', 'category': 'coverage',
                                          'description': 'Never transfer below this coverage threshold'},
            'burnaby_target_coverage_months': {'value': '6.0', 'type': 'float', 'category': 'coverage',
                                             'description': 'Target coverage retention for Burnaby'},
            'burnaby_coverage_with_pending': {'value': '1.5', 'type': 'float', 'category': 'coverage',
                                            'description': 'Coverage with imminent pending orders'},

            # Import/Export settings
            'auto_create_estimated_dates': {'value': 'true', 'type': 'bool', 'category': 'import_export',
                                          'description': 'Automatically create estimated dates for missing values'},
            'require_sku_validation': {'value': 'true', 'type': 'bool', 'category': 'import_export',
                                     'description': 'Validate SKUs exist before import'},

            # Business rules
            'min_transfer_quantity': {'value': '1', 'type': 'int', 'category': 'business_rules',
                                    'description': 'Minimum transfer quantity'},
            'enable_stockout_override': {'value': 'true', 'type': 'bool', 'category': 'business_rules',
                                       'description': 'Enable stockout quantity overrides'},
        }

    def get_setting(self, key: str, default_value: Any = None) -> Any:
        """
        Get configuration setting value with type conversion

        Args:
            key: Configuration key
            default_value: Default value if not found

        Returns:
            Configuration value with proper type conversion
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor(pymysql.cursors.DictCursor)

            cursor.execute("""
                SELECT config_value, data_type
                FROM system_config
                WHERE config_key = %s
            """, (key,))

            result = cursor.fetchone()

            if result:
                return self._convert_value(result['config_value'], result['data_type'])
            elif key in self.default_settings:
                default_setting = self.default_settings[key]
                return self._convert_value(default_setting['value'], default_setting['type'])
            else:
                return default_value

        except Exception as e:
            logger.warning(f"Error getting setting {key}: {str(e)}")
            if key in self.default_settings:
                default_setting = self.default_settings[key]
                return self._convert_value(default_setting['value'], default_setting['type'])
            return default_value
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

    def set_setting(self, key: str, value: Any, data_type: str = 'string',
                   category: str = 'general', description: str = None) -> bool:
        """
        Set configuration setting

        Args:
            key: Configuration key
            value: Configuration value
            data_type: Data type (string, int, float, bool, json)
            category: Configuration category
            description: Human-readable description

        Returns:
            True if successful
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor()

            # Validate value can be converted
            converted_value = str(value)
            self._convert_value(converted_value, data_type)  # Test conversion

            cursor.execute("""
                INSERT INTO system_config
                (config_key, config_value, data_type, category, description, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    config_value = VALUES(config_value),
                    data_type = VALUES(data_type),
                    category = VALUES(category),
                    description = VALUES(description),
                    updated_at = NOW()
            """, (key, converted_value, data_type, category, description))

            db.commit()
            logger.info(f"Configuration setting updated: {key} = {value}")
            return True

        except Exception as e:
            logger.error(f"Error setting configuration {key}: {str(e)}")
            if 'db' in locals():
                db.rollback()
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

    def get_all_settings(self, category: str = None) -> Dict[str, Any]:
        """
        Get all configuration settings

        Args:
            category: Optional category filter

        Returns:
            Dictionary of all settings
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor(pymysql.cursors.DictCursor)

            if category:
                cursor.execute("""
                    SELECT config_key, config_value, data_type, category, description
                    FROM system_config
                    WHERE category = %s
                    ORDER BY config_key
                """, (category,))
            else:
                cursor.execute("""
                    SELECT config_key, config_value, data_type, category, description
                    FROM system_config
                    ORDER BY category, config_key
                """)

            results = cursor.fetchall()
            settings = {}

            for row in results:
                settings[row['config_key']] = {
                    'value': self._convert_value(row['config_value'], row['data_type']),
                    'raw_value': row['config_value'],
                    'data_type': row['data_type'],
                    'category': row['category'],
                    'description': row['description']
                }

            # Add defaults for missing settings
            for key, default in self.default_settings.items():
                if key not in settings and (category is None or default['category'] == category):
                    settings[key] = {
                        'value': self._convert_value(default['value'], default['type']),
                        'raw_value': default['value'],
                        'data_type': default['type'],
                        'category': default['category'],
                        'description': default['description'],
                        'is_default': True
                    }

            return settings

        except Exception as e:
            logger.error(f"Error getting all settings: {str(e)}")
            return {}
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

    def _convert_value(self, value: str, data_type: str) -> Any:
        """Convert string value to proper type"""
        if data_type == 'int':
            return int(value)
        elif data_type == 'float':
            return float(value)
        elif data_type == 'bool':
            return value.lower() in ['true', '1', 'yes', 'on']
        elif data_type == 'json':
            import json
            return json.loads(value)
        else:
            return value

    def reset_to_defaults(self, category: str = None) -> bool:
        """
        Reset settings to defaults

        Args:
            category: Optional category to reset

        Returns:
            True if successful
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor()

            if category:
                cursor.execute("DELETE FROM system_config WHERE category = %s", (category,))
            else:
                cursor.execute("DELETE FROM system_config")

            db.commit()
            logger.info(f"Reset configuration settings" + (f" for category {category}" if category else ""))
            return True

        except Exception as e:
            logger.error(f"Error resetting settings: {str(e)}")
            if 'db' in locals():
                db.rollback()
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

    def get_supplier_lead_times(self) -> List[Dict]:
        """Get all supplier-specific lead time overrides"""
        try:
            db = database.get_database_connection()
            cursor = db.cursor(pymysql.cursors.DictCursor)

            cursor.execute("""
                SELECT supplier, lead_time_days, destination, notes, created_at, updated_at
                FROM supplier_lead_times
                ORDER BY supplier, destination
            """)

            return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error getting supplier lead times: {str(e)}")
            return []
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

    def set_supplier_lead_time(self, supplier: str, lead_time_days: int,
                              destination: str = None, notes: str = None) -> bool:
        """
        Set supplier-specific lead time override

        Args:
            supplier: Supplier name
            lead_time_days: Lead time in days
            destination: Optional specific destination
            notes: Optional notes

        Returns:
            True if successful
        """
        try:
            db = database.get_database_connection()
            cursor = db.cursor()

            cursor.execute("""
                INSERT INTO supplier_lead_times
                (supplier, lead_time_days, destination, notes, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    lead_time_days = VALUES(lead_time_days),
                    notes = VALUES(notes),
                    updated_at = NOW()
            """, (supplier, lead_time_days, destination, notes))

            db.commit()
            logger.info(f"Supplier lead time updated: {supplier} = {lead_time_days} days")
            return True

        except Exception as e:
            logger.error(f"Error setting supplier lead time: {str(e)}")
            if 'db' in locals():
                db.rollback()
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

    def delete_supplier_lead_time(self, supplier: str, destination: str = None) -> bool:
        """Delete supplier lead time override"""
        try:
            db = database.get_database_connection()
            cursor = db.cursor()

            if destination:
                cursor.execute("""
                    DELETE FROM supplier_lead_times
                    WHERE supplier = %s AND destination = %s
                """, (supplier, destination))
            else:
                cursor.execute("""
                    DELETE FROM supplier_lead_times
                    WHERE supplier = %s AND destination IS NULL
                """, (supplier,))

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Error deleting supplier lead time: {str(e)}")
            if 'db' in locals():
                db.rollback()
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

    def get_effective_lead_time(self, supplier: str = None, destination: str = None) -> int:
        """
        Get effective lead time considering supplier overrides

        Args:
            supplier: Supplier name
            destination: Destination warehouse

        Returns:
            Effective lead time in days
        """
        if supplier:
            try:
                db = database.get_database_connection()
                cursor = db.cursor()

                # Try specific supplier + destination first
                if destination:
                    cursor.execute("""
                        SELECT lead_time_days FROM supplier_lead_times
                        WHERE supplier = %s AND destination = %s
                    """, (supplier, destination))

                    result = cursor.fetchone()
                    if result:
                        return result[0]

                # Try supplier without destination
                cursor.execute("""
                    SELECT lead_time_days FROM supplier_lead_times
                    WHERE supplier = %s AND destination IS NULL
                """, (supplier,))

                result = cursor.fetchone()
                if result:
                    return result[0]

            except Exception as e:
                logger.warning(f"Error getting supplier lead time: {str(e)}")
            finally:
                if 'cursor' in locals():
                    cursor.close()
                if 'db' in locals():
                    db.close()

        # Fall back to default setting
        return self.get_setting('default_lead_time_days', 120)

# Global instance
configuration_manager = ConfigurationManager()