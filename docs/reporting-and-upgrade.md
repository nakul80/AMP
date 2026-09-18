# AMP 0.0.2: reporting and transaction references

## Installing the update

ERPNext must be installed on the site. For a self-hosted bench, deploy the updated app, then run:

```bash
bench --site SITE migrate
bench build --app amp
bench --site SITE clear-cache
```

### Frappe Cloud deployment

1. Push the completed AMP revision to its GitHub repository.
2. Open the target **private Bench Group → Apps**. Add the repository with **Add App → Add from GitHub** if it is not already listed. The connected Frappe Cloud GitHub App must be allowed to read the repository.
3. Select **Update Available**, select a staging site first, and choose **Deploy and Update**. The bench deploy fetches the current GitHub revision and runs the app migration.
4. On a first installation only, open that site's **Apps** tab and select **Install App → AMP**. An existing AMP site only needs the deploy; reinstalling is unnecessary.
5. Review the deploy log before continuing. Refresh the Desk browser tab after it completes, then perform the site verification steps below.

The migration installs ERPNext custom fields, assigns stable BOQ references where attribution is unambiguous, adds structural fabrication/erection fields, fixes the Stock Entry/DPR reverse link, rebuilds drawing counters, and refreshes the AMP workspace. Existing Project records remain the project master.

The local repository has no Frappe installation, database, or connected site. The automated tests use in-memory adapters and mocks. They do not establish that migration, permissions, stock valuation, or the UI works on your particular site. Run the site verification below after installation.

## Opening reports

Use **AMP → Project Progress Summary** or **Project → AMP Reports**. Project, Main Area, Sub Area, and Drawing are all optional. Leaving Project blank includes accessible projects, including projects with no areas/drawings (zero progress). Selecting only Project works; no Main Area is required.

- Submitted DPRs supply execution quantities; drafts and cancellations are excluded.
- From Date separates prior execution from execution during the period; a blank From Date includes all execution through To Date.
- Physical work budget is `estimated_qty`, excluding procurement wastage.
- Each BOQ line has a **Progress Weight**, default 1. Overall progress is `sum(weight × min(executed/work budget, 1)) / sum(weight)`. Equal default weights mean equal activity weighting, not cost or duration weighting. Configure weights to match the project's measurement plan.
- Zero-budget, zero-weight, retired, and unallocated activities do not contribute to overall completion. Overrun quantities remain visible.
- Expand Project → Main Area → Sub Area → Drawing → Activity to see DPR document links. Disable Show DPR Entries for a shorter view.
- Budget and hierarchy are the **current** approved drawing BOQ, including As-Built drawings. A historical To Date does not select a historical design baseline.
- Report queries respect accessible Projects, Drawings and DPRs. A restricted user's figures can represent only their accessible records, not the entire company's project.

**Project Material Status** is cumulative through To Date, in the item's stock UOM. It shows separate draft reservations, submitted purchase requests, orders, net receipts (returns reduce receipts), net transfers to the configured Project WIP warehouse, stock material issues, and DPR-reported material usage. Draft requests reduce available procurement budget but are not counted as submitted requests. Different items/UOMs are never given a grand quantity total.

- Configure Project → AMP Construction → WIP Warehouse to classify WIP transfers. Transfers to other warehouses are not treated as WIP or consumption.
- “Consumed Minus Budget” compares stock issues with the full approved material budget. It is not a theoretical consumption variance based on work performed. This app does not yet have an activity-to-material BOM conversion model.
- “To Request” is budget less submitted requests and draft reservations. “To Order” is requested less ordered; “To Receive” is ordered less net receipts, each floored at zero. These quantity balances are not forecasts and do not model waived/closed commitments.
- Enable Show Transactions for clickable source documents. A DPR-reported quantity is not added again to stock consumption.
- The report requires read permission for Material Request, Purchase Order, Purchase Receipt, and Stock Entry as well as AMP records. No purchasing/stock permissions are automatically granted. Row-level restrictions still apply, and partial access can result in partial totals.

## Daily progress entry

Main Area is still required when **creating a DPR**, because the DPR records the site location. It is optional in the reports.

The new **View Submitted DPR** action opens the exact created document. In the DPR List, **Show All DPRs** clears saved filters; **Submitted DPRs** clears filters and selects submitted documents. Status indicators distinguish Draft, Submitted, and Cancelled. Fetch Open Drawing Tasks now works before the first save and preserves the exact BOQ-line reference, including repeated item codes.

Quick Entry has an optional **Material Used** column. Work executed no longer implicitly consumes the same quantity of an item. Enter actual material usage explicitly. A selected warehouse posts that usage as a Stock Entry; without a warehouse it remains DPR-reported usage. Use the normal DPR form for several different materials, batches, or transfer to WIP. Submitting stock requires the user's normal Stock Entry create/submit permissions; cancelling a DPR with a linked Stock Entry requires stock cancellation permission.

Existing draft DPRs may already contain material rows auto-generated by the old version: review those quantities before submission. This update does not erase them.

## Structural fabrication and erection

