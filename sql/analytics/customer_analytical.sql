-- ==== v_customer_analytical (MySQL 8.0) ===========================================
-- Customer-level analytical table for the causal analysis (Day 2 deliverable).
-- Real Olist data only — NO marketing variables here; the simulated marketing
-- layer (sim_*) joins on top of this in the simulation module.
--
-- Cohort definition: customers with >= 1 "purchased order" = an order with
-- order_status NOT IN ('canceled','unavailable') AND at least one order_items
-- row (i.e. a recorded purchase). N = 94,983.
-- Excluded: 7 customers whose only valid orders are early-pipeline with no
-- items (8 orders: 5 'created', 2 'invoiced', 1 'shipped').
--
-- RFM + tenure + geography + review proxies; recency_days/tenure_days are
-- measured against the data end (max purchase ts). The simulation later
-- recomputes recency relative to each campaign date.
--
-- NOTE on ONLY_FULL_GROUP_BY: end-of-data is fetched via scalar subqueries so
-- the aggregates remain legal without putting eod columns in GROUP BY.
--
-- PERFORMANCE NOTE (2026-09-19, ADR in docs/decisions.md):
--   The previous version filtered purchased orders with a correlated
--   EXISTS over order_items. MySQL 8.0 fused that semi-join with the outer
--   equi-joins on the SAME order_items table into a catastrophic plan
--   (order_items full scan x customers hash join) -> query did not finish
--   (>300 s). Replacing EXISTS with  JOIN order_items ... SELECT DISTINCT
--   materializes the purchased-order set ONCE and MySQL reuses it across all
--   consumer CTEs. Measured: 22.8 s for SELECT COUNT(*) (vs. unfinished).
--   Remaining cost is the five per-customer aggregation passes, which is
--   inherent to a view on this machine.

CREATE OR REPLACE VIEW v_customer_analytical AS
WITH purchased_orders AS (
    -- one row per purchased order: order facts + customer geography,
    -- deduplicated (an order joins to >=1 item row).
    SELECT DISTINCT
        o.order_id, o.customer_id, c.customer_unique_id, c.customer_state,
        o.order_purchase_timestamp
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
),
customer_base AS (
    SELECT
        customer_unique_id                    AS customer_id,
        MIN(order_purchase_timestamp)         AS first_order_date,
        MAX(order_purchase_timestamp)         AS last_order_date,
        COUNT(DISTINCT order_id)              AS order_count
    FROM purchased_orders
    GROUP BY customer_unique_id
),
revenue AS (
    SELECT
        c.customer_unique_id AS customer_id,
        SUM(i.price + i.freight_value) AS total_revenue
    FROM customers c
    JOIN purchased_orders o ON o.customer_id = c.customer_id
    JOIN order_items i      ON i.order_id   = o.order_id
    GROUP BY c.customer_unique_id
),
reviews AS (
    SELECT
        c.customer_unique_id              AS customer_id,
        AVG(r.review_score)               AS review_score_avg,
        COUNT(DISTINCT r.review_id)       AS review_count
    FROM customers c
    JOIN purchased_orders o ON o.customer_id = c.customer_id
    JOIN order_reviews r    ON r.order_id   = o.order_id
    GROUP BY c.customer_unique_id
),
category_affinity AS (
    SELECT customer_id, product_category_name, cnt,
           ROW_NUMBER() OVER (
               PARTITION BY customer_id
               ORDER BY cnt DESC, product_category_name
           ) AS rn
    FROM (
        SELECT
            c.customer_unique_id AS customer_id,
            p.product_category_name,
            COUNT(*) AS cnt
        FROM customers c
        JOIN purchased_orders o ON o.customer_id = c.customer_id
        JOIN order_items i      ON i.order_id   = o.order_id
        JOIN products p         ON p.product_id = i.product_id
        WHERE p.product_category_name IS NOT NULL
        GROUP BY c.customer_unique_id, p.product_category_name
    ) t
),
-- Some unique customers appear under multiple customer_ids in different states
-- (39 of 94,983). Assign the state of the customer's EARLIEST purchased order.
state_lookup AS (
    SELECT customer_unique_id, customer_state,
           ROW_NUMBER() OVER (
               PARTITION BY customer_unique_id
               ORDER BY order_purchase_timestamp, customer_id
           ) AS rn
    FROM purchased_orders
)
SELECT
    cb.customer_id,
    cb.first_order_date,
    cb.last_order_date,
    DATEDIFF((SELECT MAX(o.order_purchase_timestamp) FROM purchased_orders o), cb.first_order_date) AS tenure_days,
    DATEDIFF((SELECT MAX(o.order_purchase_timestamp) FROM purchased_orders o), cb.last_order_date)  AS recency_days,
    cb.order_count,
    rv.total_revenue,
    ROUND(rv.total_revenue / cb.order_count, 2)  AS avg_order_value,
    ca.product_category_name                      AS category_affinity_top,
    sl.customer_state                             AS state,
    rr.review_score_avg,
    rr.review_count
FROM customer_base cb
JOIN revenue rv          ON rv.customer_id = cb.customer_id
LEFT JOIN reviews rr     ON rr.customer_id = cb.customer_id
LEFT JOIN category_affinity ca ON ca.customer_id = cb.customer_id AND ca.rn = 1
LEFT JOIN state_lookup sl     ON sl.customer_unique_id = cb.customer_id AND sl.rn = 1;