BEGIN IMMEDIATE;

CREATE TABLE task_step9 (
    id INTEGER PRIMARY KEY,
    stock_id TEXT NOT NULL CHECK (length(stock_id) > 0),
    fiscal_year INTEGER NOT NULL CHECK (fiscal_year > 0),
    report_period TEXT NOT NULL CHECK (report_period IN ('Q1', 'Q2', 'Q3', 'FY')),
    state TEXT NOT NULL CHECK (length(state) > 0),
    engine TEXT NOT NULL CHECK (
        engine IN ('mops', 'goodinfo', 'yahoo', 'google', 'grounded_ai')
    ),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    fail_count INTEGER NOT NULL DEFAULT 0 CHECK (fail_count >= 0),
    dispatched_at TEXT,
    worker_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CONSTRAINT task_identity_unique UNIQUE (stock_id, fiscal_year, report_period)
) STRICT;

INSERT OR ROLLBACK INTO task_step9 (
    id,
    stock_id,
    fiscal_year,
    report_period,
    state,
    engine,
    attempts,
    fail_count,
    dispatched_at,
    worker_id,
    created_at,
    updated_at
)
SELECT
    id,
    stock_id,
    fiscal_year,
    report_period,
    state,
    engine,
    attempts,
    fail_count,
    dispatched_at,
    worker_id,
    created_at,
    updated_at
FROM task;

DROP TABLE task;
ALTER TABLE task_step9 RENAME TO task;

COMMIT;
