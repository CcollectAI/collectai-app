-- Push notification tokens (Expo Push)
-- Stores device tokens for sending push notifications via Expo's Push API

CREATE TABLE IF NOT EXISTS public.user_push_tokens (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     text NOT NULL,
    push_token  text NOT NULL,         -- ExponentPushToken[xxxx]
    platform    text NOT NULL DEFAULT 'unknown',  -- ios | android | web
    device_name text,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    UNIQUE (user_id, push_token)
);

CREATE INDEX IF NOT EXISTS idx_push_tokens_user
    ON public.user_push_tokens (user_id)
    WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_push_tokens_token
    ON public.user_push_tokens (push_token);
