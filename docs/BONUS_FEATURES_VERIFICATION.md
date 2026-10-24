# Bonus feature verification

Verified locally on 2026-10-24.

## Implemented

- Scoped 30/60/90-day cost forecast, daily sensitivity range, allocated/busy usage estimates.
- Local-time shutdown simulator with environment, hour, weekday and demand controls.
- In-app usage anomaly, cost increase, capacity and horizon-budget alerts.
- Qwen explanations for scenarios and scoped recommendations, with labeled rule fallback.
- Scoped Markdown reports, JSON evidence, and provider-neutral Terraform handoff.
- Adjustable energy and carbon estimates.
- Engineer, Finance and Leadership presentation views, plus existing estate filters.

## Verification evidence

- Full backend suite: 64 tests passed before the final upcoming-date regression was added.
- Monitoring tests after date correction: 17 passed.
- Additional regression: 1 passed; proves equal daily billing across different month lengths
  does not create false cost growth and forecasts start after today.
- Frontend TypeScript and Vite production build: passed.
- `git diff --check`: passed.
- Live deployed forecast: 90 points from **2026-10-25 to 2027-01-22**, using evidence
  through 2026-08-31. A horizon budget of INR 1 generated a budget-overrun alert.
- Live deployed explanation endpoint: returned `source=qwen` using existing environment
  credentials; credentials and provider responses were not logged.
- Exported Terraform handoff: `terraform validate -json` returned `valid=true`.
- Browser: selected and ran 90 days, confirmed upcoming dates, inspected cards/chart.
  Preview: [monitoring-forecast.png](monitoring-forecast.png).

## Product limits

Historical billing remains synthetic; unknown prices are excluded. Cost avoidance requires
prorated billing and may not reduce quarterly commitments. Energy/carbon values are
scenario estimates. Alerts reevaluate every minute while the page is open. Role choices
are presentation preferences, not authentication or tenant isolation. Terraform exports
are reviewed metadata handoffs requiring verified provider scheduler wiring.
