# Browser QA

Browser QA uses Playwright against the built dashboard and a local Vite preview server.

```powershell
npm run qa:browser
npm run qa:screenshots
```

The test mocks backend API responses in the browser. It does not require Northflank, Neon, Redis, Backblaze, Supabase, TDLib, or cloud secrets.

Covered pages:

- SaaS shell / Accounts
- Health Center
- Jobs
- Proxy Center
- Settings
- Mobile Health Center shell

Screenshots are saved as Playwright test artifacts under ignored `test-results/playwright`. HTML reports are saved under ignored `playwright-report`.

Do not commit generated screenshots or Playwright artifacts unless a future PR intentionally introduces stable visual snapshots.
