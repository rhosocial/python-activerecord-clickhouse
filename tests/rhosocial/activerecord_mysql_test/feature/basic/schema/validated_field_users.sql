-- tests/rhosocial/activerecord_mysql_test/feature/basic/schema/validated_field_users.sql
-- MySQL version of the validated_field_users table schema

CREATE TABLE `validated_field_users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(255) NOT NULL,
    `email` VARCHAR(255) NOT NULL,
    `age` INT,
    `balance` DECIMAL(10,2),
    `credit_score` INT NOT NULL,
    `status` ENUM('active', 'inactive', 'banned', 'pending', 'suspended') NOT NULL DEFAULT 'active',
    `is_active` TINYINT NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;