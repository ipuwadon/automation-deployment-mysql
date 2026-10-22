-- Procedure to transfer stock between warehouses
DELIMITER $$
CREATE PROCEDURE sp_transfer_stock(
    IN prod_id INT,
    IN from_wh INT,
    IN to_wh INT,
    IN qty INT
)
BEGIN
    -- Record stock OUT from source warehouse
    INSERT INTO stock_movement(product_id, warehouse_id, movement_type, quantity)
    VALUES (prod_id, from_wh, 'OUT', qty);

    -- Record stock IN to destination warehouse
    INSERT INTO stock_movement(product_id, warehouse_id, movement_type, quantity)
    VALUES (prod_id, to_wh, 'IN', qty);
END $$
DELIMITER ;