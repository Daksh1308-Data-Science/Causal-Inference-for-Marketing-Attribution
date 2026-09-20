-- ==== v_order_monthly (MySQL 8.0) ===========================================
-- Order-level monthly activity for cohort/retention analysis (Day 3).
-- One row per (customer, purchase-month): how many purchased orders and how
-- much revenue. "Purchased" follows the cohort definition from
-- v_customer_analytical (status NOT IN ('canceled','unavailable') AND >=1
-- order_items row).
--
-- Real Olist data only — no marketing variables here.
--
-- NOTE: this is a plain aggregation over orders x order_items (112,650 rows),
-- NOT the correlated-EXISTS pattern that broke v_customer_analytical
-- (ADR-008). Count uses COUNT(DISTINCT order_id) so multi-item orders count
-- once per month.

CREATE OR REPLACE VIEW v_order_monthly AS
SELECT
    c.customer_unique_id                   AS customer_id,
    DATE(DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m-01')) AS purchase_month,
    COUNT(DISTINCT o.order_id)             AS order_count,
    SUM(i.price + i.freight_value)         AS revenue
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN order_items i ON i.order_id = o.order_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY c.customer_unique_id, DATE(DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m-01'));