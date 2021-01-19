-- MySQL dump 10.13  Distrib 8.0.22, for Linux (x86_64)
--
-- Host: localhost    Database: talya
-- ------------------------------------------------------
-- Server version	8.0.22

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `addresses`
--

DROP TABLE IF EXISTS `addresses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `addresses` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `name` varchar(32) COLLATE utf8_unicode_ci DEFAULT NULL,
  `zip` varchar(5) COLLATE utf8_unicode_ci DEFAULT NULL,
  `address_1` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `address_2` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_addresses_when_created` (`when_created`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `companies`
--

DROP TABLE IF EXISTS `companies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `companies` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `name` varchar(32) COLLATE utf8_unicode_ci DEFAULT NULL,
  `tax_id_1` varchar(3) COLLATE utf8_unicode_ci DEFAULT NULL,
  `tax_id_2` varchar(2) COLLATE utf8_unicode_ci DEFAULT NULL,
  `tax_id_3` varchar(5) COLLATE utf8_unicode_ci DEFAULT NULL,
  `phone` varchar(13) COLLATE utf8_unicode_ci DEFAULT NULL,
  `address_id` int DEFAULT NULL,
  `bank_id` varchar(2) COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `address_id` (`address_id`),
  KEY `ix_companies_when_created` (`when_created`),
  CONSTRAINT `companies_ibfk_1` FOREIGN KEY (`address_id`) REFERENCES `addresses` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `countries`
--

DROP TABLE IF EXISTS `countries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `countries` (
  `id` varchar(2) COLLATE utf8_unicode_ci NOT NULL,
  `name` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `sort_order` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `currencies`
--

DROP TABLE IF EXISTS `currencies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `currencies` (
  `code` varchar(3) COLLATE utf8_unicode_ci NOT NULL,
  `name` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `rate` decimal(7,5) DEFAULT NULL,
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dhl_countries`
--

DROP TABLE IF EXISTS `dhl_countries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dhl_countries` (
  `zone` int DEFAULT NULL,
  `country_id` varchar(2) COLLATE utf8_unicode_ci DEFAULT NULL,
  KEY `country_id` (`country_id`),
  KEY `zone` (`zone`),
  CONSTRAINT `dhl_countries_ibfk_1` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`),
  CONSTRAINT `dhl_countries_ibfk_2` FOREIGN KEY (`zone`) REFERENCES `dhl_zones` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dhl_rates`
--

DROP TABLE IF EXISTS `dhl_rates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dhl_rates` (
  `zone` int DEFAULT NULL,
  `weight` float DEFAULT NULL,
  `rate` float DEFAULT NULL,
  KEY `zone` (`zone`),
  CONSTRAINT `dhl_rates_ibfk_1` FOREIGN KEY (`zone`) REFERENCES `dhl_zones` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dhl_zones`
--

DROP TABLE IF EXISTS `dhl_zones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dhl_zones` (
  `id` int NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invoice_items`
--

DROP TABLE IF EXISTS `invoice_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoice_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `invoice_id` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  `product_id` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  `price` decimal(8,2) DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `invoice_id` (`invoice_id`),
  KEY `product_id` (`product_id`),
  KEY `ix_invoice_items_when_created` (`when_created`),
  CONSTRAINT `invoice_items_ibfk_1` FOREIGN KEY (`invoice_id`) REFERENCES `invoices` (`id`),
  CONSTRAINT `invoice_items_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=77 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invoices`
--

DROP TABLE IF EXISTS `invoices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoices` (
  `id` varchar(16) COLLATE utf8_unicode_ci NOT NULL,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `seq_num` int DEFAULT NULL,
  `customer` varchar(128) COLLATE utf8_unicode_ci DEFAULT NULL,
  `address` varchar(256) COLLATE utf8_unicode_ci DEFAULT NULL,
  `country_id` int DEFAULT NULL,
  `phone` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_invoices_when_created` (`when_created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `order_product_status_history`
--

DROP TABLE IF EXISTS `order_product_status_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_product_status_history` (
  `order_product_id` int NOT NULL,
  `when_created` datetime NOT NULL,
  `status` enum('pending','po_created','unavailable','purchased','shipped','complete','cancelled') COLLATE utf8_unicode_ci DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`order_product_id`,`when_created`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `order_product_status_history_ibfk_1` FOREIGN KEY (`order_product_id`) REFERENCES `order_products` (`id`),
  CONSTRAINT `order_product_status_history_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `order_products`
--

DROP TABLE IF EXISTS `order_products`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_products` (
  `id` int NOT NULL AUTO_INCREMENT,
  `product_id` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  `status` set('pending','po_created','unavailable','purchased','shipped') COLLATE utf8_unicode_ci DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `private_comment` varchar(256) COLLATE utf8_unicode_ci DEFAULT NULL,
  `public_comment` varchar(256) COLLATE utf8_unicode_ci DEFAULT NULL,
  `price` int DEFAULT NULL,
  `order_id` varchar(16) CHARACTER SET utf8 COLLATE utf8_unicode_ci DEFAULT NULL,
  `suborder_id` varchar(20) COLLATE utf8_unicode_ci NOT NULL,
  `when_created` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`),
  KEY `order_products_ibfk_1` (`order_id`),
  KEY `ix_order_products_when_created` (`when_created`),
  KEY `order_products_ibfk_3` (`suborder_id`),
  CONSTRAINT `order_products_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `order_products_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
  CONSTRAINT `order_products_ibfk_3` FOREIGN KEY (`suborder_id`) REFERENCES `suborders` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=593 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `orders`
--

DROP TABLE IF EXISTS `orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders` (
  `id` varchar(16) COLLATE utf8_unicode_ci NOT NULL,
  `customer_name` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `address` varchar(256) COLLATE utf8_unicode_ci DEFAULT NULL,
  `country_id` varchar(2) COLLATE utf8_unicode_ci DEFAULT NULL,
  `phone` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `comment` varchar(128) COLLATE utf8_unicode_ci DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `when_created` datetime DEFAULT NULL,
  `invoice_id` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  `shipping_box_weight` int DEFAULT NULL,
  `shipping_krw` int DEFAULT NULL,
  `shipping_rur` decimal(10,2) DEFAULT NULL,
  `shipping_usd` decimal(10,2) DEFAULT NULL,
  `subtotal_krw` int DEFAULT NULL,
  `subtotal_rur` decimal(10,2) DEFAULT NULL,
  `subtotal_usd` decimal(10,2) DEFAULT NULL,
  `total_krw` int DEFAULT NULL,
  `total_rur` decimal(10,2) DEFAULT NULL,
  `total_usd` decimal(10,2) DEFAULT NULL,
  `total_weight` int DEFAULT NULL,
  `seq_num` int DEFAULT NULL,
  `shipping_method_id` int DEFAULT NULL,
  `status` enum('pending','can_be_paid','po_created','paid','shipped','complete') COLLATE utf8_unicode_ci DEFAULT NULL,
  `tracking_id` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `tracking_url` varchar(256) COLLATE utf8_unicode_ci DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `purchase_date` datetime DEFAULT NULL,
  `purchase_date_sort` datetime NOT NULL DEFAULT '9999-12-31 00:00:00',
  `attached_order_id` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  `payment_method_id` int DEFAULT NULL,
  `transaction_id` int DEFAULT NULL,
  `zip` varchar(10) COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `invoice_id` (`invoice_id`),
  KEY `shipping_method_id` (`shipping_method_id`),
  KEY `country_id` (`country_id`),
  KEY `ix_orders_purchase_date_sort` (`purchase_date_sort`),
  KEY `attached_order_id` (`attached_order_id`),
  KEY `payment_method_id` (`payment_method_id`),
  KEY `transaction_id` (`transaction_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `orders_ibfk_2` FOREIGN KEY (`invoice_id`) REFERENCES `invoices` (`id`),
  CONSTRAINT `orders_ibfk_3` FOREIGN KEY (`shipping_method_id`) REFERENCES `shipping` (`id`),
  CONSTRAINT `orders_ibfk_4` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`),
  CONSTRAINT `orders_ibfk_5` FOREIGN KEY (`attached_order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `orders_ibfk_6` FOREIGN KEY (`payment_method_id`) REFERENCES `payment_methods` (`id`),
  CONSTRAINT `orders_ibfk_7` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payment_methods`
--

DROP TABLE IF EXISTS `payment_methods`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payment_methods` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `name` varchar(32) COLLATE utf8_unicode_ci DEFAULT NULL,
  `payee_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_payment_methods_when_created` (`when_created`),
  KEY `payee_id` (`payee_id`),
  CONSTRAINT `payment_methods_ibfk_1` FOREIGN KEY (`payee_id`) REFERENCES `companies` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payments`
--

DROP TABLE IF EXISTS `payments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `currency_code` varchar(3) COLLATE utf8_unicode_ci DEFAULT NULL,
  `amount_sent_original` decimal(10,0) DEFAULT NULL,
  `amount_sent_krw` int DEFAULT NULL,
  `amount_received_krw` int DEFAULT NULL,
  `payment_method_id` int DEFAULT NULL,
  `evidence_image` varchar(256) COLLATE utf8_unicode_ci DEFAULT NULL,
  `status` enum('pending','approved','rejected','cancelled') COLLATE utf8_unicode_ci DEFAULT NULL,
  `transaction_id` int DEFAULT NULL,
  `changed_by_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `changed_by_id` (`changed_by_id`),
  KEY `currency_code` (`currency_code`),
  KEY `payment_method_id` (`payment_method_id`),
  KEY `transaction_id` (`transaction_id`),
  KEY `user_id` (`user_id`),
  KEY `ix_payments_when_created` (`when_created`),
  CONSTRAINT `payments_ibfk_1` FOREIGN KEY (`changed_by_id`) REFERENCES `users` (`id`),
  CONSTRAINT `payments_ibfk_2` FOREIGN KEY (`currency_code`) REFERENCES `currencies` (`code`),
  CONSTRAINT `payments_ibfk_3` FOREIGN KEY (`payment_method_id`) REFERENCES `payment_methods` (`id`),
  CONSTRAINT `payments_ibfk_4` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`),
  CONSTRAINT `payments_ibfk_5` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payments_orders`
--

DROP TABLE IF EXISTS `payments_orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payments_orders` (
  `payment_id` int DEFAULT NULL,
  `order_id` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  KEY `order_id` (`order_id`),
  KEY `payment_id` (`payment_id`),
  CONSTRAINT `payments_orders_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `payments_orders_ibfk_2` FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `products`
--

DROP TABLE IF EXISTS `products`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products` (
  `id` varchar(16) COLLATE utf8_unicode_ci NOT NULL,
  `name_english` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `name_russian` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `weight` int DEFAULT NULL,
  `price` int DEFAULT NULL,
  `points` int DEFAULT NULL,
  `category` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `name` varchar(256) COLLATE utf8_unicode_ci DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `when_created` datetime DEFAULT NULL,
  `available` tinyint(1) DEFAULT NULL,
  `synchronize` tinyint(1) DEFAULT NULL,
  `separate_shipping` tinyint(1) DEFAULT NULL,
  `purchase` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_products_name_english` (`name_english`),
  KEY `ix_products_name_russian` (`name_russian`),
  KEY `ix_products_name` (`name`),
  KEY `ix_products_when_created` (`when_created`),
  CONSTRAINT `products_chk_1` CHECK ((`available` in (0,1))),
  CONSTRAINT `products_chk_2` CHECK ((`synchronize` in (0,1))),
  CONSTRAINT `products_chk_3` CHECK ((`separate_shipping` in (0,1))),
  CONSTRAINT `products_chk_4` CHECK ((`purchase` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `purchase_orders`
--

DROP TABLE IF EXISTS `purchase_orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `purchase_orders` (
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `id` varchar(23) COLLATE utf8_unicode_ci NOT NULL,
  `suborder_id` varchar(20) COLLATE utf8_unicode_ci NOT NULL,
  `customer_id` int DEFAULT NULL,
  `contact_phone` varchar(13) COLLATE utf8_unicode_ci DEFAULT NULL,
  `payment_phone` varchar(13) COLLATE utf8_unicode_ci DEFAULT NULL,
  `payment_account` varchar(32) COLLATE utf8_unicode_ci DEFAULT NULL,
  `status` enum('pending','partially_posted','posted','paid','payment_past_due','shipped','delivered','failed','cancelled') COLLATE utf8_unicode_ci DEFAULT NULL,
  `zip` varchar(5) COLLATE utf8_unicode_ci DEFAULT NULL,
  `address_1` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `address_2` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  `company_id` int DEFAULT NULL,
  `status_details` text COLLATE utf8_unicode_ci,
  `vendor_po_id` varchar(12) COLLATE utf8_unicode_ci DEFAULT NULL,
  `vendor` varchar(64) COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `customer_id` (`customer_id`),
  KEY `ix_purchase_orders_when_created` (`when_created`),
  KEY `company_id` (`company_id`),
  KEY `purchase_orders_ibfk_2` (`suborder_id`),
  CONSTRAINT `purchase_orders_ibfk_1` FOREIGN KEY (`customer_id`) REFERENCES `subcustomers` (`id`),
  CONSTRAINT `purchase_orders_ibfk_2` FOREIGN KEY (`suborder_id`) REFERENCES `suborders` (`id`),
  CONSTRAINT `purchase_orders_ibfk_3` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `name` varchar(32) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `ix_roles_when_created` (`when_created`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `roles_users`
--

DROP TABLE IF EXISTS `roles_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles_users` (
  `user_id` int DEFAULT NULL,
  `role_id` int DEFAULT NULL,
  KEY `role_id` (`role_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `roles_users_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`),
  CONSTRAINT `roles_users_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `shipping`
--

DROP TABLE IF EXISTS `shipping`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `shipping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `name` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  `discriminator` varchar(50) COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_shipping_when_created` (`when_created`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `shipping_rates`
--

DROP TABLE IF EXISTS `shipping_rates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `shipping_rates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `destination` varchar(2) COLLATE utf8_unicode_ci DEFAULT NULL,
  `weight` int DEFAULT NULL,
  `rate` int DEFAULT NULL,
  `shipping_method_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_shipping_rates_weight` (`weight`),
  KEY `shipping_method_id` (`shipping_method_id`),
  KEY `shipping_rates_ibfk_2` (`destination`),
  CONSTRAINT `shipping_rates_ibfk_1` FOREIGN KEY (`shipping_method_id`) REFERENCES `shipping` (`id`),
  CONSTRAINT `shipping_rates_ibfk_2` FOREIGN KEY (`destination`) REFERENCES `countries` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2310 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `subcustomers`
--

DROP TABLE IF EXISTS `subcustomers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `subcustomers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `name` varchar(128) COLLATE utf8_unicode_ci DEFAULT NULL,
  `username` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  `password` varchar(16) COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_subcustomers_when_created` (`when_created`)
) ENGINE=InnoDB AUTO_INCREMENT=161 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `suborders`
--

DROP TABLE IF EXISTS `suborders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `suborders` (
  `id` varchar(20) COLLATE utf8_unicode_ci NOT NULL,
  `when_created` datetime DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `subcustomer_id` int DEFAULT NULL,
  `order_id` varchar(16) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `buyout_date` datetime DEFAULT NULL,
  `local_shipping` int DEFAULT NULL,
  `seq_num` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `order_id` (`order_id`),
  KEY `subcustomer_id` (`subcustomer_id`),
  KEY `ix_suborders_buyout_date` (`buyout_date`),
  KEY `ix_suborders_when_created` (`when_created`),
  CONSTRAINT `suborders_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `suborders_ibfk_2` FOREIGN KEY (`subcustomer_id`) REFERENCES `subcustomers` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `transactions`
--

DROP TABLE IF EXISTS `transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `when_created` datetime DEFAULT NULL,
  `amount` int DEFAULT NULL,
  `customer_id` int DEFAULT NULL,
  `customer_balance` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_transactions_when_created` (`when_created`),
  KEY `customer_id` (`customer_id`),
  CONSTRAINT `transactions_ibfk_3` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `transactions_ibfk_4` FOREIGN KEY (`customer_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=34 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(32) COLLATE utf8_unicode_ci NOT NULL,
  `email` varchar(80) CHARACTER SET utf8 COLLATE utf8_unicode_ci DEFAULT NULL,
  `password_hash` varchar(200) CHARACTER SET utf8 COLLATE utf8_unicode_ci DEFAULT NULL,
  `when_changed` datetime DEFAULT NULL,
  `when_created` datetime DEFAULT NULL,
  `balance` int DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  CONSTRAINT `users_chk_1` CHECK ((`enabled` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2021-01-19 17:19:43
