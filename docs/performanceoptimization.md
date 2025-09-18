# Warehouse Transfer Planning Performance Optimization StrategyBased on your performance analysis showing **70% database bottlenecks, 20% calculation overhead, and 10% frontend rendering**, here's a comprehensive optimization roadmap targeting your **25-40 second load times** to achieve the **sub-5 second goal**.

## Performance Optimization Roadmap## Immediate Optimizations (1-2 Days Effort)### 1. Database Index Optimization - **Expected 30-40% Improvement****Priority:** Critical - Address the 70% database bottleneck first

Add these composite indexes to eliminate the correlated subquery performance issues:[1][2]

```sql
-- Critical indexes for main query performance
CREATE INDEX idx_monthly_sales_latest_data 
ON monthly_sales (sku_id, year_month DESC, kentucky_sales, burnaby_sales);

CREATE INDEX idx_monthly_sales_sku_month 
ON monthly_sales (sku_id, year_month DESC);

-- Supporting indexes for JOINs
CREATE INDEX idx_inventory_current_sku ON inventory_current (sku_id);
CREATE INDEX idx_transfer_confirmations_sku ON transfer_confirmations (sku_id);
```

**Implementation Code:**
```python
# Execute during low-traffic period
def add_performance_indexes():
    indexes = [
        "CREATE INDEX idx_monthly_sales_latest_data ON monthly_sales (sku_id, year_month DESC, kentucky_sales, burnaby_sales)",
        "CREATE INDEX idx_monthly_sales_sku_month ON monthly_sales (sku_id, year_month DESC)",
        "CREATE INDEX idx_inventory_current_sku ON inventory_current (sku_id)",
        "CREATE INDEX idx_transfer_confirmations_sku ON transfer_confirmations (sku_id)"
    ]
    
    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
            print(f"✓ Created: {index_sql}")
        except Exception as e:
            print(f"✗ Failed: {e}")
```

### 2. Progressive Loading Implementation - **Expected 80% Perceived Improvement**Replace the monolithic 4000+ SKU response with progressive loading:[3][4]

```python
@app.get("/api/transfer-recommendations")
async def get_transfer_recommendations_progressive(
    page: int = 1,
    page_size: int = 100,
    priority_only: bool = True
):
    if priority_only and page == 1:
        # Load high-priority SKUs first (ABC-A items, high velocity)
        query = """
        SELECT * FROM your_main_query 
        WHERE s.abc_code = 'A' OR (s.xyz_code = 'X' AND ic.kentucky_qty < 10)
        ORDER BY s.abc_code, COALESCE(ms.kentucky_sales, 0) DESC
        LIMIT 100
        """
    else:
        # Standard pagination for remaining items
        offset = (page - 1) * page_size
        query = f"""
        SELECT * FROM your_main_query 
        ORDER BY s.sku_id
        LIMIT {page_size} OFFSET {offset}
        """
    
    results = execute_query_with_caching(query)
    return {"items": results, "page": page, "has_more": len(results) == page_size}
```

**Frontend Implementation:**
```javascript
async function loadRecommendationsProgressive() {
    showLoadingSpinner();
    
    // Load first 100 critical items immediately
    const firstBatch = await fetch('/api/transfer-recommendations?priority_only=true');
    const data = await firstBatch.json();
    
    updateTableWithData(data.items);
    hideLoadingSpinner();
    showProgressIndicator("Loading remaining items...");
    
    // Load remaining items in background
    let page = 2;
    while (data.has_more) {
        const nextBatch = await fetch(`/api/transfer-recommendations?page=${page}`);
        const nextData = await nextBatch.json();
        
        appendTableData(nextData.items);
        updateProgress(page * 100, totalItems);
        page++;
        
        // Prevent UI blocking
        await new Promise(resolve => setTimeout(resolve, 50));
    }
    
    hideProgressIndicator();
}
```

### 3. Query Optimization - Replace Correlated Subquery - **Expected 15-25% Improvement**Transform the expensive correlated subquery using window functions:[1][2]

