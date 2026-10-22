-- ================================
-- Backout Script: Stock Management
-- ================================

-- Drop procedure
DROP PROCEDURE IF EXISTS sp_transfer_stock;

-- Drop triggers
DROP TRIGGER IF EXISTS trg_stock_movement_insert;

-- Drop views
DROP VIEW IF EXISTS vw_stock_summary;

-- Drop indexes (must be dropped before tables if named explicitly)
-- Note: MySQL automatically drops indexes when dropping tables,
-- but explicit DROP INDEX is safer if you want selective rollback.
DROP INDEX idx_product_name ON product;
DROP INDEX idx_warehouse_name ON warehouse;
DROP INDEX idx_stock_movement ON stock_movement;

-- Drop tables (reverse order of dependencies)
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS stock_movement;
DROP TABLE IF EXISTS warehouse;
DROP TABLE IF EXISTS product;