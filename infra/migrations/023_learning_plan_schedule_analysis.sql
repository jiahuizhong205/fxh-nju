ALTER TABLE learning_plans
    ADD COLUMN IF NOT EXISTS schedule_analysis JSONB NOT NULL DEFAULT '{}'::jsonb;
