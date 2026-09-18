"""Controller regression tests with explicit document/database mocks."""
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch
from test_reports import FakeFrappe, Row


class Doc:
    def __init__(self, **values):
        self.__dict__.update(values)
        self.flags = Row()

    def __getattr__(self, key):
        return None

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def set(self, key, value):
        setattr(self, key, value)

    def check_permission(self, permission):
        pass

    def get_doc_before_save(self):
        return self.get('_before')

    def append(self, field, values):
        rows = self.get(field) or []
        rows.append(Doc(**values))
        self.set(field, rows)
        return rows[-1]


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.frappe=FakeFrappe()
        self.frappe.whitelist=lambda: lambda function: function
        document=types.ModuleType('frappe.model.document')
        document.Document=Doc
        utils=types.ModuleType('frappe.utils')
        utils.nowdate=lambda:'2026-09-18'
        utils.add_days=lambda date,days:'2026-09-25'
        self.frappe.utils=utils
        self.frappe.defaults=Row(get_user_default=lambda key:'Company')
        self.modules=patch.dict(sys.modules, {'frappe':self.frappe,'frappe.model':types.ModuleType('frappe.model'),'frappe.model.document':document,'frappe.utils':utils})
        self.modules.start()
        self.loaded={}
        for name in ['amp.amp.boq','amp.amp.transactions',
                     'amp.amp.doctype.drawing_boq_item.drawing_boq_item',
                     'amp.amp.doctype.project_drawing.project_drawing',
                     'amp.amp.doctype.drawing_revision.drawing_revision',
                     'amp.amp.doctype.daily_progress_item.daily_progress_item',
                     'amp.amp.doctype.daily_progress_report.daily_progress_report',
                     'amp.amp.api.procurement','amp.amp.api.progress','amp.amp.api.stock_entry']:
            self.loaded[name]=importlib.reload(importlib.import_module(name))

    def tearDown(self):
        self.modules.stop()

    def test_dpr_uses_server_quantities_and_distinguishes_repeated_items(self):
        module=self.loaded['amp.amp.doctype.daily_progress_report.daily_progress_report']
        item_cls=self.loaded['amp.amp.doctype.daily_progress_item.daily_progress_item'].DailyProgressItem
        drawing=Doc(name='D1',project='P1',main_area='A1',sub_area=None,status='Good For Construction (GFC)',boq_items=[
            Doc(boq_line_id='L1',item_code='STEEL',uom='Kg',estimated_qty=100),
            Doc(boq_line_id='L2',item_code='STEEL',uom='Kg',estimated_qty=200)])
        rows=[item_cls(drawing='D1',boq_item='STEEL',boq_line_id=key,uom='Kg',today_executed_qty=5,drawing_budget_qty=9999,previously_executed_qty=9999) for key in ['L1','L2']]
        dpr=module.DailyProgressReport(project='P1',main_area='A1',progress_items=rows,material_consumptions=[],auto_create_stock_entry=0)
        with patch.object(module,'validate_location'),patch.object(module,'lock_drawing'),patch.object(module,'drawing_totals',return_value={'L1':20,'L2':30}),patch.object(module,'drawing_stage_totals',return_value={}),patch.object(self.frappe,'get_doc',return_value=drawing):
            dpr.validate()
        self.assertEqual((rows[0].drawing_budget_qty,rows[0].previously_executed_qty,rows[0].cumulative_executed_qty),(100,20,25))
        self.assertEqual(rows[1].cumulative_executed_qty,35)
        self.assertEqual(dpr.material_consumptions,[])

    def test_structural_dpr_tracks_fabrication_and_erection_separately(self):
        module=self.loaded['amp.amp.doctype.daily_progress_report.daily_progress_report']
        item_cls=self.loaded['amp.amp.doctype.daily_progress_item.daily_progress_item'].DailyProgressItem
        line=Doc(boq_line_id='L1',item_code='STEEL',uom='Kg',estimated_qty=100,discipline='Structural',
            fabrication_progress_weight=40,erection_progress_weight=60)
        drawing=Doc(name='D1',project='P1',main_area='A1',sub_area=None,status='Good For Construction (GFC)',boq_items=[line])
        row=item_cls(drawing='D1',boq_item='STEEL',boq_line_id='L1',uom='Kg',today_executed_qty=0,
            today_fabricated_qty=10,today_erected_qty=5)
        dpr=module.DailyProgressReport(project='P1',main_area='A1',progress_items=[row],material_consumptions=[],auto_create_stock_entry=0)
        with patch.object(module,'validate_location'),patch.object(module,'lock_drawing'),patch.object(module,'drawing_totals',return_value={'L1':14}),patch.object(module,'drawing_stage_totals',return_value={'L1':{'fabricated':20,'erected':10}}),patch.object(self.frappe,'get_doc',return_value=drawing):
            dpr.validate()
        self.assertEqual((row.previously_fabricated_qty,row.cumulative_fabricated_qty),(20,30))
        self.assertEqual((row.previously_erected_qty,row.cumulative_erected_qty),(10,15))
        self.assertEqual(row.today_executed_qty,7)
        self.assertEqual(row.is_structural_stage_progress,1)

    def test_structural_dpr_rejects_erection_ahead_of_fabrication(self):
        module=self.loaded['amp.amp.doctype.daily_progress_report.daily_progress_report']
        item_cls=self.loaded['amp.amp.doctype.daily_progress_item.daily_progress_item'].DailyProgressItem
        line=Doc(boq_line_id='L1',item_code='STEEL',uom='Kg',estimated_qty=100,discipline='Structural',fabrication_progress_weight=50,erection_progress_weight=50)
        drawing=Doc(name='D1',project='P1',main_area='A1',sub_area=None,status='Good For Construction (GFC)',boq_items=[line])
        row=item_cls(drawing='D1',boq_item='STEEL',boq_line_id='L1',uom='Kg',today_fabricated_qty=0,today_erected_qty=1)
        dpr=module.DailyProgressReport(project='P1',main_area='A1',progress_items=[row],material_consumptions=[],auto_create_stock_entry=0)
        with patch.object(module,'validate_location'),patch.object(module,'lock_drawing'),patch.object(module,'drawing_totals',return_value={'L1':0}),patch.object(module,'drawing_stage_totals',return_value={}),patch.object(self.frappe,'get_doc',return_value=drawing):
            with self.assertRaisesRegex(ValueError,'Erected quantity'):
                dpr.validate()

    def test_dpr_rejects_cross_project_drawing(self):
        module=self.loaded['amp.amp.doctype.daily_progress_report.daily_progress_report']
        dpr=module.DailyProgressReport(project='P1',main_area='A1',progress_items=[Doc(drawing='D2')])
        drawing=Doc(project='P2',main_area='A1')
        with patch.object(module,'validate_location'),patch.object(module,'lock_drawing'),patch.object(self.frappe,'get_doc',return_value=drawing):
            with self.assertRaisesRegex(ValueError,'DPR drawing must belong'):
                dpr.validate()

    def test_ambiguous_item_without_line_reference_is_rejected(self):
        module=self.loaded['amp.amp.boq']
        drawing=Doc(name='D1',boq_items=[Doc(boq_line_id='A',item_code='STEEL',uom='Kg'),Doc(boq_line_id='B',item_code='STEEL',uom='Kg')])
        with self.assertRaisesRegex(ValueError,'unambiguous'):
            module.resolve_line(drawing,item_code='STEEL',uom='Kg')
        self.assertEqual(module.resolve_line(drawing,'B','STEEL').boq_line_id,'B')

    def test_budget_guard_includes_other_draft_requests(self):
        module=self.loaded['amp.amp.transactions']
        drawing=Doc(name='D1',boq_items=[Doc(boq_line_id='L1',item_code='STEEL',uom='Kg',total_budget_qty=100)])
        doc=Doc(name='NEW',items=[Doc(custom_amp_drawing='D1',custom_amp_boq_line_id='L1',item_code='STEEL',uom='Kg',qty=25)])
        with patch.object(module,'lock_drawing'),patch.object(module,'stock_factor',return_value=1),patch.object(module,'material_totals',return_value={'L1':{'requested_qty':60,'draft_requested_qty':20}}),patch.object(self.frappe,'get_doc',return_value=drawing):
            with self.assertRaisesRegex(ValueError,'exceeds'):
                module.validate_request_budget(doc)
            doc.items[0].qty=20
            module.validate_request_budget(doc)

    def test_procurement_rejects_unapproved_drawing(self):
        module=self.loaded['amp.amp.api.procurement']
        with patch.object(module,'lock_drawing'),patch.object(self.frappe,'get_doc',return_value=Doc(status='Draft')):
            with self.assertRaisesRegex(ValueError,'GFC'):
                module.create_material_request_from_drawing('D1')

    def test_revision_endpoint_uses_shared_drawing_procurement(self):
        module=self.loaded['amp.amp.api.procurement']
        revision=Doc(drawing='D1',revision_status='Approved - GFC',reload=Mock())
        with patch.object(module,'lock_drawing'),patch.object(self.frappe,'get_doc',return_value=revision),patch.object(module,'create_material_request_from_drawing',return_value='MR1') as create:
            self.assertEqual(module.create_material_request_from_revision('REV1'),'MR1')
            create.assert_called_once_with('D1')

    def test_revision_sync_does_not_copy_operational_counters(self):
        module=self.loaded['amp.amp.doctype.drawing_revision.drawing_revision']
        revision=module.DrawingRevision(drawing='D1',name='REV2',revision_no='REV 2',revision_status='Approved - GFC',
            items=[Doc(boq_line_id='L1',item_code='STEEL',uom='Kg',discipline='Civil',estimated_qty=150,wastage_percent=0,progress_weight=1,executed_qty=0,requested_qty=0)])
        parent=Doc(name='D1',boq_items=[Doc(boq_line_id='L1',item_code='STEEL',uom='Kg',estimated_qty=100,executed_qty=50)],save=Mock())
        with patch.object(self.frappe,'get_doc',return_value=parent),patch.object(self.frappe,'get_all',return_value=[]),patch.object(module,'refresh_drawing') as refresh:
            revision.on_update()
            self.assertEqual(parent.boq_items[0].estimated_qty,150)
            self.assertNotIn('executed_qty',parent.boq_items[0].__dict__)
            refresh.assert_called_once_with('D1')

    def test_cancel_stock_then_rebuild_drawing_once(self):
        module=self.loaded['amp.amp.doctype.daily_progress_report.daily_progress_report']
        events=[]
        entry=Doc(docstatus=1,cancel=lambda:events.append('cancel-stock'))
        dpr=module.DailyProgressReport(docstatus=2,stock_entry='SE1',progress_items=[Doc(drawing='D1'),Doc(drawing='D1')])
        with patch.object(self.frappe,'get_doc',return_value=entry),patch.object(module,'refresh_drawing',side_effect=lambda name:events.append('refresh-'+name)):
            dpr.on_cancel()
        self.assertEqual(events,['cancel-stock','refresh-D1'])

    def test_wastage_affects_procurement_not_physical_progress(self):
        cls=self.loaded['amp.amp.doctype.drawing_boq_item.drawing_boq_item'].DrawingBOQItem
        row=cls(estimated_qty=100,wastage_percent=10,requested_qty=30,draft_requested_qty=20,executed_qty=40)
        row.calculate_quantities()
        self.assertEqual((row.total_budget_qty,row.balance_to_order,row.balance_to_execute),(110,60,60))

    def test_stock_conversion_uses_persisted_transaction_factor(self):
        module=self.loaded['amp.amp.transactions']
        self.assertEqual(module.stock_qty({'doctype':'Purchase Receipt Item','qty':2,'conversion_factor':100,'stock_qty':200}),200)
        self.assertEqual(module.stock_qty({'doctype':'Stock Entry Detail','qty':2,'conversion_factor':100,'transfer_qty':200}),200)
