# Code Review Guidelines

## Code Reviewer Role

As a senior code reviewer and technical lead, your responsibilities include:

1. **Review code for quality, security, and performance**
2. **Ensure adherence to project standards and patterns** 
3. **Identify potential bugs and edge cases**
4. **Suggest specific improvements with examples**
5. **Validate test coverage and documentation**

## Review Categories

### Code Quality
- **Naming**: Variables, functions, and classes have clear, descriptive names
- **Structure**: Code is well-organized with proper separation of concerns
- **Maintainability**: Code is easy to read, modify, and extend
- **Consistency**: Follows established project patterns and conventions

### Security
- **Input Validation**: All user inputs are properly validated and sanitized
- **Authentication**: Access controls are properly implemented
- **Data Exposure**: Sensitive data is not logged or exposed inappropriately
- **SQL Injection**: Database queries use parameterized statements

### Performance
- **Complexity**: Algorithms have appropriate time/space complexity
- **Memory Usage**: No memory leaks or unnecessary object creation
- **Query Efficiency**: Database queries are optimized and indexed properly
- **Caching**: Appropriate use of caching mechanisms

### Architecture
- **Separation of Concerns**: Business logic, data access, and presentation are properly separated
- **Design Patterns**: Appropriate use of design patterns where beneficial
- **Dependencies**: Minimal coupling between modules
- **Error Handling**: Proper exception handling and logging

## Review Process

### 1. Pre-Review Checklist
- [ ] Code compiles without warnings
- [ ] All tests pass
- [ ] Documentation is updated
- [ ] No merge conflicts
- [ ] Follows git commit message conventions

### 2. Code Analysis
- **Read the requirements**: Understand what the code is supposed to do
- **Trace execution paths**: Follow the logic through various scenarios
- **Check edge cases**: Consider boundary conditions and error states
- **Verify business logic**: Ensure calculations and algorithms are correct

### 3. Feedback Guidelines
- **Be specific**: Point to exact lines and provide concrete examples
- **Be constructive**: Suggest improvements rather than just pointing out problems
- **Explain reasoning**: Help the developer understand why changes are needed
- **Prioritize**: Distinguish between critical issues and minor improvements

## Project-Specific Standards

### Backend (Python/FastAPI)
```python
#  Good: Clear function with proper typing and documentation
def calculate_transfer_quantity(
    demand: float, 
    current_inventory: int, 
    transfer_multiple: int = 50
) -> int:
    """
    Calculate recommended transfer quantity based on demand and inventory.
    
    Args:
        demand: Monthly demand with stockout correction applied
        current_inventory: Current Kentucky warehouse inventory
        transfer_multiple: Rounding multiple for transfers
        
    Returns:
        Recommended transfer quantity rounded to nearest multiple
        
    Raises:
        ValueError: If demand or inventory is negative
    """
    if demand < 0 or current_inventory < 0:
        raise ValueError("Demand and inventory must be non-negative")
    
    target_qty = max(0, demand * 6 - current_inventory)  # 6 months coverage
    return round_to_multiple(target_qty, transfer_multiple)

# L Bad: Unclear function without documentation
def calc(d, i, m=50):
    return ((d * 6 - i) // m + 1) * m if d * 6 > i else 0
```

### Frontend (HTML/JavaScript)
```javascript
//  Good: Clear function with error handling
async function loadTransferRecommendations() {
    try {
        showLoadingSpinner(true);
        
        const response = await fetch('/api/transfer-recommendations');
        if (!response.ok) {
            throw new Error(`Failed to load recommendations: ${response.status}`);
        }
        
        const recommendations = await response.json();
        updateTransferTable(recommendations);
        
    } catch (error) {
        console.error('Error loading recommendations:', error);
        showErrorMessage('Unable to load transfer recommendations. Please try again.');
    } finally {
        showLoadingSpinner(false);
    }
}

// L Bad: No error handling, unclear variable names
function load() {
    fetch('/api/transfer-recommendations')
        .then(r => r.json())
        .then(d => updateTable(d));
}
```

## Common Issues to Look For

### Security Vulnerabilities
- [ ] **SQL Injection**: Raw SQL strings with user input
- [ ] **XSS**: Unescaped user content in HTML
- [ ] **CSRF**: Missing CSRF tokens on state-changing operations
- [ ] **Data Exposure**: Logging sensitive information

### Performance Problems
- [ ] **N+1 Queries**: Database queries in loops
- [ ] **Memory Leaks**: Unclosed resources or circular references
- [ ] **Inefficient Algorithms**: O(n²) where O(n log n) is possible
- [ ] **Blocking Operations**: Synchronous operations that should be async

### Business Logic Errors
- [ ] **Calculation Errors**: Incorrect formulas or edge cases
- [ ] **Data Validation**: Missing input validation
- [ ] **State Management**: Race conditions or inconsistent state
- [ ] **Error Recovery**: Poor error handling that could lose data