```sql
-- BEFORE: Correlated subquery (executes for each SKU)
SELECT s.sku_id, s.description, ...
FROM skus s
LEFT JOIN monthly_sales ms ON s.sku_id = ms.sku_id
    AND ms.year_month = (
        SELECT MAX(year_month) FROM monthly_sales ms2
        WHERE ms2.sku_id = s.sku_id  -- EXPENSIVE!
        AND (ms2.kentucky_sales > 0 OR ms2.burnaby_sales > 0)
    )

-- AFTER: Window function approach
WITH latest_sales AS (
    SELECT sku_id, year_month, kentucky_sales, burnaby_sales,
           ROW_NUMBER() OVER (
               PARTITION BY sku_id 
               ORDER BY year_month DESC
           ) as rn
    FROM monthly_sales 
    WHERE kentucky_sales > 0 OR burnaby_sales > 0
)
SELECT s.sku_id, s.description, s.supplier, s.abc_code, s.xyz_code,
       ic.burnaby_qty, ic.kentucky_qty,
       COALESCE(ls.kentucky_sales, 0) as kentucky_sales,
       COALESCE(ls.burnaby_sales, 0) as burnaby_sales
FROM skus s
LEFT JOIN inventory_current ic ON s.sku_id = ic.sku_id
LEFT JOIN latest_sales ls ON s.sku_id = ls.sku_id AND ls.rn = 1
LEFT JOIN transfer_confirmations tc ON s.sku_id = tc.sku_id
ORDER BY s.sku_id
```

### 4. User Experience Enhancements - **Expected 90% UX Improvement**```javascript
// Add detailed progress tracking
function showDetailedProgress() {
    const progressHTML = `
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-text">
                <span id="progressText">Loading transfer recommendations...</span>
                <span id="progressCount">0 / 4000 SKUs processed</span>
            </div>
            <div class="progress-stages">
                <div class="stage active" id="stage1">📊 Fetching data</div>
                <div class="stage" id="stage2">⚡ Calculating demands</div>
                <div class="stage" id="stage3">📋 Rendering results</div>
            </div>
        </div>
    `;
    
    document.getElementById('loadingContainer').innerHTML = progressHTML;
}
```

## Medium-Term Improvements (1 Week Effort)### 5. Persistent Database Cache - **Expected 60-70% Improvement**Create a dedicated cache table to store calculated results:[5][6]

```sql
CREATE TABLE calculation_cache (
    sku_id VARCHAR(50) NOT NULL,
    warehouse ENUM('kentucky', 'burnaby') NOT NULL,
    enhanced_demand DECIMAL(10,2),
    calculation_strategy VARCHAR(50),
    abc_classification VARCHAR(10),
    xyz_classification VARCHAR(10),
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    data_hash VARCHAR(64), -- For invalidation
    PRIMARY KEY (sku_id, warehouse),
    INDEX idx_cache_expiry (expires_at),
    INDEX idx_cache_hash (data_hash)
);
```

**Cache Management Implementation:**
```python
class PersistentCacheManager:
    def __init__(self, db_session):
        self.db = db_session
        
    async def get_cached_demand(self, sku_id: str, warehouse: str) -> Optional[dict]:
        query = """
        SELECT enhanced_demand, calculation_strategy, abc_classification, xyz_classification
        FROM calculation_cache 
        WHERE sku_id = %s AND warehouse = %s AND expires_at > NOW()
        """
        result = await self.db.fetch_one(query, (sku_id, warehouse))
        return dict(result) if result else None
    
    async def cache_demand_result(self, sku_id: str, warehouse: str, result: dict):
        # Calculate data hash for invalidation
        data_hash = hashlib.md5(f"{sku_id}{warehouse}{result}".encode()).hexdigest()
        
        query = """
        INSERT INTO calculation_cache (sku_id, warehouse, enhanced_demand, calculation_strategy, 
                                     abc_classification, xyz_classification, expires_at, data_hash)
        VALUES (%s, %s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 4 HOUR), %s)
        ON DUPLICATE KEY UPDATE 
            enhanced_demand = VALUES(enhanced_demand),
            calculation_strategy = VALUES(calculation_strategy),
            calculated_at = NOW(),
            expires_at = VALUES(expires_at),
            data_hash = VALUES(data_hash)
        """
        
        await self.db.execute(query, (
            sku_id, warehouse, result['enhanced_demand'], 
            result['strategy'], result['abc_code'], result['xyz_code'], data_hash
        ))
