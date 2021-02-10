# -*- coding: utf-8 -*-

import os

import base64
from openerp import api, fields, models


class WizardGSTReport(models.TransientModel):
    _name = 'wizard.gst.report'

    start_date = fields.Date(
                    'Start Date',
                    required=True,
                    default=fields.Date.context_today)
    end_date = fields.Date(
                    'End Date',
                    required=True,
                    default=fields.Date.context_today)

    def _create_file(self, gst, result):
        GSTTaxMapping = self.env['gst.tax.mapping']
        seq_lst = []
        mappings = GSTTaxMapping.search([])
        gst_maps = mappings.filtered(lambda r: r.is_tap_file == 'yes' or r.is_msic)
        sequence_lst = gst_maps.filtered(lambda r: r.sequence > 0).mapped('sequence')
        seq_lst += sequence_lst
        val_sequence_lst = gst_maps.filtered(lambda r: r.value_sequence > 0).mapped('value_sequence')
        seq_lst += val_sequence_lst
        min_seq = 0
        max_seq = 0
        if seq_lst:
            min_seq = min(seq_lst)
            max_seq = max(seq_lst)
        for key in result:
            print key, type(key)
        text = ''
        if min_seq > 0 and max_seq > 0:
            for i in range(min_seq, max_seq + 1, 1):
                if result.get(i) and i == min_seq:
                    text += str(result[i])
                elif result.get(i):
                    text += '|' + str(result[i])
                else:
                    text += '|' + '0'
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_name = dir_path + '/file.txt'
        f = open(file_name, 'w')
        f.write(text)
        f.close()
        f = open(file_name, 'r')
        data = f.read()
        return data

    @api.multi
    def action_print(self):
        self.ensure_one()
        GSTTaxMapping = self.env['gst.tax.mapping']
        AccountGST = self.env['account.gst']
        AccountGSTLine = self.env['account.gst.line']
        AccountTax = self.env['account.tax']
        result = {}
        mapping_result = {}

        account_gst = AccountGST.create({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'print_date': fields.Datetime.now(),
        })

        gst_tax_maps = GSTTaxMapping.search([])
        for gst_tax in gst_tax_maps:
            print "gst_tax;:::::", gst_tax.name, gst_tax.name.name
            amount_total = 0.0
            taxes = gst_tax.mapped('taxes_ids')
            if not gst_tax.is_formula and not gst_tax.is_msic and not gst_tax.is_carry_forward_refund:
                if gst_tax.is_base and gst_tax.tax_type == 'input':
                    self.env.cr.execute("""
                        SELECT
                            CASE WHEN aml.tax_line_id IS NULL AND aml_atr.account_tax_id in %s THEN
                                COALESCE(SUM(aml.debit), 0.0) - COALESCE(SUM(aml.credit), 0.0)
                            ELSE 0 END AS amount
                        FROM account_move_line aml
                        LEFT JOIN account_move_line_account_tax_rel aml_atr on (aml_atr.account_move_line_id = aml.id)
                        where aml.date >= %s and aml.date <= %s AND aml_atr.account_tax_id in %s
                        GROUP BY aml.tax_line_id, aml_atr.account_tax_id""", (
                            tuple(taxes.ids), self.start_date, self.end_date, tuple(taxes.ids),))
                elif gst_tax.is_base and gst_tax.tax_type == 'output':
                    self.env.cr.execute("""
                        SELECT
                            CASE WHEN aml.tax_line_id IS NULL AND aml_atr.account_tax_id in %s THEN
                                COALESCE(SUM(aml.credit), 0.0) - COALESCE(SUM(aml.debit), 0.0)
                            ELSE 0 END AS amount
                        FROM account_move_line aml
                        LEFT JOIN account_move_line_account_tax_rel aml_atr on (aml_atr.account_move_line_id = aml.id)
                        where aml.date >= %s and aml.date <= %s AND aml_atr.account_tax_id in %s
                        GROUP BY aml.tax_line_id, aml_atr.account_tax_id""", (
                            tuple(taxes.ids), self.start_date, self.end_date, tuple(taxes.ids),))
                elif gst_tax.is_base == 0 and gst_tax.tax_type == 'input':
                    self.env.cr.execute("""
                        SELECT
                            COALESCE(SUM(aml.debit), 0.0) - COALESCE(SUM(aml.credit), 0.0)
                        FROM account_move_line aml
                        where aml.date >= %s and aml.date <= %s AND aml.tax_line_id in %s""", (self.start_date, self.end_date, tuple(taxes.ids),))
                else:
                    self.env.cr.execute("""
                        SELECT
                            COALESCE(SUM(aml.credit), 0.0) - COALESCE(SUM(aml.debit), 0.0)
                        FROM account_move_line aml
                        where aml.date >= %s and aml.date <= %s AND aml.tax_line_id in %s""", (self.start_date, self.end_date, tuple(taxes.ids),))
                res = self.env.cr.fetchall()
                total = 0.0
                for rec in res:
                    if rec[0] > 0.0:
                        total += rec[0]
                if total > 0.0:
                    AccountGSTLine.create({
                        'amount': total,
                        'name': gst_tax.name.id,
                        'account_gst_id': account_gst.id,
                    })
                mapping_result.update({
                    gst_tax.name.name: total
                })

                result.update({
                    gst_tax.sequence: total
                })
                if gst_tax.is_msic:
                    result.update({
                        gst_tax.value_sequence: gst_tax.msic_code
                    })
                    if gst_tax.data_gst_mapping_id:
                        result.update({
                            gst_tax.sequence: mapping_result[gst_tax.data_gst_mapping_id.name]
                        })
            elif gst_tax.is_carry_forward_refund:
                total = 0
                result.update({
                    gst_tax.sequence: 0
                })
                if gst_tax.carry_forward_refund == 'yes':
                    result.update({
                        gst_tax.sequence: 1
                    })
                    total = 1
                AccountGSTLine.create({
                    'amount': total,
                    'name': gst_tax.name.id,
                    'account_gst_id': account_gst.id,
                })
            else:
                if gst_tax.is_formula:
                    from_total = 0.0
                    to_total = 0.0
                    for line in gst_tax.from_gst_mapping_ids:
                        gst_map = GSTTaxMapping.search([('name', '=', line.id)])
                        taxes = gst_map.mapped('taxes_ids')
                        if gst_map.is_base and gst_tax.tax_type == 'input':
                            self.env.cr.execute("""
                                SELECT
                                    CASE WHEN aml.tax_line_id IS NULL AND aml_atr.account_tax_id in %s THEN
                                        COALESCE(SUM(aml.debit), 0.0) - COALESCE(SUM(aml.credit), 0.0)
                                    ELSE 0 END AS amount
                                FROM account_move_line aml
                                LEFT JOIN account_move_line_account_tax_rel aml_atr on (aml_atr.account_move_line_id = aml.id)
                                where aml.date >= %s and aml.date <= %s AND aml_atr.account_tax_id in %s
                                GROUP BY aml.tax_line_id, aml_atr.account_tax_id""", (
                                tuple(taxes.ids), self.start_date, self.end_date, tuple(taxes.ids),))
                        elif gst_map.is_base and gst_tax.tax_type == 'output':
                            self.env.cr.execute("""
                                SELECT
                                    CASE WHEN aml.tax_line_id IS NULL AND aml_atr.account_tax_id in %s THEN
                                        COALESCE(SUM(aml.credit), 0.0) - COALESCE(SUM(aml.debit), 0.0)
                                    ELSE 0 END AS amount
                                FROM account_move_line aml
                                LEFT JOIN account_move_line_account_tax_rel aml_atr on (aml_atr.account_move_line_id = aml.id)
                                where aml.date >= %s and aml.date <= %s AND aml_atr.account_tax_id in %s
                                GROUP BY aml.tax_line_id, aml_atr.account_tax_id""", (
                                tuple(taxes.ids), self.start_date, self.end_date, tuple(taxes.ids),))
                        elif gst_map.is_base == 0 and gst_tax.tax_type == 'input':
                            self.env.cr.execute("""
                                SELECT
                                    COALESCE(SUM(aml.debit), 0.0) - COALESCE(SUM(aml.credit), 0.0)
                                FROM account_move_line aml
                                where aml.date >= %s and aml.date <= %s AND aml.tax_line_id in %s""",
                                                (self.start_date, self.end_date, tuple(taxes.ids),))
                        else:
                            self.env.cr.execute("""
                                SELECT
                                    COALESCE(SUM(aml.credit), 0.0) - COALESCE(SUM(aml.debit), 0.0)
                                FROM account_move_line aml
                                where aml.date >= %s and aml.date <= %s AND aml.tax_line_id in %s""",
                                                (self.start_date, self.end_date, tuple(taxes.ids),))
                        res = self.env.cr.fetchall()
                        for rec in res:
                            from_total += rec[0]

                    for line in gst_tax.to_gst_mapping_ids:
                        gst_map = GSTTaxMapping.search([('name', '=', line.id)])
                        taxes = gst_map.mapped('taxes_ids')
                        if gst_map.is_base and gst_tax.tax_type == 'input':
                            self.env.cr.execute("""
                                SELECT
                                    CASE WHEN aml.tax_line_id IS NULL AND aml_atr.account_tax_id in %s THEN
                                        COALESCE(SUM(aml.debit), 0.0) - COALESCE(SUM(aml.credit), 0.0)
                                    ELSE 0 END AS amount
                                FROM account_move_line aml
                                LEFT JOIN account_move_line_account_tax_rel aml_atr on (aml_atr.account_move_line_id = aml.id)
                                where aml.date >= %s and aml.date <= %s AND aml_atr.account_tax_id in %s
                                GROUP BY aml.tax_line_id, aml_atr.account_tax_id""", (
                                tuple(taxes.ids), self.start_date, self.end_date, tuple(taxes.ids),))
                        elif gst_map.is_base and gst_tax.tax_type == 'output':
                            self.env.cr.execute("""
                                SELECT
                                    CASE WHEN aml.tax_line_id IS NULL AND aml_atr.account_tax_id in %s THEN
                                        COALESCE(SUM(aml.credit), 0.0) - COALESCE(SUM(aml.debit), 0.0)
                                    ELSE 0 END AS amount
                                FROM account_move_line aml
                                LEFT JOIN account_move_line_account_tax_rel aml_atr on (aml_atr.account_move_line_id = aml.id)
                                where aml.date >= %s and aml.date <= %s AND aml_atr.account_tax_id in %s
                                GROUP BY aml.tax_line_id, aml_atr.account_tax_id""", (
                                tuple(taxes.ids), self.start_date, self.end_date, tuple(taxes.ids),))
                        elif gst_map.is_base == 0 and gst_tax.tax_type == 'input':
                            self.env.cr.execute("""
                                SELECT
                                    COALESCE(SUM(aml.debit), 0.0) - COALESCE(SUM(aml.credit), 0.0)
                                FROM account_move_line aml
                                where aml.date >= %s and aml.date <= %s AND aml.tax_line_id in %s""",
                                                (self.start_date, self.end_date, tuple(taxes.ids),))
                        else:
                            self.env.cr.execute("""
                                SELECT
                                    COALESCE(SUM(aml.credit), 0.0) - COALESCE(SUM(aml.debit), 0.0)
                                FROM account_move_line aml
                                where aml.date >= %s and aml.date <= %s AND aml.tax_line_id in %s""",
                                                (self.start_date, self.end_date, tuple(taxes.ids),))

                            res = self.env.cr.fetchall()
                            for rec in res:
                                to_total += rec[0]
                    if gst_tax.operator == '-':
                        amount_total = from_total - to_total
                        if amount_total <= 0:
                            amount_total = 0
                    elif gst_tax.operator == '*':
                        amount_total = from_total * to_total
                    elif gst_tax.operator == '+':
                        amount_total = from_total + to_total
                    elif gst_tax.operator == '/':
                        amount_total = from_total / to_total
                    AccountGSTLine.create({
                        'amount': amount_total,
                        'name': gst_tax.name.id,
                        'account_gst_id': account_gst.id,
                    })
                    mapping_result.update({
                        gst_tax.name.name: amount_total
                    })
                    result.update({
                        gst_tax.sequence: amount_total
                    })
                elif gst_tax.is_msic:
                    result.update({
                        gst_tax.value_sequence: gst_tax.msic_code
                    })
                    if gst_tax.data_gst_mapping_id:
                        result.update({
                            gst_tax.sequence: mapping_result[gst_tax.data_gst_mapping_id.name]
                        })
        data = base64.encodestring(self._create_file(account_gst, result))
        account_gst.write({
            'filename': 'GST.txt',
            'file': data
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'GST DATA',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.gst',
            'domain': [('id', '=', account_gst.id)]
        }
