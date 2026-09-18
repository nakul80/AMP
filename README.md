# AMP — App for Managing Projects

A Frappe / ERPNext construction and engineering app for drawing BOQs, procurement and daily site execution. AMP extends ERPNext's existing **Project** master with custom Main Areas, Sub Areas, drawings and reports.

## Features

- Drawing register, attachments, disciplines, GFC revisions and revision quantity comparisons.
- Stable BOQ-line references across revisions, including repeated item codes.
- Material budget = estimated quantity × (1 + wastage %). Draft and submitted Material Requests share one drawing budget, enforced server-side.
- Procurement references carried from Material Request rows to Purchase Order and Purchase Receipt rows; transaction events rebuild drawing counters.
- Daily Progress Reports with contractor, weather, photographs, actual work quantities and explicit material usage. Optional stock issue or transfer to WIP uses normal ERPNext stock permissions.
- Structural activities record fabrication and erection separately. Their configurable stage weights (50% / 50% by default) produce one combined physical completion without adding the same steelwork twice.
- Keyboard-friendly Site Progress Quick Entry with a direct link to the submitted DPR. DPR list shortcuts clear stale filters or show submitted records.
- **Project Progress Summary:** all projects or a selected project, optional Main Area/Sub Area/Drawing, date filters, weighted physical completion and DPR drill-down.
- **Project Material Status:** draft requests, submitted requests, orders, net receipts, WIP transfers, stock issues and separately reported material usage, with source-document links.

Physical completion excludes procurement wastage and uses configurable activity weights (default: equal weight per BOQ activity), rather than adding incompatible units. Reports use the current approved BOQ and submitted transactions. Unallocated legacy records are identified instead of being guessed into drawings. The material report is a quantity-status report; it does not implement activity-to-material BOM consumption norms or cost forecasting.

## Installation

ERPNext must already be installed on the site.

```bash
bench get-app <your-amp-repository-url>
bench --site SITE install-app amp
bench --site SITE migrate
bench build --app amp
```

### Frappe Cloud

1. Push this revision to the GitHub repository connected to Frappe Cloud.
2. In the private Bench Group, open **Apps → Add App → Add from GitHub** and select the AMP repository. Ensure the Frappe Cloud GitHub App has access to that repository.
3. Select **Update Available**, choose the target site, then use **Deploy and Update**. Frappe Cloud fetches the repository and runs the migration as part of this deploy.
4. When the deploy succeeds, open the site's **Apps** tab and select **Install App → AMP** if this is the first AMP installation. For an existing AMP installation, do not reinstall it.
5. Hard-refresh the Desk browser tab, then open **AMP → Project Progress Summary** and verify the new fabrication and erection columns.

Use a staging site first when existing DPRs, drawing revisions, stock entries, or procurement records are present. Do not run `bench` commands on a Frappe Cloud production site; use the Bench Group and Site dashboard instead.

For an existing installation, deploy the code and run `bench --site SITE migrate`, `bench build --app amp`, and `bench --site SITE clear-cache`.

See [report definitions, migration behavior and site verification](docs/reporting-and-upgrade.md) before upgrading existing records. The guide also includes a read-only diagnostic for a DPR count/list visibility mismatch.

## Local checks

```bash
python -m unittest discover -s tests -v
node --test tests/ui.test.cjs
```

These regression tests use in-memory adapters/mocks; validate migration, document lifecycle, permissions and stock posting on a Frappe/ERPNext test site. ERPNext v16 is the intended deployment target; local tests are not a framework compatibility certification.

## License

MIT
