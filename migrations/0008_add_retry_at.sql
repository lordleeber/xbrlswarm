-- Step-27 keeps retry timing across API restarts without rebuilding task.
ALTER TABLE task ADD COLUMN retry_at TEXT;
