-- Replay protection for the jwt-bearer (trusted-app) grant: every accepted assertion's
-- `jti` is recorded until it expires. Rows are pruned on each issue.
CREATE TABLE oauth_assertions (
    jti text PRIMARY KEY,
    expires_at timestamptz NOT NULL
);
