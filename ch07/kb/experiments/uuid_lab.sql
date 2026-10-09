\timing off
DROP TABLE IF EXISTS u4, u7;
CREATE TABLE u4 (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), n int);
CREATE TABLE u7 (id uuid PRIMARY KEY DEFAULT uuidv7(), n int);
\echo inserting 1,000,000 rows, uuid4:
\timing on
INSERT INTO u4 (n) SELECT g FROM generate_series(1, 1000000) g;
\timing off
\echo inserting 1,000,000 rows, uuid7:
\timing on
INSERT INTO u7 (n) SELECT g FROM generate_series(1, 1000000) g;
\timing off
SELECT 'uuid4' AS type, pg_size_pretty(pg_relation_size('u4_pkey')) AS "index"
UNION ALL
SELECT 'uuid7', pg_size_pretty(pg_relation_size('u7_pkey'));
