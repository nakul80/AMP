import frappe
from frappe import _
from amp.amp.boq import stock_factor
from amp.amp.quantities import number
from amp.amp.report.data import child_rows, column, projects_and_drawings, report_filters, submitted_dprs
from amp.amp.transactions import TRANSACTIONS, stock_qty

MEASURES = ("draft_requested_qty", "requested_qty", "ordered_qty", "received_qty", "wip_qty", "consumed_qty", "reported_qty")


def execute(filters=None):
    filters = report_filters(filters)
    # Missing purchasing/stock permissions must not silently look like zero quantities.
    for doctype, _child, _date in TRANSACTIONS:
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(_("Read permission for {0} is required for the Material Status report.").format(doctype), frappe.PermissionError)
    projects, drawings = projects_and_drawings(filters)
    project_names = {p.name for p in projects}
    lines = {}
    for row in child_rows("Drawing BOQ Item", drawings, "Project Drawing"):
        drawing = drawings[row.parent]
        if drawing.status not in ("Good For Construction (GFC)", "As-Built"):
            continue
        factor = stock_factor(row.item_code, row.uom)
        key = (drawing.project, row.parent, row.boq_line_id, row.item_code)
        lines[key] = make_line(drawing.project, row.parent, row.boq_line_id, row.item_code, drawings, row.discipline or drawing.discipline)
        lines[key]["budget_qty"] = number(row.total_budget_qty) * factor
        lines[key]["allocation"] = "Approved BOQ"
    for parenttype, childtype, datefield in TRANSACTIONS:
        conditions = {"docstatus": ["in", [0, 1]] if parenttype == "Material Request" else 1, datefield: ["<=", filters.to_date]}
        if parenttype == "Material Request":
            conditions["material_request_type"] = "Purchase"
        fields = ["name", "docstatus", datefield]
        if parenttype == "Stock Entry":
            fields += ["purpose", "project"]
        parents = {p.name: p for p in frappe.get_list(parenttype, filters=conditions, fields=fields, limit_page_length=0)}
        for row in child_rows(childtype, parents, parenttype):
            parent = parents[row.parent]
            drawing = row.get("custom_amp_drawing")
            project = row.get("project") or parent.get("project")
            if drawing in drawings:
                project = drawings[drawing].project
            elif drawing:
                continue  # Drawing outside filters or not accessible.
            if project not in project_names:
                continue
            if not drawing and (filters.get("main_area") or filters.get("sub_area") or filters.get("drawing")):
                continue  # Unallocated transactions cannot be attributed to an area.
            line_id = row.get("custom_amp_boq_line_id") or ""
            key = (project, drawing or "", line_id, row.item_code)
            line = lines.setdefault(key, make_line(project, drawing, line_id, row.item_code, drawings))
            field = {"Material Request": "requested_qty", "Purchase Order": "ordered_qty", "Purchase Receipt": "received_qty"}.get(parenttype)
            if parenttype == "Material Request" and parent.docstatus == 0:
                field = "draft_requested_qty"
            if parenttype == "Stock Entry":
                if parent.purpose == "Material Issue":
                    field = "consumed_qty"
                elif parent.purpose == "Material Transfer":
                    wip = frappe.db.get_value("Project", project, "custom_amp_wip_warehouse")
                    if not wip or (row.t_warehouse != wip and row.s_warehouse != wip):
                        continue
                    field = "wip_qty"
                else:
                    continue
            qty = stock_qty(row | {"doctype": childtype})
            if field == "wip_qty":
                qty *= (1 if row.t_warehouse == wip else 0) - (1 if row.s_warehouse == wip else 0)
            line[field] += qty
            line["details"].append(dict(source_type=parenttype, source_name=row.parent, posting_date=parent[datefield], **{field: qty}))
    dprs = submitted_dprs(filters, projects)
    for row in child_rows("DPR Material Consumption", dprs, "Daily Progress Report"):
        parent = dprs[row.parent]
        if row.drawing and row.drawing not in drawings:
            continue
        if not row.drawing and filters.get("drawing"):
            continue
        key = (parent.project, row.drawing or "", row.boq_line_id or "", row.item_code)
        line = lines.setdefault(key, make_line(parent.project, row.drawing, row.boq_line_id, row.item_code, drawings))
        qty = number(row.qty_consumed) * stock_factor(row.item_code, row.uom)
        line["reported_qty"] += qty
        line["details"].append(dict(source_type="Daily Progress Report", source_name=row.parent, posting_date=parent.posting_date, reported_qty=qty))
    data = []
    for key, line in sorted(lines.items()):
        if filters.get("item_code") and line["item_code"] != filters.item_code:
            continue
        if filters.get("discipline") and line.get("discipline") != filters.discipline:
            continue
        allocated = line["allocation"] == "Approved BOQ"
        line["pending_request"] = max(0, line["budget_qty"] - line["requested_qty"] - line["draft_requested_qty"]) if allocated else None
        line["pending_order"] = max(0, line["requested_qty"] - line["ordered_qty"])
        line["pending_receipt"] = max(0, line["ordered_qty"] - line["received_qty"])
        line["budget_variance"] = line["consumed_qty"] - line["budget_qty"] if allocated else None
        data.append({k: v for k, v in line.items() if k != "details"} | dict(indent=0))
        if filters.get("show_transactions"):
            for detail in sorted(line["details"], key=lambda d: (str(d["posting_date"]), d["source_name"])):
                data.append(detail | dict(indent=1, project=line["project"], item_code=line["item_code"], uom=line["uom"]))
    summary = [dict(label=_("Material lines"), value=sum(r["indent"] == 0 for r in data), datatype="Int"),
        dict(label=_("Unallocated / retired lines"), value=sum(r["indent"] == 0 and r.get("allocation") != "Approved BOQ" for r in data), datatype="Int", indicator="Orange")]
    message = _("Cumulative transactions through To Date, in each item's stock UOM, against the CURRENT approved material budget. Draft requests are separate reservations. Receipts are net of returns. WIP shows net transfers to the Project's configured WIP warehouse, not consumption. DPR-reported usage is separate from stock-posted issues. Unallocated transactions appear only where their Project is known; they cannot be assigned to an area. Results respect document permissions and may cover only the transactions you can access.")
    return columns(), data, message, None, summary, True


