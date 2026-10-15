CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE otps (
    id bigserial PRIMARY KEY,
    email text NOT NULL,
    code_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX otps_email_created_idx ON otps (email, created_at DESC);

CREATE TABLE broker_connections (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    kite_user_id text NOT NULL,
    user_name text,
    access_token_enc text,
    status text NOT NULL CHECK (status IN ('active', 'token_expired', 'disconnected')),
    connected_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    token_mail_sent_on date,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE oauth_clients (
    client_id text PRIMARY KEY,
    data jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE oauth_txns (
    txn_id text PRIMARY KEY,
    params jsonb NOT NULL,
    email text,
    expires_at timestamptz NOT NULL
);

CREATE TABLE oauth_codes (
    code text PRIMARY KEY,
    data jsonb NOT NULL,
    expires_at timestamptz NOT NULL
);

CREATE TABLE oauth_tokens (
    token_hash text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('access', 'refresh')),
    data jsonb NOT NULL,
    pair text NOT NULL,
    revoked boolean NOT NULL DEFAULT false,
    expires_at timestamptz NOT NULL
);
CREATE INDEX oauth_tokens_pair_idx ON oauth_tokens (pair);

CREATE TABLE watchers (
    id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    symbol text NOT NULL,
    label text NOT NULL,
    script text NOT NULL,
    market text NOT NULL,
    check_every_s integer NOT NULL,
    status text NOT NULL CHECK (status IN ('ARMED', 'PAUSED', 'ERROR', 'EXPIRED', 'CANCELLED')),
    status_reason text,
    paused_by text CHECK (paused_by IN ('user', 'broker')),
    baseline_done boolean NOT NULL DEFAULT false,
    latched boolean NOT NULL DEFAULT false,
    last_met boolean,
    last_value text,
    last_detail text,
    last_error text,
    error_count integer NOT NULL DEFAULT 0,
    last_checked_at timestamptz,
    last_fired_at timestamptz,
    fired_count integer NOT NULL DEFAULT 0,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX watchers_user_idx ON watchers (user_id, created_at DESC);
CREATE INDEX watchers_due_idx ON watchers (status, last_checked_at);

CREATE TABLE watcher_fires (
    id text PRIMARY KEY,
    watcher_id text NOT NULL REFERENCES watchers (id) ON DELETE CASCADE,
    fired_at timestamptz NOT NULL DEFAULT now(),
    value text,
    detail text,
    emailed boolean NOT NULL DEFAULT false
);
CREATE INDEX watcher_fires_watcher_idx ON watcher_fires (watcher_id, fired_at DESC);
