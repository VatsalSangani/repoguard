UPDATE orders
SET status = 'cancelled'
WHERE id IN (SELECT * FROM stale_order_ids);
