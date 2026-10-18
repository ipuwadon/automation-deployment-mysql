-- Auto-generated unit test for procedure `customer_product_summary`
-- Source     : procedures/customer_product_summary.sql
-- Model      : qwen2.5-coder:1.5b | generation: fallback | attempts: 3
-- Generated  : 2026-10-18 03:14:03Z
-- Contract   : each assertion returns 'UT_RESULT', <test_case>, 'PASS'|'FAIL', <details>
-- AI analysis:
--   The stored procedure `customer_product_summary` is designed to provide a summary of customer orders and products. It retrieves data from the `customer`, `orders`, `order_details`, and `products` tables. The procedure groups the data by customer, product, and calculates the total number of orders, total quantity, and total spent for each product. The results are ordered by customer and total spent in descending order.

-- Baseline checks
SELECT 'UT_RESULT', 'procedure_exists', IF(COUNT(*) = 1, 'PASS', 'FAIL'),
       CONCAT('routines found: ', COUNT(*))
FROM information_schema.routines
WHERE routine_schema = DATABASE() AND routine_type = 'PROCEDURE' AND routine_name = 'customer_product_summary';

CALL `customer_product_summary`();
SELECT 'UT_RESULT', 'procedure_executes', 'PASS', 'CALL customer_product_summary() completed without error';

START TRANSACTION;

ROLLBACK;
