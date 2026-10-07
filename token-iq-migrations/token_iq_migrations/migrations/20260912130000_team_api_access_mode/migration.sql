-- courier_mode could say "only the provider addresses" or nothing at all. It could not say
-- "only the shared address", and it could not say "either, while this team migrates one
-- application at a time". Three answers need a column that can hold three.
--
-- No backfill: courier_mode shipped on this branch and has never been released, so no
-- deployment holds a value worth carrying over. "both" is what every team behaved as
-- before the setting existed.
ALTER TABLE "LiteLLM_TeamTable" ADD COLUMN IF NOT EXISTS "api_access_mode" TEXT NOT NULL DEFAULT 'both';
ALTER TABLE "LiteLLM_TeamTable" DROP COLUMN IF EXISTS "courier_mode";

ALTER TABLE "LiteLLM_DeletedTeamTable" ADD COLUMN IF NOT EXISTS "api_access_mode" TEXT NOT NULL DEFAULT 'both';
ALTER TABLE "LiteLLM_DeletedTeamTable" DROP COLUMN IF EXISTS "courier_mode";

-- Same omission, one table over: provider_credentials went onto the key but not onto the
-- record a deleted key is archived into, so /key/delete returned 500 for every key.
ALTER TABLE "LiteLLM_DeletedVerificationToken" ADD COLUMN IF NOT EXISTS "provider_credentials" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];
