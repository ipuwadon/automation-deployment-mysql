-- Dev Environment Release ------------------
-- Table ------------------------------------
source tables/product.sql
source tables/warehouse.sql
source tables/stock_movement.sql
source tables/audit_log.sql

-- Index ------------------------------------
source indexes/index_stock_management_table.sql

-- Trigger ------------------------------------
source triggers/trg_stock_movement_insert.sql

-- View -------------------------------------
source views/vw_stock_summary.sql

-- Procedure --------------------------------
source procedures/sp_transfer_stock.sql

-- Test ------------------------------------
source feature/Stock-Management/test/test_script.sql