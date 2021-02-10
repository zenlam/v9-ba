-- DELETE DATA IN TABLES
-- DELETE  FROM account_analytic_line;
-- DELETE FROM account_move_line;
-- delete from account_move_line_account_tax_rel; -- auto delete with constraint
-- DELETE FROM account_move;


DELETE FROM account_bank_statement_line;
DELETE FROM account_bank_statement;

-- delete from account_invoice_line_tax; -- auto delete with constraint
-- DELETE FROM account_invoice_line;
--DELETE FROM sale_order_line_invoice_rel;
--DELETE FROM account_invoice;
--DELETE FROM account_payment;

DELETE FROM stock_pack_operation_lot;
DELETE FROM stock_pack_operation;
delete from account_move_line_stock_quant_rel;
delete from stock_return_picking_line;
DELETE FROM stock_move;
DELETE FROM stock_quant;
DELETE FROM stock_picking;
delete from stock_quant_move_rel;
delete from stock_move_operation_link;
delete from stock_quant_move_rel;
delete from stock_location_route_move;
delete from stock_backorder_confirmation;
delete from stock_immediate_transfer;
DELETE FROM product_price_history;
DELETE FROM stock_inventory_line;
DELETE FROM stock_inventory;
DELETE FROM stock_picking_to_wave;
DELETE FROM stock_picking_wave;
DELETE FROM stock_landed_cost;
DELETE FROM stock_quant_package;


-- DELETE FROM procurement_order; --------Ask YS as can't drop all as we keep some move_line need to clean only
-- DELETE FROM sale_order_line;
-- DELETE FROM sale_order;

DELETE FROM crm_lead;
DELETE FROM crm_activity;

--DELETE FROM purchase_requisition_line;
--DELETE FROM purchase_requisition;
--DELETE FROM purchase_order_line;
--DELETE FROM purchase_order;

DELETE FROM pos_order_line;
delete from pos_order_line_promotion_default_rel;
Delete from  account_tax_pos_order_line_rel;
delete from br_config_voucher_pos_order_rel;
delete from account_tax_br_pos_order_line_master_rel;
delete from br_confirm_refund_wizard;
DELETE FROM br_pos_order_line_master;
DELETE FROM pos_order;
DELETE FROM pos_session;
delete from pos_session_cash_in;
