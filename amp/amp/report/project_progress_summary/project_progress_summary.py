from collections import defaultdict
import frappe
from frappe import _
from amp.amp.quantities import number, progress_values, structural_progress_values, weighted_completion
from amp.amp.report.data import child_rows, column, projects_and_drawings, report_filters, submitted_dprs


def execute(filters=None):
    filters = report_filters(filters)
    projects, drawings = projects_and_drawings(filters)
    dprs = submitted_dprs(filters, projects)
    lines = {}
    for row in child_rows("Drawing BOQ Item", drawings, "Project Drawing"):
        drawing = drawings[row.parent]
        if drawing.status not in ("Good For Construction (GFC)", "As-Built"):
            continue
        lines[(row.parent, row.boq_line_id)] = dict(
            project=drawing.project, main_area=drawing.main_area, sub_area=drawing.sub_area,
            drawing=drawing.name, item_code=row.item_code, uom=row.uom,
            activity=row.description or row.item_name or row.item_code,
            boq_line_id=row.boq_line_id, budget_qty=number(row.estimated_qty),
            progress_weight=number(row.progress_weight), previous_qty=0, period_qty=0,
            is_structural=row.discipline == "Structural",
            fabrication_progress_weight=number(row.fabrication_progress_weight),
            erection_progress_weight=number(row.erection_progress_weight),
            previous_fabricated_qty=0, period_fabricated_qty=0,
            previous_erected_qty=0, period_erected_qty=0,
            allocation="Approved BOQ", details=[])
    for row in child_rows("Daily Progress Item", dprs, "Daily Progress Report"):
        drawing = drawings.get(row.drawing)
        if not drawing:
            continue
        key = (row.drawing, row.boq_line_id or f"unallocated:{row.boq_item}:{row.uom}")
        if key not in lines:
            lines[key] = dict(project=drawing.project, main_area=drawing.main_area, sub_area=drawing.sub_area,
                drawing=row.drawing, item_code=row.boq_item, uom=row.uom, activity=row.activity_description or row.boq_item,
                boq_line_id=row.boq_line_id, budget_qty=0, progress_weight=0, previous_qty=0, period_qty=0,
                is_structural=False, fabrication_progress_weight=0, erection_progress_weight=0,
                previous_fabricated_qty=0, period_fabricated_qty=0,
                previous_erected_qty=0, period_erected_qty=0,
                allocation="Retired BOQ line" if row.boq_line_id else "Unallocated legacy DPR", details=[])
        line = lines[key]
        # Never add quantities with a different UOM to an existing activity.
        if line["uom"] != row.uom:
            frappe.throw(_("DPR {0} has a UOM mismatch for BOQ line {1}. Reconcile it before reporting.").format(row.parent, row.boq_line_id))
        dpr = dprs[row.parent]
        field = "previous_qty" if filters.get("from_date") and str(dpr.posting_date) < filters.from_date else "period_qty"
        if not row.is_structural_stage_progress:
            line[field] += number(row.today_executed_qty)
        fabrication_field = "previous_fabricated_qty" if field == "previous_qty" else "period_fabricated_qty"
        erection_field = "previous_erected_qty" if field == "previous_qty" else "period_erected_qty"
        line[fabrication_field] += number(row.today_fabricated_qty)
        line[erection_field] += number(row.today_erected_qty)
        line["details"].append(dict(activity=row.parent, dpr=row.parent, posting_date=dpr.posting_date,
            previous_qty=number(row.today_executed_qty) if field == "previous_qty" and not row.is_structural_stage_progress else 0,
            period_qty=number(row.today_executed_qty) if field == "period_qty" and not row.is_structural_stage_progress else 0,
            previous_fabricated_qty=number(row.today_fabricated_qty) if field == "previous_qty" else 0,
            period_fabricated_qty=number(row.today_fabricated_qty) if field == "period_qty" else 0,
            previous_erected_qty=number(row.today_erected_qty) if field == "previous_qty" else 0,
            period_erected_qty=number(row.today_erected_qty) if field == "period_qty" else 0, uom=row.uom))
    for line in lines.values():
        if line["is_structural"]:
            previous = structural_progress_values(
                line["budget_qty"], line["fabrication_progress_weight"], line["erection_progress_weight"],
                line["previous_fabricated_qty"], line["previous_erected_qty"], line["previous_qty"],
            )
            current = structural_progress_values(
                line["budget_qty"], line["fabrication_progress_weight"], line["erection_progress_weight"],
                line["previous_fabricated_qty"] + line["period_fabricated_qty"],
                line["previous_erected_qty"] + line["period_erected_qty"], line["previous_qty"] + line["period_qty"],
            )
            line.update(current)
            line["period_qty"] = current["executed_qty"] - previous["executed_qty"]
        else:
            line.update(progress_values(line["budget_qty"], line["previous_qty"], line["period_qty"]))
        line["fabricated_qty"] = line["previous_fabricated_qty"] + line["period_fabricated_qty"]
        line["erected_qty"] = line["previous_erected_qty"] + line["period_erected_qty"]
    data = []
    project_rows = []
    for project in projects:
        selected = [r for r in lines.values() if r["project"] == project.name]
        if (filters.get("main_area") or filters.get("sub_area") or filters.get("drawing")) and not selected:
            continue
        summary = dict(activity=project.project_name or project.name, project=project.name,
            indent=0, percent_progress=weighted_completion(selected), is_group=1)
        project_rows.append(summary)
        data.append(summary)
        append_groups(data, selected, ("main_area", "sub_area", "drawing"), 1, filters.get("show_dprs"))
    chart = dict(data=dict(labels=[r["activity"] for r in project_rows], datasets=[dict(name=_("Physical progress %"), values=[r["percent_progress"] for r in project_rows])]), type="bar")
    summary = [dict(label=_("Projects"), value=len(project_rows), datatype="Int"),
        dict(label=_("Weighted physical progress"), value=weighted_completion(list(lines.values())), datatype="Percent", indicator="Blue"),
        dict(label=_("Lines needing reconciliation"), value=sum(r["allocation"] != "Approved BOQ" for r in lines.values()), datatype="Int", indicator="Orange")]
    message = _("Submitted DPRs only. Dates filter execution; budgets use the CURRENT approved BOQ (not a historical baseline). Structural activities show Fabricated and Erected quantities separately and use their configured stage weights to calculate one physical completion value; the two quantities are never added together. Progress uses activity weights, default 1 per activity; quantities with different UOMs are never totalled. Retired/unallocated lines are displayed but excluded from weighted completion.")
    return columns(), data, message, chart, summary, True


