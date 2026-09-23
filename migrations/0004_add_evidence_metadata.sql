BEGIN IMMEDIATE;

ALTER TABLE evidence ADD COLUMN period_start TEXT;
ALTER TABLE evidence ADD COLUMN period_end TEXT;
ALTER TABLE evidence ADD COLUMN board_approved_date TEXT;
ALTER TABLE evidence ADD COLUMN audit_committee_date TEXT;
ALTER TABLE evidence ADD COLUMN company_name TEXT;

COMMIT;
