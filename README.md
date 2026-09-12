# AMP - App for Managing Projects

A customized **Frappe / ERPNext v16** application designed specifically for construction and engineering projects:

1. **Drawing Register & Revision Control**:
   - Manage drawings across **Main Areas** and **Sub Areas**.
   - Discipline tracking: **Excavation**, **Civil**, **Structural**, and **Piping/Ducting/Railings** (as part of Structural).
   - Drawing Revision management (`Rev 0`, `Rev 1`, etc.) with PDF/CAD attachments and GFC (Good For Construction) status.

2. **Drawing BOM / BOQ Quantity Takeoff**:
   - Link each drawing item to ERPNext **Item Master** and **UOM**.
   - Capture estimated quantities, wastage allowances, and calculate total budgeted quantities.
   - Built-in revision delta comparison engine to highlight quantity differences between revisions.

3. **Procurement Integration**:
   - 1-Click creation of ERPNext **`Material Request`** (Purchase Indent) directly from approved drawing BOQ.
   - Real-time tracking of:
     $$\text{Drawing BOQ} \;\longleftrightarrow\; \text{Requested (PR)} \;\longleftrightarrow\; \text{Ordered (PO)} \;\longleftrightarrow\; \text{Received (GRN)} \;\longleftrightarrow\; \text{Executed (WIP)}$$
   - Prevents over-requesting beyond the approved drawing budget.

4. **Fast Site Progress & Daily Progress Reports (DPR)**:
   - **Excel-alternative Quick Entry Sheet**: Rapid tabular keyboard-friendly input of daily executed quantities.
   - Automatic generation of ERPNext **`Stock Entry`** (`Material Issue` / Transfer to WIP) upon DPR submission.
   - Material consumption logging with theoretical BOM vs actual site usage comparison.
   - Site photo attachments, contractor tracking, and weather logs.

---

## Installation on Frappe Cloud / Bench

### Frappe Cloud
1. Push this repository to GitHub or GitLab.
2. In your Frappe Cloud dashboard, go to **Apps** -> **Add App** and link your Git repository.
3. In your Site dashboard, click **Install App** and select **`amp`**.

### Bench CLI (Self-Hosted / Local)
```bash
bench get-app https://github.com/your-org/amp.git
bench --site [your-site-name] install-app amp
bench --site [your-site-name] migrate
```

---

## License
MIT License
