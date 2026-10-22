-- Auto-generated unit test for procedure `sp_transfer_stock`
-- Source     : procedures/sp_transfer_stock.sql
-- Model      : qwen2.5-coder:1.5b | generation: fallback | attempts: 3
-- Generated  : 2026-10-22 15:18:45Z
-- Contract   : each assertion returns 'UT_RESULT', <test_case>, 'PASS'|'FAIL', <details>
-- AI analysis:
--   - The stored procedure `sp_transfer_stock` is designed to transfer stock between two warehouses based on the provided product ID, source warehouse ID, destination warehouse ID, and quantity.
--   - The procedure inserts stock movement records for both the IN and OUT transactions.
--   - The procedure checks for the existence of the product and the availability of stock in the source warehouse before performing the transfer.
--   - The procedure updates the stock quantity in both warehouses after the transfer.
--   - The procedure handles edge cases such as the product not existing in the source warehouse or insufficient stock in the source warehouse.
--   - The procedure introduces a risk of data inconsistency if the procedure is not properly tested and maintained.

-- Baseline checks
SELECT 'UT_RESULT', 'procedure_exists', IF(COUNT(*) = 1, 'PASS', 'FAIL'),
       CONCAT('routines found: ', COUNT(*))
FROM information_schema.routines
WHERE routine_schema = DATABASE() AND routine_type = 'PROCEDURE' AND routine_name = 'sp_transfer_stock';

START TRANSACTION;

ROLLBACK;
