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
            drawing=drawing.name, discipline=row.discipline or drawing.discipline, item_code=row.item_code, uom=row.uom,
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
                drawing=row.drawing, discipline=row.discipline or drawing.discipline, item_code=row.boq_item, uom=row.uom, activity=row.activity_description or row.boq_item,
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
        # One visible diary row per actual work stage makes the reported work unambiguous.
        add_work_done_details(line, row, dpr)
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
        selected = [r for r in lines.values() if r["project"] == project.name and (not filters.get("discipline") or r.get("discipline") == filters.discipline)]
        if (filters.get("main_area") or filters.get("sub_area") or filters.get("drawing") or filters.get("discipline")) and not selected:
            continue
        summary = dict(activity=project.project_name or project.name, project=project.name,
            indent=0, percent_progress=weighted_completion(selected), is_group=1)
        project_rows.append(summary)
        data.append(summary)
        append_groups(data, selected, ("main_area", "sub_area", "discipline", "drawing"), 1, filters.get("show_dprs"))
    chart = dict(data=dict(labels=[r["activity"] for r in project_rows], datasets=[dict(name=_("Physical progress %"), values=[r["percent_progress"] for r in project_rows])]), type="bar")
    summary = [dict(label=_("Projects"), value=len(project_rows), datatype="Int"),
        dict(label=_("Weighted physical progress"), value=weighted_completion([r for r in lines.values() if not filters.get("discipline") or r.get("discipline") == filters.discipline]), datatype="Percent", indicator="Blue"),
        dict(label=_("Lines needing reconciliation"), value=sum(r["allocation"] != "Approved BOQ" for r in lines.values()), datatype="Int", indicator="Orange")]
    message = _("This is a project summary. Expand an activity only when you need the DPR diary rows: each row states whether the work done was Execution, Fabrication, or Erection and its recorded quantity. Civil and Structural work are shown in separate discipline groups and can be filtered independently. Structural completion uses the configured stage weights; fabricated and erected quantities are never added together.")
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


def add_work_done_details(line, row, dpr):
    base = dict(dpr=row.parent, posting_date=dpr.posting_date, uom=row.uom, remarks=row.remarks or "")
    stages = (
        (_("Execution"), number(row.today_executed_qty), not row.is_structural_stage_progress),
        (_("Fabrication"), number(row.today_fabricated_qty), True),
        (_("Erection"), number(row.today_erected_qty), True),
    )
    for work_done, quantity, applicable in stages:
        if applicable and quantity:
            line["details"].append(base | dict(
                activity=_('{0} — {1}').format(row.parent, work_done),
                work_done=work_done, reported_qty=quantity,
            ))


def columns():
    return [column("activity", "Project / Area / Drawing / Activity", "Data", width=310),
        column("project", "Project", "Link", "Project"), column("discipline", "Discipline", "Data", width=110),
        column("work_done", "Work Done", "Data", width=110), column("item_code", "Item", "Link", "Item"),
        column("uom", "UOM", "Link", "UOM", 80), column("budget_qty", "Approved Qty"),
        column("reported_qty", "Recorded Qty"), column("fabricated_qty", "Fabricated To Date"),
        column("erected_qty", "Erected To Date"), column("executed_qty", "Progress Qty"),
        column("remaining_qty", "Remaining Qty"), column("percent_progress", "Progress %", "Percent"),
        column("allocation", "Allocation", "Data", width=180),
        column("dpr", "DPR", "Link", "Daily Progress Report"), column("posting_date", "Date", "Date"), column("remarks", "Remarks", "Data", width=180),
        column("boq_line_id", "BOQ Reference", "Data", width=180)]
