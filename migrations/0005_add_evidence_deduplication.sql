BEGIN IMMEDIATE;

CREATE TEMP TABLE step13_duplicate_guard (
    duplicate_count INTEGER NOT NULL CHECK (duplicate_count = 0)
) STRICT;

INSERT OR ROLLBACK INTO step13_duplicate_guard (duplicate_count)
SELECT 1
FROM evidence
WHERE source_type = 'mops'
  AND source_locator IS NOT NULL
  AND raw_payload_hash IS NOT NULL
GROUP BY
    task_id,
    source_type,
    source_locator,
    evidence_type,
    COALESCE(event_date, X''),
    COALESCE(event_time, X''),
    COALESCE(event_precision, X''),
    raw_payload_hash
HAVING COUNT(*) > 1
LIMIT 1;

INSERT OR ROLLBACK INTO step13_duplicate_guard (duplicate_count)
SELECT 1
FROM evidence
WHERE source_type = 'goodinfo'
  AND source_locator IS NOT NULL
  AND event_date IS NOT NULL
  AND event_time IS NOT NULL
  AND source_subject IS NOT NULL
GROUP BY
    task_id,
    source_type,
    source_locator,
    evidence_type,
    event_date,
    event_time,
    COALESCE(event_precision, X''),
    source_subject,
    COALESCE(raw_payload_hash, X'')
HAVING COUNT(*) > 1
LIMIT 1;

DROP TABLE step13_duplicate_guard;

CREATE UNIQUE INDEX evidence_mops_logical_identity_unique
ON evidence (
    task_id,
    source_type,
    source_locator,
    evidence_type,
    COALESCE(event_date, X''),
    COALESCE(event_time, X''),
    COALESCE(event_precision, X''),
    raw_payload_hash
)
WHERE source_type = 'mops'
  AND source_locator IS NOT NULL
  AND raw_payload_hash IS NOT NULL;

CREATE UNIQUE INDEX evidence_goodinfo_logical_identity_unique
ON evidence (
    task_id,
    source_type,
    source_locator,
    evidence_type,
    event_date,
    event_time,
    COALESCE(event_precision, X''),
    source_subject,
    COALESCE(raw_payload_hash, X'')
)
WHERE source_type = 'goodinfo'
  AND source_locator IS NOT NULL
  AND event_date IS NOT NULL
  AND event_time IS NOT NULL
  AND source_subject IS NOT NULL;

COMMIT;
