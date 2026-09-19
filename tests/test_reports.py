"""Execute real report code against a permission-aware in-memory Frappe adapter.

These tests exercise filtering and aggregation, not Frappe/database integration.
"""
import datetime
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


class FakeFrappe(types.ModuleType):
    def __init__(self):
        super().__init__('frappe')
        self._ = lambda text: text
        self._dict = Row
        self.PermissionError = PermissionError
        self.tables = {}
        self.hidden = set()
        self.denied_types = set()
        self.db = types.SimpleNamespace(get_value=self.get_value)

    def has_permission(self, doctype, _permission):
        return doctype not in self.denied_types

    def throw(self, text, exc=ValueError):
        raise exc(text)

    def get_doc(self, doctype, name, **kwargs):
        row = next(r for r in self.tables[doctype] if r.name == name)
        row.check_permission = lambda permission: self.throw('Denied', PermissionError) if name in self.hidden else None
        return row

    def get_value(self, doctype, name, field):
        for row in self.tables.get(doctype, []):
            if (row.name == name if isinstance(name, str) else self.matches(row, name)):
                return row.get(field)
        return None

    @staticmethod
    def matches(row, filters):
        for key, expected in filters.items():
            actual = row.get(key)
            if isinstance(expected, list):
                op, value = expected
                if op == 'in' and actual not in value:
                    return False
                if op == '<=' and str(actual) > str(value):
                    return False
            elif actual != expected:
                return False
        return True

    def query(self, doctype, filters=None, fields=None, pluck=None, permissions=False, **kwargs):
        if permissions and not self.has_permission(doctype, 'read'):
            raise PermissionError(doctype)
        rows = [r for r in self.tables.get(doctype, []) if self.matches(r, filters or {}) and (not permissions or r.name not in self.hidden)]
        if pluck:
            return [r.get(pluck) for r in rows]
        return [Row(r) if fields == ['*'] else Row({f: r.get(f) for f in fields}) for r in rows]

    def get_list(self, doctype, **kwargs):
        return self.query(doctype, permissions=True, **kwargs)

    def get_all(self, doctype, **kwargs):
        return self.query(doctype, **kwargs)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.frappe = FakeFrappe()
        utils = types.ModuleType('frappe.utils')
        utils.nowdate = lambda: '2026-09-18'
        utils.getdate = lambda value: datetime.date.fromisoformat(str(value))
        self.modules = patch.dict(sys.modules, {'frappe': self.frappe, 'frappe.utils': utils})
        self.modules.start()
        # Reload production modules so every test uses its own database adapter.
        for name in ['amp.amp.boq', 'amp.amp.transactions', 'amp.amp.report.data',
                     'amp.amp.report.project_progress_summary.project_progress_summary',
                     'amp.amp.report.project_material_status.project_material_status']:
            module = importlib.import_module(name)
            importlib.reload(module)
        self.progress = sys.modules['amp.amp.report.project_progress_summary.project_progress_summary']
        self.material = sys.modules['amp.amp.report.project_material_status.project_material_status']
        self.frappe.tables = {
            'Project': [Row(name='P1', project_name='Plant'), Row(name='P2', project_name='No Areas', custom_amp_wip_warehouse='WIP')],
            'Project Drawing': [Row(name='D1', project='P1', main_area='A1', sub_area=None, status='Good For Construction (GFC)')],
            'Drawing BOQ Item': [Row(name='B1', parent='D1', parenttype='Project Drawing', boq_line_id='L1', item_code='STEEL', item_name='Steel', uom='Kg', estimated_qty=100, total_budget_qty=110, progress_weight=1)],
            'Item': [Row(name='STEEL', stock_uom='Kg')],
            'Daily Progress Report': [Row(name='DPR1', project='P1', main_area='A1', docstatus=1, posting_date='2026-09-01'),
                Row(name='DPR2', project='P1', main_area='A1', docstatus=1, posting_date='2026-09-10'),
                Row(name='DRAFT', project='P1', main_area='A1', docstatus=0, posting_date='2026-09-10'),
                Row(name='CANCELLED', project='P1', main_area='A1', docstatus=2, posting_date='2026-09-10')],
            'Daily Progress Item': [Row(name='PI'+str(i), parent=parent, parenttype='Daily Progress Report', drawing='D1', boq_line_id='L1', boq_item='STEEL', uom='Kg', today_executed_qty=qty)
                for i,(parent,qty) in enumerate([('DPR1',20),('DPR2',30),('DRAFT',500),('CANCELLED',700)])],
        }

    def tearDown(self):
        self.modules.stop()

    def test_all_projects_and_project_only_need_no_area(self):
        rows = self.progress.execute({})[1]
        self.assertEqual(len([r for r in rows if r.get('indent') == 0]), 2)
        self.assertEqual(next(r for r in rows if r.get('project') == 'P2')['percent_progress'], 0)
        rows = self.progress.execute({'project': 'P1'})[1]
        self.assertEqual(rows[0]['percent_progress'], 50)
        self.assertEqual(next(r for r in rows if r.get('boq_line_id') == 'L1')['budget_qty'], 100)

    def test_period_and_status_filters(self):
        rows = self.progress.execute({'from_date':'2026-09-05', 'to_date':'2026-09-18', 'show_dprs':1})[1]
        line = next(r for r in rows if r.get('boq_line_id') == 'L1')
        self.assertEqual((line['previous_qty'], line['period_qty'], line['executed_qty']), (20,30,50))
        self.assertEqual({r['dpr'] for r in rows if r.get('dpr')}, {'DPR1','DPR2'})
        rows = self.progress.execute({'to_date':'2026-09-05'})[1]
        self.assertEqual(rows[0]['percent_progress'], 20)

    def test_permissions_apply_to_dprs_and_projects(self):
        self.frappe.hidden.update(['DPR2','P2'])
        rows = self.progress.execute({})[1]
        self.assertEqual(rows[0]['percent_progress'], 20)
        self.assertFalse(any(r.get('project') == 'P2' for r in rows))

    def test_unallocated_legacy_is_visible_not_silently_counted(self):
        self.frappe.tables['Daily Progress Item'][0]['boq_line_id'] = None
        rows = self.progress.execute({})[1]
        self.assertEqual(rows[0]['percent_progress'], 30)
        self.assertEqual(next(r for r in rows if r.get('allocation') == 'Unallocated legacy DPR')['executed_qty'], 20)

    def test_structural_report_separates_stages_and_uses_stage_weights(self):
        line=self.frappe.tables['Drawing BOQ Item'][0]
        line.update(discipline='Structural', fabrication_progress_weight=40, erection_progress_weight=60)
        self.frappe.tables['Daily Progress Item'][0].update(today_executed_qty=0, today_fabricated_qty=50, today_erected_qty=20)
        self.frappe.tables['Daily Progress Item'][1].update(today_executed_qty=0, today_fabricated_qty=10, today_erected_qty=10)
        rows=self.progress.execute({'from_date':'2026-09-05', 'to_date':'2026-09-18', 'show_dprs': 1})[1]
        structural=next(row for row in rows if row.get('boq_line_id') == 'L1')
        self.assertEqual((structural['fabricated_qty'], structural['erected_qty']), (60,30))
        self.assertEqual((structural['previous_fabricated_qty'], structural['period_fabricated_qty']), (50,10))
        self.assertEqual((structural['previous_erected_qty'], structural['period_erected_qty']), (20,10))
        self.assertEqual(structural['percent_progress'],42)
        details = [row for row in rows if row.get('dpr')]
        self.assertEqual(
            {(row['dpr'], row['work_done'], row['reported_qty']) for row in details},
            {('DPR1', 'Fabrication', 50), ('DPR1', 'Erection', 20), ('DPR2', 'Fabrication', 10), ('DPR2', 'Erection', 10)},
        )

    def test_reject_reversed_dates(self):
        with self.assertRaisesRegex(ValueError, 'From Date'):
            self.progress.execute({'from_date':'2026-09-18','to_date':'2026-09-01'})

    def transaction(self, parenttype, childtype, name, qty, status=1, **extra):
        parent = Row(name=name, docstatus=status, transaction_date='2026-09-10', posting_date='2026-09-10', material_request_type='Purchase', project='P1', purpose='Material Issue')
        parent.update(extra.pop('parent_fields', {}))
        self.frappe.tables.setdefault(parenttype, []).append(parent)
        row = Row(name=name+'-item', parent=name, parenttype=parenttype, item_code='STEEL', project='P1',
            custom_amp_drawing='D1', custom_amp_boq_line_id='L1', stock_qty=qty, transfer_qty=qty)
        row.update(extra)
        self.frappe.tables.setdefault(childtype, []).append(row)

    def test_material_transactions_returns_drafts_and_no_double_consumption(self):
        self.transaction('Material Request','Material Request Item','MR',80)
        self.transaction('Material Request','Material Request Item','MR-DRAFT',10,status=0)
        self.transaction('Material Request','Material Request Item','MR-CANCEL',1000,status=2)
        self.transaction('Purchase Order','Purchase Order Item','PO',70)
        self.transaction('Purchase Receipt','Purchase Receipt Item','PR',60)
        self.transaction('Purchase Receipt','Purchase Receipt Item','RETURN',-5)
        self.transaction('Stock Entry','Stock Entry Detail','ISSUE',25)
        self.frappe.tables['DPR Material Consumption']=[Row(name='M1',parent='DPR1',parenttype='Daily Progress Report',drawing='D1',boq_line_id='L1',item_code='STEEL',uom='Kg',qty_consumed=25)]
        row = self.material.execute({'show_transactions':1})[1][0]
        self.assertEqual((row['requested_qty'], row['draft_requested_qty'], row['ordered_qty'], row['received_qty']), (80,10,70,55))
        self.assertEqual((row['consumed_qty'], row['reported_qty']), (25,25))
        self.assertEqual((row['pending_request'], row['pending_order'], row['pending_receipt']), (20,10,15))
        self.assertEqual(row['budget_variance'], -85)

    def test_wip_transfers_are_not_consumption(self):
        self.frappe.tables['Project'][0]['custom_amp_wip_warehouse']='WIP'
        self.transaction('Stock Entry','Stock Entry Detail','IN',12,parent_fields={'purpose':'Material Transfer'},s_warehouse='Store',t_warehouse='WIP')
        self.transaction('Stock Entry','Stock Entry Detail','OUT',2,parent_fields={'purpose':'Material Transfer'},s_warehouse='WIP',t_warehouse='Store')
        row=self.material.execute({})[1][0]
        self.assertEqual(row['wip_qty'],10)
        self.assertEqual(row['consumed_qty'],0)

    def test_material_requires_read_permissions(self):
        self.frappe.denied_types.add('Purchase Order')
        with self.assertRaises(PermissionError):
            self.material.execute({})

    def test_unallocated_project_transactions_are_visible(self):
        self.transaction('Material Request','Material Request Item','OLD-MR',15,custom_amp_drawing=None,custom_amp_boq_line_id=None)
        rows=self.material.execute({})[1]
        self.assertEqual(next(r for r in rows if r['allocation']=='Unallocated')['requested_qty'],15)
