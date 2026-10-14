DELIMITER $$

CREATE PROCEDURE customer_product_summary()
BEGIN
    SELECT 
        c.customer_id,
        c.full_name,
        p.product_name,
        SUM(od.quantity) AS total_quantity,
        SUM(od.quantity * p.price) AS total_spent
    FROM customer c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_details od ON o.order_id = od.order_id
    JOIN products p ON od.product_id = p.product_id
    GROUP BY c.customer_id, p.product_name
    ORDER BY c.customer_id;
END $$

DELIMITER ;