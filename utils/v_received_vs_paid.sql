ALTER VIEW v_received_vs_paid AS
SELECT
   `p_aggr`.`date` AS `date`,
   `c`.`name` AS `name`,
   `p_aggr`.`amount_received` AS `amount_received`,
   `po_aggr`.`amount_paid` AS `amount_paid`
FROM 
	`companies` AS `c` 
	JOIN 
		(
			SELECT 
				CAST(CONVERT_TZ(`p`.`when_created`, '+01:00', '+09:00') as date) AS `date`,
				`pm`.`payee_id` AS `payee_id`,
				SUM(`p`.`amount_received_krw`) AS `amount_received`
			FROM 
				`payments` AS `p` 
				JOIN `payment_methods` `pm` ON `p`.`payment_method_id` = `pm`.`id` 
			WHERE `p`.`status` IN ('pending','approved')
			GROUP BY `pm`.`payee_id`, CAST(CONVERT_TZ(`p`.`when_created`, '+01:00', '+09:00') AS DATE)
		) AS `p_aggr` ON `c`.`id` = `p_aggr`.`payee_id` 
	LEFT JOIN 
		(
			SELECT 
				CAST(CONVERT_TZ(po.`when_created`, '+01:00', '+09:00') AS DATE) AS `date`,
				`po`.`company_id` AS `company_id`,
				SUM((`op`.`price` * `op`.`quantity`)) AS `amount_paid` 
			FROM 
				`purchase_orders` AS `po` 
				JOIN `order_products` `op` ON `po`.`suborder_id` = `op`.`suborder_id` 
			WHERE `po`.`status` not in ('failed','cancelled')
			GROUP BY CAST(CONVERT_TZ(po.`when_created`, '+01:00', '+09:00') AS DATE), `po`.`company_id`
		) AS`po_aggr` ON `p_aggr`.`date` = `po_aggr`.`date` AND `p_aggr`.`payee_id` = `po_aggr`.`company_id` 
		
UNION ALL 

SELECT 
	`po_aggr`.`date` AS `date`,
	`c`.`name` AS `name`,
	 `p_aggr`.`amount_received` AS `amount_received`,
	 `po_aggr`.`amount_paid` AS `amount_paid` 
FROM
	`companies` AS `c` 
	 JOIN 
	 	(
	 		SELECT 
	 			CAST(CONVERT_TZ(po.`when_created`, '+01:00', '+09:00') AS DATE) AS `date`,
	 			`po`.`company_id` AS `company_id`,
	 			SUM(`op`.`price` * `op`.`quantity`) AS `amount_paid` 
	 		FROM 
	 			`purchase_orders` `po` 
	 			JOIN `order_products` `op` ON `po`.`suborder_id` = `op`.`suborder_id` 
	 		WHERE `po`.`status` NOT IN ('failed','cancelled')
	 		GROUP BY CAST(CONVERT_TZ(po.`when_created`, '+01:00', '+09:00') AS DATE), `po`.`company_id`
	 	) AS `po_aggr` ON `c`.`id` = `po_aggr`.`company_id`
	 LEFT JOIN 
	 	(
	 		SELECT 
	 			CAST(CONVERT_TZ(`p`.`when_created`, '+01:00', '+09:00') AS DATE) AS `date`,
	 			`pm`.`payee_id` AS `payee_id`,
	 			SUM(`p`.`amount_received_krw`) AS `amount_received` 
	 		FROM 
	 			`payments` AS `p` 
	 			JOIN `payment_methods` AS `pm` ON `p`.`payment_method_id` = `pm`.`id`
	 		WHERE `p`.`status` in ('pending','approved') 
	 		GROUP BY `pm`.`payee_id`, CAST(CONVERT_TZ(`p`.`when_created`, '+01:00', '+09:00') AS DATE)
	 	) AS `p_aggr` ON `p_aggr`.`date` = `po_aggr`.`date` AND `p_aggr`.`payee_id` = `po_aggr`.`company_id` 
WHERE `p_aggr`.`amount_received` IS NULL