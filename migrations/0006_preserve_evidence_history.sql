PRAGMA recursive_triggers = ON;

BEGIN IMMEDIATE;

CREATE TRIGGER evidence_source_immutable_update
BEFORE UPDATE ON evidence
WHEN OLD.id IS NOT NEW.id
  OR OLD.task_id IS NOT NEW.task_id
  OR OLD.evidence_type IS NOT NEW.evidence_type
  OR OLD.event_date IS NOT NEW.event_date
  OR OLD.event_time IS NOT NEW.event_time
  OR OLD.event_precision IS NOT NEW.event_precision
  OR OLD.source_type IS NOT NEW.source_type
  OR OLD.source_endpoint IS NOT NEW.source_endpoint
  OR OLD.source_url IS NOT NEW.source_url
  OR OLD.source_locator IS NOT NEW.source_locator
  OR OLD.source_title IS NOT NEW.source_title
  OR OLD.source_subject IS NOT NEW.source_subject
  OR OLD.retrieved_at IS NOT NEW.retrieved_at
  OR OLD.raw_payload_hash IS NOT NEW.raw_payload_hash
  OR OLD.company_name IS NOT NEW.company_name
BEGIN
    SELECT RAISE(ABORT, 'immutable source evidence');
END;

CREATE TRIGGER evidence_source_immutable_delete
BEFORE DELETE ON evidence
BEGIN
    SELECT RAISE(ABORT, 'immutable source evidence');
END;

COMMIT;
