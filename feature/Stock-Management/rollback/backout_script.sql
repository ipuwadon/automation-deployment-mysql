-- ================================
-- Backout Script: Stock Management
-- ================================

-- Drop procedure
DROP PROCEDURE IF EXISTS sp_transfer_stock;

-- Drop triggers
DROP TRIGGER IF EXISTS trg_stock_movement_insert;

-- Drop views
DROP VIEW IF EXISTS vw_stock_summary;

-- Drop tables (reverse order of dependencies)
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS stock_movement;
DROP TABLE IF EXISTS warehouse;
DROP TABLE IF EXISTS product;