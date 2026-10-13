INSERT INTO customer (full_name, email, phone, address)
VALUES
('Alice Johnson', 'alice@example.com', '0812345678', 'Bangkok, Thailand'),
('Bob Smith', 'bob@example.com', '0823456789', 'Chiang Mai, Thailand'),
('Charlie Tan', 'charlie@example.com', '0834567890', 'Phuket, Thailand');

INSERT INTO products (product_name, category, price, stock)
VALUES
('Mountain Bike X1', 'Mountain', 15000.00, 10),
('Road Bike R2', 'Road', 22000.00, 5),
('Hybrid Bike H3', 'Hybrid', 18000.00, 8),
('Kids Bike K4', 'Kids', 8000.00, 15);

INSERT INTO orders (customer_id, order_date)
VALUES
(1, '2026-10-01 10:00:00'),
(2, '2026-10-02 14:30:00'),
(3, '2026-10-03 09:15:00');

INSERT INTO order_details (order_id, product_id, quantity)
VALUES
(1, 1, 1),   -- Alice buys 1 Mountain Bike
(1, 4, 2),   -- Alice also buys 2 Kids Bikes
(2, 2, 1),   -- Bob buys 1 Road Bike
(3, 3, 1),   -- Charlie buys 1 Hybrid Bike
(3, 4, 1);   -- Charlie also buys 1 Kids Bike