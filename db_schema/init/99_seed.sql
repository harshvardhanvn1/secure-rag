-- Optional: create a demo user so you can immediately call /search (ACL will be granted on ingest anyway)
INSERT INTO app_user (email, display_name)
VALUES ('alice@example.com', 'Alice')
ON CONFLICT (email) DO UPDATE SET display_name=EXCLUDED.display_name;
