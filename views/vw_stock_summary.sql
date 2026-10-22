-- View to show current stock per product per warehouse
CREATE VIEW vw_stock_summary AS
SELECT 
    p.product_id,
    p.product_name,
    w.warehouse_name,
    SUM(CASE WHEN s.movement_type = 'IN' THEN s.quantity ELSE -s.quantity END) AS current_stock
FROM stock_movement s
JOIN product p ON s.product_id = p.product_id
JOIN warehouse w ON s.warehouse_id = w.warehouse_id
GROUP BY p.product_id, p.product_name, w.warehouse_name;