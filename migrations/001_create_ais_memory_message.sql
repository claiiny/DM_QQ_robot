-- AI 对话记忆持久化表
-- 存储从 Redis 工作集中淘汰的历史消息，以及服务重启时的上下文恢复。

CREATE TABLE IF NOT EXISTS dmwd_for_owner.ais_memory_message (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     VARCHAR(128) NOT NULL,
    role        VARCHAR(16)  NOT NULL,
    content     TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ais_memory_user_created
    ON dmwd_for_owner.ais_memory_message (user_id, created_at);