```

### 6. Asynchronous Processing - **Expected 40-50% Improvement**Implement parallel processing for SKU calculations:[5][7]

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List

class AsyncCalculationEngine:
    def __init__(self, max_workers: int = 10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cache_manager = PersistentCacheManager()
    
    async def calculate_all_recommendations_async(self, sku_data_list: List[dict]) -> List[dict]:
        # Process SKUs in batches for better memory management
        batch_size = 500
        all_results = []
        
        for i in range(0, len(sku_data_list), batch_size):
            batch = sku_data_list[i:i + batch_size]
            
            # Create async tasks for parallel processing
            tasks = [
                self.process_sku_async(sku_data) 
                for sku_data in batch
            ]
            
            # Process batch in parallel
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and add successful results
            successful_results = [
                result for result in batch_results 
                if not isinstance(result, Exception)
            ]
            
            all_results.extend(successful_results)
            
            # Optional: Yield progress for real-time updates
            yield {"processed": len(all_results), "total": len(sku_data_list)}
        
        return all_results
    
    async def process_sku_async(self, sku_data: dict) -> dict:
        sku_id = sku_data['sku_id']
        
        # Check cache first (async)
        kentucky_cached = await self.cache_manager.get_cached_demand(sku_id, 'kentucky')
        burnaby_cached = await self.cache_manager.get_cached_demand(sku_id, 'burnaby')
        
        if kentucky_cached and burnaby_cached:
            return self.build_recommendation_from_cache(sku_data, kentucky_cached, burnaby_cached)
        
        # Run expensive calculations in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        if not kentucky_cached:
            kentucky_result = await loop.run_in_executor(
                self.executor, 
                self.calculate_weighted_demand, 
                sku_data, 'kentucky'
            )
            await self.cache_manager.cache_demand_result(sku_id, 'kentucky', kentucky_result)
        else:
            kentucky_result = kentucky_cached
            
        if not burnaby_cached:
            burnaby_result = await loop.run_in_executor(
                self.executor,
                self.calculate_weighted_demand,
                sku_data, 'burnaby'
            )
            await self.cache_manager.cache_demand_result(sku_id, 'burnaby', burnaby_result)
        else:
            burnaby_result = burnaby_cached
        
        return self.build_final_recommendation(sku_data, kentucky_result, burnaby_result)
```

### 7. DataTables Server-Side Processing - **Expected 70-80% Frontend Improvement**Implement server-side pagination and sorting:[4][8]

```python
@app.get("/api/transfer-recommendations/paginated")
async def get_recommendations_paginated(
    draw: int,  # DataTables parameter
    start: int = 0,  # Offset
    length: int = 100,  # Limit
    search_value: str = "",  # Search term
    order_column: int = 0,  # Sort column index
    order_dir: str = "asc"  # Sort direction
):
    # Build dynamic query based on DataTables parameters
    columns = ["sku_id", "description", "abc_code", "kentucky_qty", "burnaby_qty", "recommendation"]
    sort_column = columns[order_column] if order_column < len(columns) else "sku_id"
    
    base_query = """
    SELECT sku_id, description, abc_code, kentucky_qty, burnaby_qty, 
           calculated_recommendation as recommendation
    FROM transfer_recommendations_view  -- Pre-calculated view
    """
    
    where_conditions = []
    params = []
    
    if search_value:
        where_conditions.append("(sku_id LIKE %s OR description LIKE %s)")
        search_param = f"%{search_value}%"
        params.extend([search_param, search_param])
    
    if where_conditions:
        base_query += " WHERE " + " AND ".join(where_conditions)
    
    # Count total records (for pagination info)
    count_query = f"SELECT COUNT(*) as total FROM ({base_query}) as subquery"
    total_records = await db.fetch_val(count_query, params)
    
    # Add sorting and pagination
    final_query = f"""
    {base_query}
    ORDER BY {sort_column} {order_dir}
    LIMIT %s OFFSET %s
    """
    params.extend([length, start])
    
    records = await db.fetch_all(final_query, params)
    
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,  # Adjust if filtering
        "data": [list(record.values()) for record in records]
    }
```

