-- ============================================================
-- Doc-Agent 数据库初始化脚本
-- 用法: mysql -u root -p < init.sql
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `doc_agent`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `doc_agent`;

-- 创建任务表
DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks` (
    `id`            VARCHAR(32)     NOT NULL        COMMENT '任务唯一标识',
    `doc_type`      VARCHAR(100)    NOT NULL        COMMENT '文档类型',
    `custom_name`   VARCHAR(200)    NOT NULL DEFAULT '' COMMENT '自定义文档名称',
    `status`        VARCHAR(20)     NOT NULL        COMMENT '任务状态: pending/running/completed/failed',
    `material`      TEXT            NOT NULL        COMMENT '原始素材文本',
    `result_md`     MEDIUMTEXT      NULL            COMMENT '生成的 Markdown 文档',
    `outline_json`  TEXT            NULL            COMMENT '生成的大纲 JSON',
    `error`         TEXT            NULL            COMMENT '失败时的错误信息',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档生成任务表';
