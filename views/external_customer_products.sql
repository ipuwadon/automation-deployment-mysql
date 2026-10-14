CREATE VIEW external_customer_products AS
SELECT 
    c.full_name AS customer,
    p.product_name AS product,
    SUM(od.quantity) AS quantity,
    SUM(od.quantity * p.price) AS total_spent
FROM customer c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_details od ON o.order_id = od.order_id
JOIN products p ON od.product_id = p.product_id
GROUP BY c.full_name, p.product_name;