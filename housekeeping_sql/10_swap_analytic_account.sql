
-- from Chin Hwa

1. SWAP JOURNAL ITEM'S ANALYTIC ACCOUNT
--------------------------------------------------------------------------
UPDATE account_move_line
SET analytic_account_id = account_analytic_default.analytic_id
FROM account_analytic_default
WHERE account_move_line.partner_id = account_analytic_default.partner_id;

2. SWAP ANALYTIC ENTRIES' ANALYTIC ACCOUNT
--------------------------------------------------------------------------
UPDATE account_analytic_line
SET account_id = account_analytic_default.analytic_id
FROM account_analytic_default, account_move_line
WHERE account_analytic_default.partner_id = account_move_line.partner_id
AND account_move_line.id = account_analytic_line.move_id;

3. SWAP PO LINES' ANALYTIC ACCOUNT
--------------------------------------------------------------------------
--UPDATE purchase_order_line 
--SET account_analytic_id = account_analytic_default.analytic_id
--FROM account_analytic_default
--WHERE purchase_order_line.partner_id = account_analytic_default.partner_id

4. SWAP SO'S ANALYTIC ACCOUNT
--------------------------------------------------------------------------
UPDATE sale_order
SET project_id = account_analytic_default.analytic_id
FROM account_analytic_default
WHERE sale_order.partner_id = account_analytic_default.partner_id

5. SWAP payment ANALYTIC ACCOUNT
--------------------------------------------------------------------------
UPDATE account_payment
SET account_analytic_id = account_analytic_default.analytic_id
FROM account_analytic_default
WHERE account_payment.partner_id = account_analytic_default.partner_id
 
