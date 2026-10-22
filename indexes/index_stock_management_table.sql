-- Index for product name search
CREATE INDEX idx_product_name ON product(product_name);

-- Index for warehouse name search
CREATE INDEX idx_warehouse_name ON warehouse(warehouse_name);

-- Index for faster stock movement queries
CREATE INDEX idx_stock_movement ON stock_movement(product_id, warehouse_id, movement_date);