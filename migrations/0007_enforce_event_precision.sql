BEGIN IMMEDIATE;

-- Step-15 stored Goodinfo speech times without an explicit precision. The
-- existing rows remain immutable; the identity projection makes their NULL
-- precision equivalent to Step-17's explicit second for retry purposes.
CREATE TEMP TABLE step17_duplicate_guard (
    duplicate_count INTEGER NOT NULL CHECK (duplicate_count = 0)
) STRICT;

INSERT OR ROLLBACK INTO step17_duplicate_guard (duplicate_count)
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
    COALESCE(event_precision, 'second'),
    source_subject,
    COALESCE(raw_payload_hash, X'')
HAVING COUNT(*) > 1
LIMIT 1;

DROP TABLE step17_duplicate_guard;

DROP INDEX evidence_goodinfo_logical_identity_unique;

CREATE UNIQUE INDEX evidence_goodinfo_logical_identity_unique
ON evidence (
    task_id,
    source_type,
    source_locator,
    evidence_type,
    event_date,
    event_time,
    COALESCE(event_precision, 'second'),
    source_subject,
    COALESCE(raw_payload_hash, X'')
)
WHERE source_type = 'goodinfo'
  AND source_locator IS NOT NULL
  AND event_date IS NOT NULL
  AND event_time IS NOT NULL
  AND source_subject IS NOT NULL;

-- No event claim is valid with only a precision or only a time. New writes
-- must carry date precision for a date alone, and second precision for a
-- date with an explicitly supplied time. Legacy rows are not rewritten.
CREATE TRIGGER evidence_event_precision_insert
BEFORE INSERT ON evidence
WHEN NOT (
    (NEW.event_date IS NULL AND NEW.event_time IS NULL
     AND NEW.event_precision IS NULL)
    OR (NEW.event_date IS NOT NULL AND NEW.event_time IS NULL
        AND NEW.event_precision IS 'date')
    OR (NEW.event_date IS NOT NULL AND NEW.event_time IS NOT NULL
        AND NEW.event_precision IS 'second')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid event precision');
END;

COMMIT;
