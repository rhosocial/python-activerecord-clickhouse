-- tests/rhosocial/activerecord_mysql_test/feature/basic/schema/validated_users.sql
-- MySQL version of the validated_users table schema

CREATE TABLE `validated_users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL,
    `email` VARCHAR(255) NOT NULL,
    `age` INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;