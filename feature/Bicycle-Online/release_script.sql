-- Dev Environment Release ------------------
-- Table ------------------------------------
source tables/customer.sql
source feature/Bicycle-Online/test/test_customer.sql

source tables/products.sql
source feature/Bicycle-Online/test/test_products.sql

source tables/orders.sql
source feature/Bicycle-Online/test/test_orders.sql

source tables/order_details.sql
source feature/Bicycle-Online/test/test_order_details.sql

-- View -------------------------------------
source views/external_customer_products.sql
source feature/Bicycle-Online/test/test_external_customer_products.sql

-- Procedure --------------------------------
-- 2026-10-18: customer_product_summary grouped by product_id, added total_orders
source procedures/customer_product_summary.sql
source feature/Bicycle-Online/test/test_customer_product_summary.sql

-- Script ----------------------------------
source scripts/insert_inital_data.sql
source feature/Bicycle-Online/test/test_insert_initial_data.sql