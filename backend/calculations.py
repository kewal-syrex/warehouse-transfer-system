"""
Core business logic and calculations for transfer recommendations
Implements stockout correction and ABC-XYZ classification algorithms
"""
import math
from typing import List, Dict, Any, Optional, Tuple
try:
    from . import database
except ImportError:
    import database
import logging

logger = logging.getLogger(__name__)

class StockoutCorrector:
    """Handles stockout detection and demand correction calculations"""
    
    @staticmethod
    def correct_monthly_demand(monthly_sales: int, stockout_days: int, days_in_month: int = 30) -> float:
        """
        Calculate stockout-corrected demand using the simplified monthly approach
        
        Args:
            monthly_sales: Actual units sold in the month
            stockout_days: Number of days out of stock in the month
            days_in_month: Total days in the month (default 30)
        
        Returns:
            Corrected demand accounting for stockout periods
        """
        if stockout_days == 0 or monthly_sales == 0:
            return float(monthly_sales)
        
        # Calculate availability rate
        availability_rate = (days_in_month - stockout_days) / days_in_month
        
        if availability_rate < 1.0:
            # Apply correction with 30% floor to prevent overcorrection
            correction_factor = max(availability_rate, 0.3)
            corrected_demand = monthly_sales / correction_factor
            
            # Cap at 50% increase for very low availability (safeguard)
            if availability_rate < 0.3:
                corrected_demand = min(corrected_demand, monthly_sales * 1.5)
            
            return round(corrected_demand, 2)
        
        return float(monthly_sales)

class ABCXYZClassifier:
    """Handles ABC-XYZ classification for inventory management"""
    
    @staticmethod
    def classify_abc(annual_value: float, total_value: float) -> str:
        """
        Classify SKU based on annual value (Pareto 80/15/5 rule)
        
        Args:
            annual_value: Annual sales value for the SKU
            total_value: Total annual sales value across all SKUs
        
        Returns:
            ABC classification ('A', 'B', or 'C')
        """
        if total_value == 0:
            return 'C'
        
        percentage = (annual_value / total_value) * 100
        
        if percentage >= 80:  # Top 80% of value
            return 'A'
        elif percentage >= 15:  # Next 15% of value
            return 'B'
        else:  # Bottom 5% of value
            return 'C'
    
    @staticmethod
    def classify_xyz(sales_data: List[float]) -> str:
        """
        Classify SKU based on demand variability (coefficient of variation)
        
        Args:
            sales_data: List of monthly sales figures
        
        Returns:
            XYZ classification ('X', 'Y', or 'Z')
        """
        if len(sales_data) < 2:
            return 'Z'  # Insufficient data = irregular
        
        mean_sales = sum(sales_data) / len(sales_data)
        if mean_sales == 0:
            return 'Z'
        
        # Calculate standard deviation
        variance = sum((x - mean_sales) ** 2 for x in sales_data) / (len(sales_data) - 1)
        std_dev = math.sqrt(variance)
        
        # Coefficient of variation
        cv = std_dev / mean_sales
        
        if cv < 0.25:
            return 'X'  # Stable demand
        elif cv < 0.50:
            return 'Y'  # Variable demand
        else:
            return 'Z'  # Irregular demand

