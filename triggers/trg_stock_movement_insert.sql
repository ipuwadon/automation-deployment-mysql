-- Trigger for stock movement insert
CREATE TRIGGER trg_stock_movement_insert
AFTER INSERT ON stock_movement
FOR EACH ROW
INSERT INTO audit_log(table_name, action, details)
VALUES ('stock_movement', 'INSERT', 
        CONCAT('Movement ', NEW.movement_type, 
               ' of ', NEW.quantity, 
               ' units for product_id ', NEW.product_id,
               ' in warehouse_id ', NEW.warehouse_id));