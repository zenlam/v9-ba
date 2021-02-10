-- Add CONSTRAINTS
ALTER TABLE public.account_move_line
    ADD CONSTRAINT account_move_line_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.account_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_move_line
    ADD CONSTRAINT account_move_line_account_id_fkey FOREIGN KEY (account_id)
    REFERENCES public.account_account (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_move_line
    ADD CONSTRAINT account_move_line_analytic_account_id_fkey FOREIGN KEY (analytic_account_id)
    REFERENCES public.account_analytic_account (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_move_line
    ADD CONSTRAINT account_move_line_tax_line_id_fkey FOREIGN KEY (tax_line_id)
    REFERENCES public.account_tax (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;


ALTER TABLE public.account_analytic_line
    ADD CONSTRAINT account_analytic_line_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.account_move_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_partial_reconcile
    ADD CONSTRAINT account_partial_reconcile_credit_move_id_fkey FOREIGN KEY (credit_move_id)
    REFERENCES public.account_move_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_invoice_account_move_line_rel
    ADD CONSTRAINT account_invoice_account_move_line_rel_account_move_line_id_fkey FOREIGN KEY (account_move_line_id)
    REFERENCES public.account_move_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_move_line_stock_quant_rel
    ADD CONSTRAINT account_move_line_stock_quant_rel_account_move_line_id_fkey FOREIGN KEY (account_move_line_id)
    REFERENCES public.account_move_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;



ALTER TABLE public.account_move_line_account_tax_rel
    ADD CONSTRAINT account_move_line_account_tax_rel_account_move_line_id_fkey FOREIGN KEY (account_move_line_id)
    REFERENCES public.account_move_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_partial_reconcile
    ADD CONSTRAINT account_partial_reconcile_debit_move_id_fkey FOREIGN KEY (debit_move_id)
    REFERENCES public.account_move_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.pos_order
  ADD CONSTRAINT pos_order_account_move_fkey FOREIGN KEY (account_move)
      REFERENCES public.account_move (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.account_invoice
    ADD CONSTRAINT account_invoice_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.account_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;


ALTER TABLE public.account_asset_depreciation_line
    ADD CONSTRAINT account_asset_depreciation_line_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.account_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_landed_cost
    ADD CONSTRAINT stock_landed_cost_account_move_id_fkey FOREIGN KEY (account_move_id)
    REFERENCES public.account_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_move
    ADD CONSTRAINT account_move_statement_line_id_fkey FOREIGN KEY (statement_line_id)
    REFERENCES public.account_bank_statement_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;



ALTER TABLE public.pos_session
    ADD CONSTRAINT pos_session_cash_register_id_fkey FOREIGN KEY (cash_register_id)
    REFERENCES public.account_bank_statement (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_account_id_fkey FOREIGN KEY (account_id)
    REFERENCES public.account_account (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_bank_account_id_fkey FOREIGN KEY (bank_account_id)
    REFERENCES public.res_partner_bank (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_cash_control_id_fkey FOREIGN KEY (cash_control_id)
    REFERENCES public.br_cash_control (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_credit_account_id_fkey FOREIGN KEY (credit_account_id)
    REFERENCES public.account_account (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_currency_id_fkey FOREIGN KEY (currency_id)
    REFERENCES public.res_currency (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_journal_id_fkey FOREIGN KEY (journal_id)
    REFERENCES public.account_journal (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_partner_id_fkey FOREIGN KEY (partner_id)
    REFERENCES public.res_partner (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_pos_statement_id_fkey FOREIGN KEY (pos_statement_id)
    REFERENCES public.pos_order (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_bank_statement_line
    ADD CONSTRAINT account_bank_statement_line_statement_id_fkey FOREIGN KEY (statement_id)
    REFERENCES public.account_bank_statement (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_invoice_line_tax
    ADD CONSTRAINT account_invoice_line_tax_invoice_line_id_fkey FOREIGN KEY (invoice_line_id)
    REFERENCES public.account_invoice_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.sale_order_line_invoice_rel
    ADD CONSTRAINT sale_order_line_invoice_rel_invoice_line_id_fkey FOREIGN KEY (invoice_line_id)
    REFERENCES public.account_invoice_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_move_line
  ADD CONSTRAINT account_move_line_invoice_id_fkey FOREIGN KEY (invoice_id)
      REFERENCES public.account_invoice (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.pos_order
  ADD CONSTRAINT pos_order_invoice_id_fkey FOREIGN KEY (invoice_id)
      REFERENCES public.account_invoice (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.stock_move_operation_link
    ADD CONSTRAINT stock_move_operation_link_operation_id_fkey FOREIGN KEY (operation_id)
    REFERENCES public.stock_pack_operation (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.stock_pack_operation_lot
    ADD CONSTRAINT stock_pack_operation_lot_operation_id_fkey FOREIGN KEY (operation_id)
    REFERENCES public.stock_pack_operation (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


aLTER TABLE public.account_move_line
    ADD CONSTRAINT account_move_line_stock_move_id_fkey FOREIGN KEY (stock_move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_move
    ADD CONSTRAINT stock_move_origin_returned_move_id_fkey FOREIGN KEY (origin_returned_move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;

ALTER TABLE public.stock_move
    ADD CONSTRAINT stock_move_split_from_fkey FOREIGN KEY (split_from)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_quant
    ADD CONSTRAINT stock_quant_negative_move_id_fkey FOREIGN KEY (negative_move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


aLTER TABLE public.stock_picking
    ADD CONSTRAINT stock_picking_picking_orig_id_fkey FOREIGN KEY (picking_orig_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.pos_order
    ADD CONSTRAINT pos_order_picking_id_fkey FOREIGN KEY (picking_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;



ALTER TABLE public.stock_move_operation_link
    ADD CONSTRAINT stock_move_operation_link_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;



ALTER TABLE public.procurement_order
    ADD CONSTRAINT procurement_order_move_dest_id_fkey FOREIGN KEY (move_dest_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;



ALTER TABLE public.stock_move
    ADD CONSTRAINT stock_move_move_dest_id_fkey FOREIGN KEY (move_dest_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;

ALTER TABLE public.stock_quant_move_rel
    ADD CONSTRAINT stock_quant_move_rel_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;



ALTER TABLE public.stock_return_picking_line
    ADD CONSTRAINT stock_return_picking_line_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_quant
    ADD CONSTRAINT stock_quant_reservation_id_fkey FOREIGN KEY (reservation_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_valuation_adjustment_lines
    ADD CONSTRAINT stock_valuation_adjustment_lines_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_location_route_move
    ADD CONSTRAINT stock_location_route_move_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.stock_move_operation_link
    ADD CONSTRAINT stock_move_operation_link_reserved_quant_id_fkey FOREIGN KEY (reserved_quant_id)
    REFERENCES public.stock_quant (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_quant_move_rel
    ADD CONSTRAINT stock_quant_move_rel_quant_id_fkey FOREIGN KEY (quant_id)
    REFERENCES public.stock_quant (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;



ALTER TABLE public.account_move_line_stock_quant_rel
    ADD CONSTRAINT account_move_line_stock_quant_rel_stock_quant_id_fkey FOREIGN KEY (stock_quant_id)
    REFERENCES public.stock_quant (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.stock_quant
    ADD CONSTRAINT stock_quant_propagated_from_id_fkey FOREIGN KEY (propagated_from_id)
    REFERENCES public.stock_quant (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;

ALTER TABLE public.stock_move
    ADD CONSTRAINT stock_move_picking_id_fkey FOREIGN KEY (picking_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;



ALTER TABLE public.stock_pack_operation
    ADD CONSTRAINT stock_pack_operation_picking_id_fkey FOREIGN KEY (picking_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_immediate_transfer
    ADD CONSTRAINT stock_immediate_transfer_pick_id_fkey FOREIGN KEY (pick_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;



ALTER TABLE public.stock_backorder_confirmation
    ADD CONSTRAINT stock_backorder_confirmation_pick_id_fkey FOREIGN KEY (pick_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;



ALTER TABLE public.stock_picking
    ADD CONSTRAINT stock_picking_backorder_id_fkey FOREIGN KEY (backorder_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_landed_cost_stock_picking_rel
    ADD CONSTRAINT stock_landed_cost_stock_picking_rel_stock_picking_id_fkey FOREIGN KEY (stock_picking_id)
    REFERENCES public.stock_picking (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;

ALTER TABLE public.stock_transfer_dispute_details
    ADD CONSTRAINT stock_transfer_dispute_details_move_id_fkey FOREIGN KEY (move_id)
    REFERENCES public.stock_move (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.stock_move
  ADD CONSTRAINT stock_move_inventory_line_id_fkey FOREIGN KEY (inventory_line_id)
      REFERENCES public.stock_inventory_line (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.stock_move
  ADD CONSTRAINT stock_move_inventory_id_fkey FOREIGN KEY (inventory_id)
      REFERENCES public.stock_inventory (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.stock_picking
  ADD CONSTRAINT stock_picking_wave_id_fkey FOREIGN KEY (wave_id)
      REFERENCES public.stock_picking_wave (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.stock_picking_to_wave
    ADD CONSTRAINT stock_picking_to_wave_wave_id_fkey FOREIGN KEY (wave_id)
    REFERENCES public.stock_picking_wave (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;

ALTER TABLE public.stock_pack_operation
  ADD CONSTRAINT stock_pack_operation_package_id_fkey FOREIGN KEY (package_id)
      REFERENCES public.stock_quant_package (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;

ALTER TABLE public.stock_pack_operation
  ADD CONSTRAINT stock_pack_operation_result_package_id_fkey FOREIGN KEY (result_package_id)
      REFERENCES public.stock_quant_package (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE;


ALTER TABLE public.stock_move
  ADD CONSTRAINT stock_move_procurement_id_fkey FOREIGN KEY (procurement_id)
      REFERENCES public.procurement_order (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.account_analytic_line
  ADD CONSTRAINT account_analytic_line_so_line_fkey FOREIGN KEY (so_line)
      REFERENCES public.sale_order_line (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.procurement_order
  ADD CONSTRAINT procurement_order_sale_line_id_fkey FOREIGN KEY (sale_line_id)
      REFERENCES public.sale_order_line (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.stock_move
  ADD CONSTRAINT stock_move_purchase_line_id_fkey FOREIGN KEY (purchase_line_id)
      REFERENCES public.purchase_order_line (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;

ALTER TABLE public.account_tax_pos_order_line_rel
    ADD CONSTRAINT account_tax_pos_order_line_rel_pos_order_line_id_fkey FOREIGN KEY (pos_order_line_id)
    REFERENCES public.pos_order_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;



ALTER TABLE public.pos_order_line_promotion_default_rel
    ADD CONSTRAINT pos_order_line_promotion_default_rel_pos_order_line_id_fkey FOREIGN KEY (pos_order_line_id)
    REFERENCES public.pos_order_line (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.pos_order_line
  ADD CONSTRAINT pos_order_line_master_id_fkey FOREIGN KEY (master_id)
      REFERENCES public.br_pos_order_line_master (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.br_pos_order_line_master
  ADD CONSTRAINT br_pos_order_line_master_order_id_fkey FOREIGN KEY (order_id)
      REFERENCES public.pos_order (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE;


ALTER TABLE public.pos_order_line
  ADD CONSTRAINT pos_order_line_order_id_fkey FOREIGN KEY (order_id)
      REFERENCES public.pos_order (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE;


ALTER TABLE public.pos_order
  ADD CONSTRAINT pos_order_parent_id_fkey FOREIGN KEY (parent_id)
      REFERENCES public.pos_order (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.account_tax_br_pos_order_line_master_rel
    ADD CONSTRAINT account_tax_br_pos_order_line__br_pos_order_line_master_id_fkey FOREIGN KEY (br_pos_order_line_master_id)
    REFERENCES public.br_pos_order_line_master (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;




ALTER TABLE public.br_confirm_refund_wizard
    ADD CONSTRAINT br_confirm_refund_wizard_pos_order_id_fkey FOREIGN KEY (pos_order_id)
    REFERENCES public.pos_order (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.br_config_voucher
    ADD CONSTRAINT br_config_voucher_order_id_fkey FOREIGN KEY (order_id)
    REFERENCES public.pos_order (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;


ALTER TABLE public.br_config_voucher_pos_order_rel
    ADD CONSTRAINT br_config_voucher_pos_order_rel_pos_order_id_fkey FOREIGN KEY (pos_order_id)
    REFERENCES public.pos_order (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE public.account_bank_statement
  ADD CONSTRAINT account_bank_statement_pos_session_id_fkey FOREIGN KEY (pos_session_id)
      REFERENCES public.pos_session (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL;


ALTER TABLE public.pos_session_cash_in
    ADD CONSTRAINT pos_session_cash_in_pos_session_id_fkey FOREIGN KEY (pos_session_id)
    REFERENCES public.pos_session (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;