class TransferCalculator:
    """Main calculator for transfer recommendations"""
    
    def __init__(self):
        self.corrector = StockoutCorrector()
        self.classifier = ABCXYZClassifier()
    
    def get_coverage_target(self, abc_class: str, xyz_class: str) -> float:
        """
        Get coverage target in months based on ABC-XYZ classification
        
        Args:
            abc_class: ABC classification ('A', 'B', 'C')
            xyz_class: XYZ classification ('X', 'Y', 'Z')
        
        Returns:
            Target coverage in months
        """
        # Coverage matrix from PRD
        coverage_matrix = {
            'AX': 4, 'AY': 5, 'AZ': 6,
            'BX': 3, 'BY': 4, 'BZ': 5,
            'CX': 2, 'CY': 2, 'CZ': 1
        }
        
        key = f"{abc_class}{xyz_class}"
        return coverage_matrix.get(key, 6)  # Default 6 months if unknown
    
    def round_to_multiple(self, quantity: int, multiple: int) -> int:
        """
        Round transfer quantity to appropriate multiple
        
        Args:
            quantity: Calculated transfer quantity
            multiple: Transfer multiple (25, 50, 100)
        
        Returns:
            Rounded quantity respecting minimum transfer of 10 units
        """
        if quantity < 10:
            return 0  # Below minimum transfer threshold
        
        return math.ceil(quantity / multiple) * multiple
    
    def calculate_transfer_recommendation(self, sku_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate transfer recommendation for a single SKU
        
        Args:
            sku_data: Dictionary containing SKU information
        
        Returns:
            Dictionary with transfer recommendation
        """
        try:
            # Extract data
            sku_id = sku_data['sku_id']
            burnaby_qty = sku_data.get('burnaby_qty', 0)
            kentucky_qty = sku_data.get('kentucky_qty', 0)
            kentucky_sales = sku_data.get('kentucky_sales', 0)
            stockout_days = sku_data.get('kentucky_stockout_days', 0)
            abc_class = sku_data.get('abc_code', 'C')
            xyz_class = sku_data.get('xyz_code', 'Z')
            transfer_multiple = sku_data.get('transfer_multiple', 50)
            
            # Calculate corrected demand
            corrected_demand = self.corrector.correct_monthly_demand(
                kentucky_sales, stockout_days
            )
            
            # Update database with corrected demand
            database.update_corrected_demand(sku_id, '2024-03', corrected_demand)
            
            # Calculate target inventory
            coverage_months = self.get_coverage_target(abc_class, xyz_class)
            target_inventory = corrected_demand * coverage_months
            
            # Account for pending inventory (simplified - assume none for now)
            pending_qty = 0
            
            # Calculate transfer need
            current_position = kentucky_qty + pending_qty
            transfer_need = target_inventory - current_position
            
            # Check Burnaby availability
            available_to_transfer = min(transfer_need, burnaby_qty)
            
            # Round to multiple
            recommended_qty = self.round_to_multiple(available_to_transfer, transfer_multiple)
            
            # Calculate priority
            if kentucky_qty == 0:
                priority = "CRITICAL"
            elif kentucky_qty / max(corrected_demand, 1) < 1:  # Less than 1 month coverage
                priority = "HIGH"
            elif kentucky_qty / max(corrected_demand, 1) < 2:  # Less than 2 months coverage
                priority = "MEDIUM"
            else:
                priority = "LOW"
            
            # Create reason
            reason_parts = []
            if stockout_days > 0:
                reason_parts.append(f"Stockout correction applied ({stockout_days} days out)")
            if kentucky_qty == 0:
                reason_parts.append("Currently out of stock")
            elif kentucky_qty / max(corrected_demand, 1) < coverage_months:
                reason_parts.append(f"Below target coverage ({coverage_months:.1f} months)")
            
            reason = "; ".join(reason_parts) if reason_parts else "Maintain optimal stock level"
            
            return {
                'sku_id': sku_id,
                'description': sku_data.get('description', ''),
                'current_kentucky_qty': kentucky_qty,
                'current_burnaby_qty': burnaby_qty,
                'corrected_monthly_demand': corrected_demand,
                'recommended_transfer_qty': recommended_qty,
                'coverage_months': round(kentucky_qty / max(corrected_demand, 1), 1),
                'target_coverage_months': coverage_months,
                'priority': priority,
                'reason': reason,
                'abc_class': abc_class,
                'xyz_class': xyz_class,
                'transfer_multiple': transfer_multiple,
                'stockout_days': stockout_days
            }
            
        except Exception as e:
            logger.error(f"Calculation failed for SKU {sku_data.get('sku_id', 'unknown')}: {e}")
            return None

def calculate_all_transfer_recommendations() -> List[Dict[str, Any]]:
    """
    Calculate transfer recommendations for all active SKUs
    
    Returns:
        List of transfer recommendations sorted by priority
    """
    try:
        # Get all active SKUs with current inventory and latest sales
        query = """
        SELECT 
            s.sku_id,
            s.description,
            s.abc_code,
            s.xyz_code,
            s.transfer_multiple,
            ic.burnaby_qty,
            ic.kentucky_qty,
            COALESCE(ms.kentucky_sales, 0) as kentucky_sales,
            COALESCE(ms.kentucky_stockout_days, 0) as kentucky_stockout_days
        FROM skus s
        LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
        LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id AND ms.`year_month` = '2024-03'
        WHERE s.status = 'Active'
        ORDER BY s.sku_id
        """
        
        sku_data_list = database.execute_query(query)
        
        if not sku_data_list:
            return []
        
        calculator = TransferCalculator()
        recommendations = []
        
        for sku_data in sku_data_list:
            recommendation = calculator.calculate_transfer_recommendation(sku_data)
            if recommendation:
                recommendations.append(recommendation)
        
        # Sort by priority (CRITICAL -> HIGH -> MEDIUM -> LOW)
        priority_order = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
        recommendations.sort(key=lambda x: (
            priority_order.get(x['priority'], 5),
            -x['corrected_monthly_demand']  # Higher demand first within same priority
        ))
        
        logger.info(f"Generated {len(recommendations)} transfer recommendations")
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to calculate transfer recommendations: {e}")
        raise

def update_abc_xyz_classifications():
    """
    Update ABC-XYZ classifications for all SKUs based on recent sales data
    This would typically be run monthly after new sales data is imported
    """
    try:
        # Get sales data for classification
        sales_query = """
        SELECT 
            s.sku_id,
            s.cost_per_unit,
            ms.kentucky_sales,
            ms.`year_month`
        FROM skus s
        LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id
        WHERE s.status = 'Active'
            AND ms.`year_month` >= '2024-01'  # Last 3 months
        ORDER BY s.sku_id, ms.`year_month`
        """
        
        sales_data = database.execute_query(sales_query)
        
        # Group by SKU
        sku_sales = {}
        for row in sales_data:
            sku_id = row['sku_id']
            if sku_id not in sku_sales:
                sku_sales[sku_id] = {
                    'cost_per_unit': row['cost_per_unit'] or 0,
                    'sales': []
                }
            sku_sales[sku_id]['sales'].append(row['kentucky_sales'] or 0)
        
        classifier = ABCXYZClassifier()
        
        # Calculate total annual value for ABC classification
        total_annual_value = 0
        for sku_data in sku_sales.values():
            annual_sales = sum(sku_data['sales']) * 4  # Extrapolate from 3 months
            annual_value = annual_sales * sku_data['cost_per_unit']
            total_annual_value += annual_value
        
        # Update classifications
        for sku_id, sku_data in sku_sales.items():
            annual_sales = sum(sku_data['sales']) * 4
            annual_value = annual_sales * sku_data['cost_per_unit']
            
            abc_class = classifier.classify_abc(annual_value, total_annual_value)
            xyz_class = classifier.classify_xyz(sku_data['sales'])
            
            # Update database
            update_query = """
            UPDATE skus 
            SET abc_code = %s, xyz_code = %s, updated_at = NOW()
            WHERE sku_id = %s
            """
            
            db = database.get_database_connection()
            cursor = db.cursor()
            cursor.execute(update_query, (abc_class, xyz_class, sku_id))
            db.close()
        
        logger.info(f"Updated ABC-XYZ classifications for {len(sku_sales)} SKUs")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update ABC-XYZ classifications: {e}")
        return False