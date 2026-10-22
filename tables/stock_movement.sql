-- Stock movement log (records IN/OUT transactions)
CREATE TABLE stock_movement (
    movement_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    warehouse_id INT NOT NULL,
    movement_type ENUM('IN','OUT') NOT NULL,
    quantity INT NOT NULL,
    movement_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES product(product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id)
);