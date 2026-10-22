-- ================================
-- Test Script: Verify Deployment
-- ================================

-- 1. Verify tables exist
SHOW TABLES LIKE 'product';
SHOW TABLES LIKE 'warehouse';
SHOW TABLES LIKE 'stock_movement';
SHOW TABLES LIKE 'audit_log';

-- 2. Verify indexes
SHOW INDEX FROM product;
SHOW INDEX FROM warehouse;
SHOW INDEX FROM stock_movement;

-- 3. Verify view
SHOW FULL TABLES WHERE TABLE_TYPE = 'VIEW';
SELECT * FROM vw_stock_summary LIMIT 5;

-- 4. Verify trigger
SHOW TRIGGERS LIKE 'stock_movement';

-- Insert test data to trigger audit log
INSERT INTO product(product_name, price) VALUES ('Test Widget', 10.00);
INSERT INTO warehouse(warehouse_name, location) VALUES ('Main Warehouse', 'Bangkok');
INSERT INTO stock_movement(product_id, warehouse_id, movement_type, quantity)
VALUES (1, 1, 'IN', 100);

-- Check audit log entry
SELECT * FROM audit_log ORDER BY changed_at DESC LIMIT 5;

-- 5. Verify procedure
CALL sp_transfer_stock(1, 1, 1, 5);

-- Check stock summary after procedure
SELECT * FROM vw_stock_summary WHERE product_id = 1;