USE dev;

ALTER TABLE customers ADD COLUMN phone VARCHAR(20);

CREATE TABLE claims (
    id INT AUTO_INCREMENT PRIMARY KEY,
    policy_id INT NOT NULL,
    claim_date DATE,
    amount DECIMAL(10,2),
    FOREIGN KEY (policy_id) REFERENCES policies(id)
);