CREATE TABLE `mixed_annotation_items` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `tags` TEXT,
    `meta` TEXT,
    `description` TEXT,
    `status` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;