def append_groups(data, lines, fields, indent, show_dprs):
    if fields:
        groups = defaultdict(list)
        for line in lines:
            groups[line.get(fields[0]) or _( "Not specified")].append(line)
        for label, rows in sorted(groups.items()):
            data.append(dict(activity=label, indent=indent, is_group=1, percent_progress=weighted_completion(rows)))
            append_groups(data, rows, fields[1:], indent + 1, show_dprs)
    else:
        for row in sorted(lines, key=lambda r: (r["item_code"], r.get("boq_line_id") or "")):
            data.append({k: v for k, v in row.items() if k != "details"} | dict(indent=indent))
            if show_dprs:
                for detail in sorted(row["details"], key=lambda d: (str(d["posting_date"]), d["dpr"])):
                    data.append(detail | dict(indent=indent+1))


def columns():
    return [column("activity", "Project / Area / Drawing / Activity", "Data", width=310),
        column("project", "Project", "Link", "Project"), column("item_code", "Item", "Link", "Item"),
        column("uom", "UOM", "Link", "UOM", 80), column("budget_qty", "Approved Work Qty"),
        column("previous_qty", "Before Period (Combined)"), column("period_qty", "During Period (Combined)"),
        column("previous_fabricated_qty", "Before Period Fabricated"), column("period_fabricated_qty", "During Period Fabricated"),
        column("fabricated_qty", "Cumulative Fabricated"),
        column("previous_erected_qty", "Before Period Erected"), column("period_erected_qty", "During Period Erected"),
        column("erected_qty", "Cumulative Erected"),
        column("executed_qty", "Cumulative Qty"), column("remaining_qty", "Remaining Qty"),
        column("overrun_qty", "Overrun Qty"), column("percent_progress", "Progress %", "Percent"),
        column("progress_weight", "Weight"), column("fabrication_progress_weight", "Fabrication % Weight"),
        column("erection_progress_weight", "Erection % Weight"), column("allocation", "Allocation", "Data", width=180),
        column("dpr", "DPR", "Link", "Daily Progress Report"), column("posting_date", "Date", "Date"),
        column("boq_line_id", "BOQ Reference", "Data", width=180)]