def make_line(project, drawing, line_id, item_code, drawings, discipline=None):
    doc = drawings.get(drawing)
    return dict(project=project, drawing=drawing or "", boq_line_id=line_id or "", item_code=item_code,
        main_area=doc.main_area if doc else None, sub_area=doc.sub_area if doc else None, discipline=discipline or (doc.discipline if doc else None),
        uom=frappe.db.get_value("Item", item_code, "stock_uom"), budget_qty=0,
        allocation="Retired BOQ line" if line_id else "Unallocated", details=[], **{f: 0 for f in MEASURES})


def columns():
    result = [column("project", "Project", "Link", "Project", 180),
        column("main_area", "Main Area", "Link", "Project Main Area"), column("sub_area", "Sub Area", "Link", "Project Sub Area"),
        column("drawing", "Drawing", "Link", "Project Drawing"), column("discipline", "Discipline", "Data", width=110), column("item_code", "Item", "Link", "Item"), column("uom", "Stock UOM", "Link", "UOM", 90),
        column("budget_qty", "Material Budget")]
    result += [column(f, label) for f, label in zip(MEASURES, ("Draft Requests", "Requested", "Ordered", "Net Received", "Net WIP Transfers", "Stock Consumed", "DPR Reported Usage"))]
    result += [column("pending_request", "To Request"), column("pending_order", "To Order"), column("pending_receipt", "To Receive"), column("budget_variance", "Consumed Minus Budget"),
        column("allocation", "Allocation", "Data", width=160), column("source_type", "Source Type", "Link", "DocType"),
        column("source_name", "Source Document", "Dynamic Link", "source_type", 180), column("posting_date", "Date", "Date"), column("boq_line_id", "BOQ Reference", "Data", width=180)]
    return result