For every **Structural** BOQ line, AMP records **Fabricated Qty** and **Erected Qty** independently. Site Progress Quick Entry shows separate blue Fabricated and amber Erected input columns for those lines. The normal Today Executed Qty input is unavailable for structural lines; it remains available for other disciplines.

Each structural BOQ line has Fabrication Progress Weight and Erection Progress Weight, set to 50% each by default. They must total 100%. The combined physical completion is:

`fabricated completion × fabrication weight + erected completion × erection weight`

For example, with a 100-tonne activity weighted 40% fabrication and 60% erection, 50 tonnes fabricated and 20 tonnes erected gives `50% × 40% + 20% × 60% = 32%` combined completion. It does not report 70% by adding the two quantities.

AMP prevents an accumulated erected quantity from exceeding the accumulated fabricated quantity. It preserves old submitted structural DPR rows as legacy combined execution so they are not lost, but does not try to infer fabrication versus erection from them. New structural entries are tagged as stage progress, preventing their calculated combined quantity from being counted a second time.

Project Progress Summary adds Before/During/Cumulative Fabricated and Erected columns alongside its combined physical completion. Configure weights on the drawing BOQ before releasing the revision; approved revision quantities and weights are immutable, so create a new revision for a change.

## Revision and procurement behavior

A BOQ line has a stable `boq_line_id` carried into new revisions and transaction rows. New Revision copies these references and progress weights. Add a new row for a different item, UOM, or discipline; do not reuse an existing reference for a different activity. Approved and superseded revision quantities cannot be edited in place.

Approving a revision changes design quantities but rebuilds execution/procurement counters from transactions. Removed activities retain their historical DPR/transaction rows and appear as retired lines in reports. Saving approved revision metadata does not reset counters.

Both Create Material Request buttons use the same active drawing balance. Requests reserve budget while in draft. Submission, editing, deletion, cancellation, and amendment update balances through transaction reconciliation. GFC approval and budget limits are checked server-side. Purchase Order and Purchase Receipt rows inherit the drawing/revision/BOQ reference from their upstream rows. Direct stock/purchasing rows may select an AMP Drawing; where an item appears multiple times, a specific BOQ reference is needed rather than guessing.

## Legacy data

The migration assigns existing DPR rows to current BOQ lines only when item/UOM matching is unique. It connects historical stock rows only through the existing explicit DPR → Stock Entry link and a unique material row. It does not infer drawing allocations from remarks.

Old requests/orders/receipts lack reliable drawing references. They remain **Unallocated** under their Project. Transactions without any Project cannot be attributed to AMP and are outside this report. Unallocated project transactions cannot appear under a Main Area filter. Reconcile legacy procurement allocations before treating the new per-drawing available budget as complete: old unallocated requests do not reserve a particular drawing's budget.

A retired or ambiguous activity is displayed separately and excluded from current weighted progress. Migration does not change historical executed quantities, document statuses, stock ledger entries, or posting dates. Do not reinterpret ambiguous quantities without reviewing their source documents.

## Diagnosing a count/list mismatch on the site

1. Open `/app/daily-progress-report`, click Show All DPRs, and try the exact DPR link.
2. If the record still does not appear, an administrator can run:

```bash
bench --site SITE execute amp.amp.api.diagnostics.dpr_visibility --kwargs '{"name":"DPR-2026-00001","user":"engineer@example.com"}'
```

This read-only diagnostic reports stored docstatus, location, linked stock entry, and whether that user can read the document and see it in an unfiltered list. It does not change roles or User Permissions. A visible document with an empty filtered list suggests saved filters or browser/site customization; failed read access calls for checking the user's roles and Project User Permissions. Capture the failing list request/server traceback if the browser reports an error. The original counter issue cannot be confirmed as resolved without checking the affected site and user.

## Site verification

1. Run migration on a test site containing existing drawings, revisions, DPRs, and procurement. Verify historical records are retained and unmatched rows appear as unallocated.
2. Open Project Progress with no filters and with only Project. Confirm neither requires Main Area. Confirm a project with no areas shows zero, and submitted historical DPRs appear under the appropriate activity or reconciliation row.
3. Use two BOQ rows with the same item in different disciplines. Submit a DPR against one row; verify only its execution changes. Cancel and amend it; confirm no double counting.
4. Create a draft request from a drawing, then try the revision button. Verify reserved quantities cannot be requested twice. Delete the draft, create/submit a replacement, then cancel it and confirm the balance reopens.
5. Map a request to an order and receipt, then return part of the receipt. Verify row references and net received quantities. Repeat with a purchase UOM conversion.
6. Submit explicit material usage, including a WIP transfer and a material issue. Verify they appear in separate columns. Cancel the DPR/stock entry and confirm both report and counter totals change correctly.
7. Approve a revised BOQ after recording progress/procurement. Confirm original operational totals remain attributed to the same stable activity; removed activities remain visible as retired history.
8. Repeat list/report access as a Projects User with restricted Project permissions. Verify hidden Projects and transactions remain hidden, and missing stock/purchase privileges are reported rather than bypassed.

Local regression checks:

```bash
python -m unittest discover -s tests -v
node --test tests/ui.test.cjs
```
