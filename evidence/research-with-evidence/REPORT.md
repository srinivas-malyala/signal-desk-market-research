# Signal Desk — “01 Research with evidence” test report

Tested on 2026-10-03 through the deployed frontend at `https://signal-desk-frontend-s88i.onrender.com/`.

- Authenticated user: `malyalasrinivas@gmail.com`
- Workflows discovered: 3
- Workflows returning a result: 1 of 3
- Workflows satisfying the advertised evidence behavior (source plus as-of date or source links): 0 of 3
- Visual evidence: captured in the browser-testing transcript for each workflow state

## 1. Ticker performance — failed

Input:

- Ticker: `AAPL`
- Calendar-day lookback: `30`

Observed result:

> The research request could not be completed. Request ID: 7e83f169-2d56-4713-9b44-544996795417

The result panel also displayed “No result was presented” and instructed the user to retry when the dependency is available.

Expected: a bounded performance result with source and as-of date.

## 2. Peer comparison — result returned, evidence incomplete

Input:

- Tickers: `AAPL, MSFT`
- Calendar-day lookback: `30`

Observed result:

| Ticker | Return | Last price | As-of date | Displayed range |
|---|---:|---:|---|---|
| AAPL | -3.92% | $315.34 | 2026-09-09 | $309.90–$330.81 |
| MSFT | -3.62% | $491.65 | 2026-09-09 | $489.80–$515.65 |

The workflow executed successfully and displayed an as-of date, but it did not display a source/provider or a source link. This does not fully meet the page statement that market claims include their source and as-of date.

## 3. Filing and news evidence — failed

Input:

- Ticker: `AAPL`
- Research question: `What evidence supports the services growth thesis?`
- Source type: `Filings and articles`

Observed result:

> The research service is temporarily unavailable. Request ID: f5386204-293c-40eb-9957-93c990303ca1

The result panel also displayed “No result was presented,” so no filing/article citations or links were available for verification.

Expected: narrative matches linking back to filings or articles.

## Additional observations

- The signed-in identity was visible and correct throughout the test.
- The browser console exposed no warning or error messages during these runs.
- The page’s usage analytics independently showed an agent error rate of 22.2% across 9 invocations, but this is stale processed data and is not direct evidence of the three test calls above.
- The visible Workflow label is not discoverable as an associated HTML label by role/label automation, even though the accessibility tree infers a name. Associating the `<label>` and `<select>` explicitly would improve testability and accessibility.

## Recommended defect priority

1. Restore the ticker-performance dependency and trace request `7e83f169-2d56-4713-9b44-544996795417`.
2. Restore semantic evidence retrieval and trace request `f5386204-293c-40eb-9957-93c990303ca1`.
3. Add the promised source/provider or link to peer-comparison market claims.
4. Add explicit `for`/`id` label associations for the research controls.
