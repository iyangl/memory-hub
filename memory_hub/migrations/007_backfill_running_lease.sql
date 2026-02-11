UPDATE catalog_jobs
SET lease_expires_at = '1970-01-01T00:00:00+00:00'
WHERE status = 'running' AND lease_expires_at IS NULL;
