SELECT routine_name
FROM information_schema.routines
WHERE routine_type = 'PROCEDURE'
  AND routine_name = 'customer_product_summary';