## Architecture Changes (2+ Weeks)### 8. Background Processing with WebSockets - **Expected 90%+ Improvement**```python
from fastapi import WebSocket
import redis
from celery import Celery

# Celery setup for background processing
celery_app = Celery('transfer_planning', broker='redis://localhost:6379')

@celery_app.task
def calculate_all_recommendations_background(request_id: str):
    """Background task to calculate all recommendations"""
    try:
        # Update progress
        redis_client.hset(f"progress:{request_id}", "status", "started")
        
        results = []
        total_skus = get_total_sku_count()
        
        for i, batch in enumerate(get_sku_batches(batch_size=100)):
            batch_results = process_sku_batch(batch)
            results.extend(batch_results)
            
            # Update progress
            progress = (i + 1) * 100 / (total_skus / 100)
            redis_client.hset(f"progress:{request_id}", "progress", progress)
            redis_client.hset(f"progress:{request_id}", "processed", len(results))
        
        # Cache final results
        redis_client.hset(f"results:{request_id}", "data", json.dumps(results))
        redis_client.hset(f"progress:{request_id}", "status", "completed")
        
    except Exception as e:
        redis_client.hset(f"progress:{request_id}", "status", "error")
        redis_client.hset(f"progress:{request_id}", "error", str(e))

@app.websocket("/ws/transfer-progress/{request_id}")
async def websocket_progress(websocket: WebSocket, request_id: str):
    await websocket.accept()
    
    while True:
        progress_data = redis_client.hgetall(f"progress:{request_id}")
        
        if progress_data:
            await websocket.send_json({
                "status": progress_data.get("status", "pending"),
                "progress": float(progress_data.get("progress", 0)),
                "processed": int(progress_data.get("processed", 0))
            })
            
            if progress_data.get("status") in ["completed", "error"]:
                break
        
        await asyncio.sleep(0.5)  # Update every 500ms

@app.post("/api/transfer-recommendations/start")
async def start_calculation(background_tasks: BackgroundTasks):
    request_id = str(uuid.uuid4())
    
    # Start background calculation
    calculate_all_recommendations_background.delay(request_id)
    
    return {"request_id": request_id, "status": "started"}
```

## Expected Performance Improvements### Implementation Priority Matrix| Phase | Task | Days | Expected Improvement | Risk Level | ROI |
|-------|------|------|---------------------|------------|-----|
| **Immediate** | Database indexes | 0.5 | 30-40% | Low | Very High |
| **Immediate** | Progressive loading | 1.0 | 80% perceived | Low | Very High |
| **Immediate** | Query optimization | 0.5 | 15-25% | Medium | High |
| **Medium-term** | Persistent cache | 2.0 | 60-70% | Medium | Very High |
| **Medium-term** | Async processing | 3.0 | 40-50% | High | High |
| **Architecture** | Background jobs | 7.0 | 90%+ | High | Very High |

## Code Examples for Most Impactful Changes### Database Index Creation Script```python
def create_performance_indexes():
    """Execute this during maintenance window"""
    critical_indexes = [
        "CREATE INDEX idx_monthly_sales_composite ON monthly_sales (sku_id, year_month DESC, kentucky_sales, burnaby_sales)",
        "CREATE INDEX idx_sku_abc_xyz ON skus (abc_code, xyz_code, sku_id)"
    ]
    
    for index in critical_indexes:
        execute_with_retry(index)
        print(f"✓ {index}")
```

### Progressive Loading Integration```python
@app.get("/api/recommendations/progressive")
async def get_progressive_recommendations(priority_first: bool = True):
    if priority_first:
        # Return top 100 critical items immediately
        return get_priority_skus(limit=100)
    else:
        # Stream remaining items
        return get_remaining_skus()
```

This optimization strategy provides a clear path from your current **25-40 second load times** to the target **sub-5 second performance**, with the most impactful changes delivering immediate user experience improvements while building toward a robust, scalable architecture.
