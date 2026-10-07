-- Migration 012: Add cert_code to exam_history
CREATE TABLE IF NOT EXISTS exam_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role VARCHAR(64) NOT NULL,
    score INT NOT NULL,
    passed BOOLEAN NOT NULL,
    timestamp DOUBLE PRECISION NOT NULL,
    cert_code VARCHAR(32)
);

ALTER TABLE exam_history ADD COLUMN IF NOT EXISTS cert_code VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_exam_history_cert_code ON exam_history(cert_code);
