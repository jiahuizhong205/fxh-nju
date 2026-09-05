ALTER TABLE learning_plans
    ADD COLUMN IF NOT EXISTS sync_fingerprint VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE recommendation_reports
    ADD COLUMN IF NOT EXISTS sync_fingerprint VARCHAR(64) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS ix_learning_plans_user_sync_fingerprint
    ON learning_plans (user_id, sync_fingerprint);

CREATE INDEX IF NOT EXISTS ix_recommendation_reports_user_sync_fingerprint
    ON recommendation_reports (user_id, sync_fingerprint);
