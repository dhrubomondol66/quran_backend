-- Run this against your PostgreSQL database to update the schema
ALTER TABLE users ADD COLUMN is_suspended BOOLEAN DEFAULT FALSE NOT NULL;
