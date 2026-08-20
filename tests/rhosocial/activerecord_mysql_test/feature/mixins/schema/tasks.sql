-- tests/rhosocial/activerecord_mysql_test/feature/mixins/schema/tasks.sql
-- MySQL version of the tasks table schema with soft deletion support

CREATE TABLE `tasks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `is_completed` TINYINT(1) NOT NULL DEFAULT 0,
    `deleted_at` TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;