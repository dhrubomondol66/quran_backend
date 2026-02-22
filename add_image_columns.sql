-- Add profile_image_url to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS profile_image_url VARCHAR(500);

-- Add community_image_url to communities table
ALTER TABLE communities 
ADD COLUMN IF NOT EXISTS community_image_url VARCHAR(500);

-- Verify
SELECT COUNT(*) FROM users WHERE profile_image_url IS NOT NULL;
SELECT COUNT(*) FROM communities WHERE community_image_url IS NOT NULL;