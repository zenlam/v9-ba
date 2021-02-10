# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015 Pexego All Rights Reserved
#    $Jesús Ventosinos Mayor <jesus@pexego.es>$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Inventory Gain & Loss Report',
    'version': '1.0',
    'category': 'stock',
    'description': '''''',
    'author': 'Onnet',
    'website': '',
    'depends': ['stock', 'br_multi_outlet', 'baskin_stock_flush'],
    'data': [
        'wizard/stock_inventory_wizard_view.xml',
        'wizard/stock_inventory_wizard_first_view.xml',
        'wizard/stock_inventory_wizard_second_view.xml',
        'wizard/stock_inventory_damage_wizard_view.xml',
        'wizard/stock_inventory_wizard_damage_first_view.xml',
        'wizard/stock_inventory_damage_wizard_second_view.xml',
        'views/stock_view.xml'
    ],
    'installable': True
}
