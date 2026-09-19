"""Retain the BOQ discipline on historic DPR rows for discipline-based reporting."""
import frappe


def execute():
    frappe.db.sql("""
        UPDATE `tabDaily Progress Item` AS item
        LEFT JOIN `tabDrawing BOQ Item` AS boq
            ON boq.parenttype = 'Project Drawing'
            AND boq.parent = item.drawing
            AND boq.boq_line_id = item.boq_line_id
        LEFT JOIN `tabProject Drawing` AS drawing ON drawing.name = item.drawing
        SET item.discipline = COALESCE(NULLIF(boq.discipline, ''), drawing.discipline)
        WHERE item.discipline IS NULL OR item.discipline = ''
    """)
