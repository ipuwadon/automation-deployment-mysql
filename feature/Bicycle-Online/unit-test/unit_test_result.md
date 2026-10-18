# ✅ Unit test result - Bicycle-Online

- **Run at:** 2026-10-18 03:14:07Z
- **Commit:** `88395a82c788c83ac420a36c39447e6b81dfba58`
- **Procedures:** 1/1 passed
- **Assertions:** 2/2 passed

| Feature | Procedure | Status | Assertions | Generation | Test script |
|---|---|---|---|---|---|
| Bicycle-Online | `customer_product_summary` | ✅ PASS | 2/2 | fallback | [ut_customer_product_summary.sql](ut_customer_product_summary.sql) |

## ✅ `customer_product_summary`

- Source: `procedures/customer_product_summary.sql`
- Model: `qwen2.5-coder:1.5b` (fallback after 3 attempt(s))
- Duration: 2.12s
- ⚠️ AI generation fell back to baseline checks: MySQL error when executing it: ERROR 1064 (42000) at line 37: You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near 'CALL customer_product_summary()' at line 1

| # | Test case | Result | Details |
|---|---|---|---|
| 1 | procedure_exists | ✅ PASS | routines found: 1 |
| 2 | procedure_executes | ✅ PASS | CALL customer_product_summary() completed without error |

<details><summary>AI analysis</summary>

The stored procedure `customer_product_summary` is designed to provide a summary of customer orders and products. It retrieves data from the `customer`, `orders`, `order_details`, and `products` tables. The procedure groups the data by customer, product, and calculates the total number of orders, total quantity, and total spent for each product. The results are ordered by customer and total spent in descending order.

</details>
