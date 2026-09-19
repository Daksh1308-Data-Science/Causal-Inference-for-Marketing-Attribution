-- ==== Olist raw schema (MySQL 8.0) =================================================
-- Executed by src/data/load_olist.py. Drops + recreates the 9 raw tables
-- deterministically (idempotent rebuild). Column names match the source CSVs
-- exactly, including the upstream typos `product_name_lenght` /
-- `product_description_lenght` (kept for source fidelity: consumers use the
-- analytical view).
--
-- Dependencies honored: FKs point child→parent, drops run children-first.
-- Charset: utf8mb4. Engine: InnoDB. Dates: DATETIME (source is naive UTC).

USE olist;

-- --- DROP (children first) ---------------------------------------------------------
DROP TABLE IF EXISTS order_reviews;
DROP TABLE IF EXISTS order_payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS product_category_name_translation;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS geolocation;
DROP TABLE IF EXISTS customers;

-- --- CREATE (parents first) ---------------------------------------------------------

CREATE TABLE customers (
    customer_id             VARCHAR(32)  NOT NULL,
    customer_unique_id      VARCHAR(32)  NOT NULL,
    customer_zip_code_prefix INT         NOT NULL,
    customer_city           VARCHAR(64)  NOT NULL,
    customer_state          CHAR(2)      NOT NULL,
    PRIMARY KEY (customer_id),
    KEY idx_customers_unique (customer_unique_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 1M+ rows, repeated zip prefixes -> no natural unique key; index the prefix.
CREATE TABLE geolocation (
    geolocation_zip_code_prefix INT          NOT NULL,
    geolocation_lat             DECIMAL(10,6) NOT NULL,
    geolocation_lng             DECIMAL(10,6) NOT NULL,
    geolocation_city            VARCHAR(64)   NOT NULL,
    geolocation_state           CHAR(2)      NOT NULL,
    KEY idx_geolocation_zip (geolocation_zip_code_prefix)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
    product_id                VARCHAR(32) NOT NULL,
    product_category_name     VARCHAR(64) NULL,
    product_name_lenght       INT         NULL,  -- upstream typo, kept as-is
    product_description_lenght INT        NULL,  -- upstream typo, kept as-is
    product_photos_qty        INT         NULL,
    product_weight_g          INT         NULL,
    product_length_cm         INT         NULL,
    product_height_cm         INT         NULL,
    product_width_cm          INT         NULL,
    PRIMARY KEY (product_id),
    KEY idx_products_category (product_category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sellers (
    seller_id               VARCHAR(32) NOT NULL,
    seller_zip_code_prefix  INT         NOT NULL,
    seller_city             VARCHAR(64) NOT NULL,
    seller_state            CHAR(2)     NOT NULL,
    PRIMARY KEY (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_category_name_translation (
    product_category_name          VARCHAR(64) NOT NULL,
    product_category_name_english  VARCHAR(64) NOT NULL,
    PRIMARY KEY (product_category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE orders (
    order_id                      VARCHAR(32) NOT NULL,
    customer_id                   VARCHAR(32) NOT NULL,
    order_status                  VARCHAR(16) NOT NULL,
    order_purchase_timestamp      DATETIME    NOT NULL,
    order_approved_at             DATETIME    NULL,
    order_delivered_carrier_date  DATETIME    NULL,
    order_delivered_customer_date DATETIME    NULL,
    order_estimated_delivery_date DATETIME    NULL,
    PRIMARY KEY (order_id),
    KEY idx_orders_customer (customer_id),
    KEY idx_orders_purchase (order_purchase_timestamp),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE order_items (
    order_id           VARCHAR(32)  NOT NULL,
    order_item_id      INT          NOT NULL,
    product_id         VARCHAR(32)  NOT NULL,
    seller_id          VARCHAR(32)  NOT NULL,
    shipping_limit_date DATETIME    NULL,
    price              DECIMAL(10,2) NOT NULL,
    freight_value      DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    KEY idx_order_items_product (product_id),
    KEY idx_order_items_seller (seller_id),
    CONSTRAINT fk_order_items_order   FOREIGN KEY (order_id)   REFERENCES orders (order_id),
    CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products (product_id),
    CONSTRAINT fk_order_items_seller  FOREIGN KEY (seller_id)  REFERENCES sellers (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE order_payments (
    order_id            VARCHAR(32)  NOT NULL,
    payment_sequential  INT          NOT NULL,
    payment_type        VARCHAR(32)  NOT NULL,
    payment_installments INT         NOT NULL,
    payment_value       DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential),
    KEY idx_payments_type (payment_type),
    CONSTRAINT fk_order_payments_order FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- review_id carries empty strings in the source -> loader assigns a surrogate
-- when empty so the PK stays sound (reported as `review_id_imputed` in the load report).
CREATE TABLE order_reviews (
    review_id              VARCHAR(32) NOT NULL,
    order_id               VARCHAR(32) NOT NULL,
    review_score           TINYINT     NULL,
    review_comment_title   TEXT        NULL,
    review_comment_message TEXT        NULL,
    review_creation_date   DATETIME    NULL,
    review_answer_timestamp DATETIME   NULL,
    PRIMARY KEY (review_id),
    KEY idx_order_reviews_order (order_id),
    KEY idx_order_reviews_score (review_score),
    CONSTRAINT fk_order_reviews_order FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;