## Review Checklist

### Pre-Merge Requirements
- [ ] **Functionality**: Code works as intended and meets requirements
- [ ] **Tests**: Adequate test coverage including edge cases
- [ ] **Documentation**: Code is properly documented
- [ ] **Performance**: No obvious performance regressions
- [ ] **Security**: No security vulnerabilities introduced
- [ ] **Standards**: Follows project coding standards
- [ ] **Integration**: Works well with existing codebase

### Documentation Standards
- [ ] **Module Docstrings**: Every Python file has clear module description
- [ ] **Function Docstrings**: All functions have Args/Returns/Raises
- [ ] **Complex Logic**: Business calculations are well-commented
- [ ] **API Documentation**: Endpoints are documented for OpenAPI
- [ ] **Frontend Components**: HTML sections and JS functions are documented

### Warehouse Transfer Specific Checks
- [ ] **Stockout Correction**: Algorithm uses 30% floor to prevent overcorrection
- [ ] **Transfer Multiples**: Quantities are rounded to appropriate multiples
- [ ] **ABC-XYZ Classification**: Classification logic is correct
- [ ] **Data Validation**: SKU data validation prevents invalid transfers
- [ ] **Error Handling**: Graceful handling of missing or invalid data

## Review Template

```markdown
## Summary
Brief description of what this PR accomplishes.

## Code Quality Review
###  Strengths
- Well-structured code with clear separation of concerns
- Good error handling throughout
- Comprehensive test coverage

### =' Issues Found
#### Critical
- [File:Line] Security vulnerability in user input handling
- [File:Line] Performance issue with database query in loop

#### Minor
- [File:Line] Consider using more descriptive variable name
- [File:Line] Missing docstring on public function

## Test Coverage
- [ ] Unit tests cover main functionality
- [ ] Integration tests verify API endpoints
- [ ] Edge cases are tested
- [ ] Performance tests with large datasets

## Security Review
- [ ] Input validation implemented
- [ ] Authentication/authorization checked
- [ ] No sensitive data exposure
- [ ] SQL injection prevention verified

## Performance Analysis
- [ ] No obvious performance regressions
- [ ] Database queries are optimized
- [ ] Memory usage is reasonable
- [ ] Caching strategy is appropriate

## Recommendations
1. **High Priority**: Fix the SQL injection vulnerability in calculations.py:42
2. **Medium Priority**: Add input validation to transfer quantity endpoint
3. **Low Priority**: Consider extracting common validation logic to utils module

## Approval Status
- [ ] Approved - Ready to merge
- [ ] Approved with minor changes - Can merge after addressing comments
- [ ] Needs work - Requires changes before approval
```

## Business Logic Validation

### Stockout Correction Algorithm
```python
# Verify this logic is correct:
def correct_monthly_demand(monthly_sales, stockout_days_in_month):
    availability_rate = (30 - stockout_days_in_month) / 30
    
    # Check: 30% floor prevents overcorrection
    if availability_rate < 1.0 and monthly_sales > 0:
        correction_factor = max(availability_rate, 0.3)  #  Correct
        corrected_demand = monthly_sales / correction_factor
        
        # Check: Cap at 50% increase for very low availability
        if availability_rate < 0.3:
            corrected_demand = min(corrected_demand, monthly_sales * 1.5)  #  Correct
```

### Transfer Calculation Validation
```python
# Verify transfer calculations follow business rules:
def calculate_transfer(sku_data):
    #  Check: Uses corrected demand
    monthly_demand = correct_monthly_demand(sku_data.sales, sku_data.stockout_days)
    
    #  Check: 6-month coverage target
    target_inventory = monthly_demand * 6
    
    #  Check: Considers current position
    current_position = sku_data.kentucky_qty + sku_data.pending_qty
    
    #  Check: Only transfer what's available in Burnaby
    transfer_need = max(0, target_inventory - current_position)
    available_qty = min(transfer_need, sku_data.burnaby_qty)
    
    #  Check: Rounds to appropriate multiple
    return round_to_multiple(available_qty, sku_data.transfer_multiple)
```

## Final Notes

### Remember to Validate:
1. **Business Rules**: All calculations follow documented business logic
2. **Data Flow**: Input validation ’ Processing ’ Output formatting
3. **Error Scenarios**: What happens when data is missing or invalid
4. **Performance**: How does it perform with 4000+ SKUs
5. **User Experience**: Is the interface intuitive and helpful

### Common Warehouse Transfer Gotchas:
- **Stockout Periods**: Don't use zero sales months in demand calculations
- **Transfer Minimums**: Enforce 10-unit minimum transfer rule
- **Multiple Rounding**: Different SKU types have different multiples
- **Availability Floors**: 30% minimum to prevent demand explosion
- **Lead Time**: 3-week total lead time affects coverage calculations

Be thorough but practical. The goal is to catch issues before they impact the business while maintaining development velocity.