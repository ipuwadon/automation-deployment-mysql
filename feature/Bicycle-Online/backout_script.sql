-- Dev Environment Backout ------------------
-- View -------------------------------------
source feature/Bicycle-Online/rollback/external_customer_products.sql

-- Procedure --------------------------------
-- 2026-10-18: customer_product_summary grouped by product_id, added total_orders
source feature/Bicycle-Online/rollback/customer_product_summary.sql

-- Table ------------------------------------
source feature/Bicycle-Online/rollback/order_details.sql
source feature/Bicycle-Online/rollback/orders.sql
source feature/Bicycle-Online/rollback/products.sql
source feature/Bicycle-Online/rollback/customer.sql