-- Migration: Add LLM Analysis columns to domains table
-- Run this on PostgreSQL database for AI domain discovery

-- LLM Analysis columns
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_evaluated_at TIMESTAMP;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_category VARCHAR(100);
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_subcategory VARCHAR(100);
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_business_model VARCHAR(100);
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_target_audience VARCHAR(255);
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_product_description TEXT;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_quality_assessment VARCHAR(20);
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_is_legitimate BOOLEAN;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_confidence FLOAT;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_suggested_score INTEGER;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_red_flags JSONB;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_positive_signals JSONB;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS llm_raw_response JSONB;

-- Verify the columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'domains'
AND column_name LIKE 'llm_%'
ORDER BY column_name;
