CREATE TABLE evidence (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE RESTRICT,
    evidence_type TEXT NOT NULL CHECK (
        evidence_type IN (
            'xbrl_document',
            'financial_report_document',
            'material_announcement',
            'search_mirror',
            'manual_review'
        )
    ),
    event_date TEXT,
    event_time TEXT,
    event_precision TEXT,
    source_type TEXT NOT NULL CHECK (length(source_type) > 0),
    source_endpoint TEXT,
    source_url TEXT,
    source_locator TEXT,
    source_title TEXT,
    source_subject TEXT,
    retrieved_at TEXT NOT NULL CHECK (length(retrieved_at) > 0),
    raw_payload_hash TEXT,
    verification_state TEXT NOT NULL CHECK (length(verification_state) > 0)
) STRICT;
