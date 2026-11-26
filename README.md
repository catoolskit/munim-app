# munim-app

## v0.20 release notes

- GST registration is enforced by the billing engine for sales and mobile invoice imports.
- Sales invoice footer is split into entry controls and a dedicated status/action row.
- First-time company setup is surfaced on Gateway and in Quick Actions.
- Company Backup / Restore exports a versioned portable JSON backup; a guided repair corrects affected sales invoices already saved with GST while the company is unregistered. Company deletion creates a recovery JSON under `MUNIM/Deleted companies` before removing the company.
- The transaction menu uses one Sales Invoice flow; invoice printing chooses Tax Invoice or Retail Invoice from company GST registration.
