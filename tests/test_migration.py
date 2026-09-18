import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch
from test_reports import FakeFrappe, Row


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.frappe=FakeFrappe()
        self.frappe.tables={
            'Project Drawing':[Row(name='D1')],
            'Drawing Revision':[Row(name='REV0',drawing='D1')],
            'Drawing BOQ Item':[
                Row(name='CURRENT',parent='D1',parenttype='Project Drawing',item_code='STEEL',uom='Kg',discipline='Civil'),
                Row(name='HISTORY',parent='REV0',parenttype='Drawing Revision',item_code='STEEL',uom='Kg',discipline='Civil')],
            'Daily Progress Item':[Row(name='PI1',drawing='D1',boq_item='STEEL',uom='Kg',today_executed_qty=12)],
            'DPR Material Consumption':[],
            'Daily Progress Report':[],
        }
        def set_value(doctype,name,field,value=None,**kwargs):
            row=next(r for r in self.frappe.tables[doctype] if r.name==name)
            row.update(field if isinstance(field,dict) else {field:value})
        self.frappe.db.set_value=set_value
        self.frappe.db.exists=lambda doctype,name:any(r.name==name for r in self.frappe.tables.get(doctype,[]))
        setup=types.ModuleType('amp.setup');setup.install=Mock()
        boq=types.ModuleType('amp.amp.boq');boq.refresh_drawing=Mock()
        workspace=types.ModuleType('amp.amp.patches.v0_0_1.sync_workspace');workspace.execute=Mock()
        self.modules=patch.dict(sys.modules,{'frappe':self.frappe,'amp.setup':setup,'amp.amp.boq':boq,'amp.amp.patches.v0_0_1.sync_workspace':workspace})
        self.modules.start()
        self.module=importlib.reload(importlib.import_module('amp.amp.patches.v0_0_2.reporting_and_references'))

    def tearDown(self):
        self.modules.stop()

    def test_unique_history_is_linked_and_rerun_preserves_identity(self):
        self.module.execute()
        rows=self.frappe.tables['Drawing BOQ Item']
        identity=rows[0].boq_line_id
        self.assertTrue(identity)
        self.assertEqual(rows[1].boq_line_id,identity)
        self.assertEqual(self.frappe.tables['Daily Progress Item'][0].boq_line_id,identity)
        self.module.execute()
        self.assertEqual(rows[0].boq_line_id,identity)
        self.assertEqual(self.frappe.tables['Daily Progress Item'][0].today_executed_qty,12)
        self.assertEqual(rows[0].progress_weight,1)

    def test_repeated_item_progress_is_left_unallocated(self):
        self.frappe.tables['Drawing BOQ Item'].append(Row(name='OTHER',parent='D1',parenttype='Project Drawing',item_code='STEEL',uom='Kg',discipline='Structural'))
        self.module.execute()
        self.assertIsNone(self.frappe.tables['Daily Progress Item'][0].boq_line_id)
        self.assertEqual(self.frappe.tables['Daily Progress Item'][0].today_executed_qty,12)

    def test_stock_backfill_uses_explicit_dpr_link(self):
        self.frappe.tables['Daily Progress Report']=[Row(name='DPR1',stock_entry='SE1')]
        self.frappe.tables['DPR Material Consumption']=[Row(name='M1',parent='DPR1',drawing='D1',item_code='STEEL',uom='Kg')]
        self.frappe.tables['Stock Entry']=[Row(name='SE1')]
        self.frappe.tables['Stock Entry Detail']=[Row(name='S1',parent='SE1',item_code='STEEL',uom='Kg')]
        self.module.execute()
        self.assertEqual(self.frappe.tables['Stock Entry'][0].custom_daily_progress_report,'DPR1')
        row=self.frappe.tables['Stock Entry Detail'][0]
        self.assertEqual(row.custom_amp_drawing,'D1')
        self.assertEqual(row.custom_amp_boq_line_id,self.frappe.tables['Drawing BOQ Item'][0].boq_line_id)
