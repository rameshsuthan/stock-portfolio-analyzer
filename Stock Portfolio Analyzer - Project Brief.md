# Stock Portfolio Analyzer — Path A Project Brief

This document scopes the Week 1 stock portfolio project and provides input for a detailed development plan. It does not implement the application. Requirements from the course handout are distinguished from proposed product choices below.

Source: [Week 1 Project Handout (Oct 2026)](Week%201%20Project%20Handout%20%28Oct%202026%29.md).

## 1. Project overview

Build an interactive application that turns a stock holdings CSV into an understandable portfolio dashboard. A user should be able to inspect portfolio value, unrealized gains and losses, individual holdings, and allocation across stocks and sectors.

Use an AI coding assistant to develop the application through small, reviewable iterations. Record prompts, screenshots, fixes, and observations along the way so the development process can be included in the course submission.

**Target user:** An individual who has a CSV of stock holdings and wants to explore their portfolio without writing analysis code.

**Core user journey:** Open the app → load sample data or upload a CSV → review validation results → explore metrics, charts, and holdings → filter the portfolio → export the current analysis.

## 2. Requirements from the handout

- The selected project is **Path A: Build a Stock Portfolio Analyzer**.
- Build a working data application that analyzes and visualizes a dataset using an AI-assisted development workflow.
- Streamlit with CSV data is the recommended starting point; alternative frameworks and datasets are permitted.
- Iterate on the application using prompts, visualizations, filters, and UX improvements. AI-powered interactions or summaries are optional.
- Document the project and development process, including screenshots, prompts, iterations, and learnings.
- Submit project documentation, a working video demo of five minutes or less, and a GitHub repository link.

The handout does **not** specify mandatory stock metrics, CSV columns, dashboard sections, or a deployment target. The remaining product and technical details in this brief are proposed defaults to make development planning concrete.

**Dataset gap:** The handout contains a placeholder CSV download link, and no stock CSV accompanies it in this workspace. Plan to create a small synthetic sample dataset and support user uploads. Reconcile the proposed schema with the actual dataset if one becomes available.

## 3. Proposed MVP scope

The first version analyzes a single portfolio snapshot in one currency. Prices come from the supplied CSV. This keeps the application self-contained and makes the results reproducible for the demo.

| Feature | Expected behavior |
| --- | --- |
| Sample portfolio | Load a bundled synthetic CSV so the app can be explored immediately. |
| CSV upload | Accept a holdings CSV and explain required columns before upload. |
| Data validation | Identify missing columns, invalid values, and duplicate holdings with useful error messages. |
| Portfolio overview | Show cost basis, market value, unrealized gain/loss, unrealized gain/loss percentage, and holding count. |
| Holdings analysis | Show a sortable table with input values and calculated metrics for each holding. |
| Allocation analysis | Show market-value allocation by stock and, when supplied, sector. |
| Gain/loss comparison | Compare holdings using a bar chart of unrealized gain/loss amounts. |
| Shared filters | Filter by symbol and sector; update all metrics, charts, the table, and export consistently. |
| CSV export | Download the currently filtered holdings with their calculated metrics. |
| Clear UI states | Explain invalid uploads, unavailable sector information, empty filters, and undefined calculations. |

### Questions the MVP should answer

- What is the portfolio's total cost basis and current value according to the uploaded prices?
- Which holdings have the largest unrealized gains or losses?
- What share of portfolio value is allocated to each stock or sector?
- Which holding or sector has the largest allocation?
- How do the metrics change when only selected holdings or sectors are included?

### Outside the MVP

- Live market prices, brokerage connections, and automatic price refreshes.
- Transaction history, realized gains, tax calculations, dividends, and cash balances.
- Historical performance, benchmark comparison, volatility, and other metrics requiring time-series data.
- Multiple currencies, currency conversion, short positions, and derivatives.
- Accounts, saved portfolios, databases, and multi-user collaboration.
- Trading, buy/sell recommendations, and automated portfolio changes.
- LLM-generated commentary or conversational analysis; these may be considered after the core app works.

## 4. Proposed CSV data contract

Each row represents one stock holding. The MVP accepts one row per symbol and expects any multiple purchase lots to be consolidated before upload.

| Column | Required | Meaning and validation |
| --- | --- | --- |
| `symbol` | Yes | Nonempty stock identifier; trim surrounding whitespace and normalize to uppercase. Must be unique after normalization. |
| `quantity` | Yes | Numeric share count greater than zero; fractional shares are allowed. |
| `average_cost` | Yes | Numeric average acquisition cost per share, greater than or equal to zero. |
| `current_price` | Yes | Numeric price per share supplied for this snapshot, greater than or equal to zero. |
| `company_name` | No | Display name; use the symbol when absent or blank. |
| `sector` | No | Sector label; group missing or blank values under `Unknown`. |

### Dataset-level assumptions

- All monetary values use one currency. Default to USD with a visible label; do not infer currency or perform conversions.
- Accept an optional user-entered snapshot date and display it when provided. Otherwise, show `Snapshot date not provided`.
- Describe values as based on uploaded prices; do not imply the prices are live.
- The average cost is supplied by the user or dataset; the app does not calculate it from trades.
- Use plain numeric values such as `1250.50`, without currency symbols or thousands separators.
- Ignore extra columns for the MVP and explain that they are not included in the analysis.
- Trim column-header whitespace and normalize headers to lowercase. Do not silently guess aliases for missing required columns.
- Reject missing, nonnumeric, or nonfinite required numeric values. Do not convert invalid values to zero.
- Report duplicate symbols and affected rows rather than silently discarding or combining holdings.
- Block analysis of an invalid upload until corrected; do not silently analyze only the valid rows.

### Synthetic example

These identifiers and values are fictional and intended for demonstration and verification.

```csv
symbol,company_name,sector,quantity,average_cost,current_price
DEMO_A,Demo Company A,Technology,10,100,120
DEMO_B,Demo Company B,Healthcare,5,200,180
```

The full bundled demo dataset can include more holdings and sectors, but this small example provides an easy calculation check.

## 5. Calculation definitions

Use these definitions consistently across the summary, charts, table, and export.

| Metric | Definition |
| --- | --- |
| Holding cost basis | `quantity × average_cost` |
| Holding market value | `quantity × current_price` |
| Holding unrealized gain/loss | `market_value − cost_basis` |
| Holding unrealized gain/loss % | `(unrealized_gain_loss ÷ cost_basis) × 100` when cost basis is positive |
| Portfolio cost basis | Sum of holding cost bases in the active selection |
| Portfolio market value | Sum of holding market values in the active selection |
| Portfolio unrealized gain/loss | `portfolio_market_value − portfolio_cost_basis` |
| Portfolio unrealized gain/loss % | `(portfolio_unrealized_gain_loss ÷ portfolio_cost_basis) × 100` when total cost basis is positive |
| Holding allocation % | `(holding_market_value ÷ portfolio_market_value) × 100` when selected portfolio value is positive |
| Sector allocation % | `(sector_market_value ÷ portfolio_market_value) × 100` when selected portfolio value is positive |
| Holding count | Count of holdings in the active selection |

### Calculation and presentation rules

- Calculate portfolio gain/loss percentage from portfolio totals, not by averaging holding percentages.
- Use unrounded values for calculations; format displayed amounts to two decimal places and percentages to two decimal places.
- Show undefined percentages as `N/A` when their denominator is zero. Never display infinity or silently substitute zero.
- If every selected holding has zero market value, explain that allocation percentages are unavailable and omit the allocation chart.
- Label the price-based change as **unrealized gain/loss**, not annualized return or total investment return.
- When filters are active, label summary metrics and allocation percentages as applying to the selected holdings.
- Show positive and negative values with signs or text in addition to color.

For the two-row synthetic example, expect a cost basis of **$2,000.00**, market value of **$2,100.00**, unrealized gain of **$100.00**, and unrealized gain percentage of **5.00%**. Stock allocations should display as **57.14%** and **42.86%**.

## 6. Proposed interface

### Data and filters

- Provide a clear choice between the sample portfolio and an uploaded CSV.
- Show the required schema and provide access to sample data.
- Display the currency, optional snapshot date, loaded holding count, and validation status.
- Provide symbol and sector selection controls plus a reset action.
- Default to all holdings selected. Combine symbol and sector filters using intersection.
- Reset filters when the underlying dataset changes so stale selections do not hide new data.

### Portfolio overview

- Place the five headline metrics near the top of the dashboard.
- Show allocation by stock and sector with visible values or tooltips.
- Show an unrealized gain/loss bar chart with a clear zero baseline.
- Provide an empty-state message when filters produce no holdings.

### Holdings table and export

- Include symbol, company name, sector, quantity, average cost, current price, cost basis, market value, unrealized gain/loss, gain/loss percentage, and allocation percentage.
- Support sorting so users can inspect the largest positions and gains or losses.
- Export the same filtered holdings and calculated values shown in the dashboard, with numeric fields preserved as numbers.
- Disable export when there are no valid selected holdings.

## 7. Suggested implementation approach

**Proposed stack:** Python, Streamlit, pandas, and Plotly. Streamlit and CSV follow the handout's recommendation; pandas and Plotly are proposed supporting libraries.

Start with a local application and a bundled CSV. Keep upload parsing, validation, and portfolio calculations separate from UI rendering so that calculations can be checked independently.

The development plan should define a small project structure covering:

- Application entry point and dashboard rendering.
- CSV parsing and schema validation.
- Portfolio calculations and filtered aggregation.
- Synthetic sample data.
- Focused checks for calculations, validation, and filter behavior.
- Dependency specification and reproducible local run instructions.
- Project README and evidence of the AI-assisted development process.

A hosted demo is optional unless a deployment target is chosen during planning. A working local demo can support the required screen recording.

## 8. Development planning workstreams

Expand these workstreams into concrete tasks, dependencies, affected files, and completion checks.

| Order | Workstream | Expected result |
| --- | --- | --- |
| 1 | Confirm scope and data | Agree on the snapshot model, column names, currency, and sample dataset. |
| 2 | Create the app foundation | Establish the environment, project structure, and a runnable Streamlit shell. |
| 3 | Load and validate data | Support sample data and uploads, including useful validation messages. |
| 4 | Implement calculations | Produce correct holding metrics and portfolio totals using the agreed formulas. |
| 5 | Build the dashboard | Add summary metrics, allocation charts, gain/loss comparison, and the holdings table. |
| 6 | Connect filters and export | Make every view and downloaded CSV reflect the same active selection. |
| 7 | Verify and refine | Check important edge cases, improve labels and empty states, and confirm setup instructions work. |
| 8 | Prepare the submission | Complete documentation, capture the working demo, and publish the code repository. |

### AI-assisted workflow

For each meaningful iteration, describe the desired behavior, request a focused change, inspect the result, run the relevant checks, and record what changed.

Keep a lightweight development log containing:

- The prompt and intended outcome.
- What the coding assistant produced.
- Any observed bug or unexpected behavior.
- The follow-up prompt or manual adjustment.
- A screenshot or verification result where useful.
- A short observation about what worked or what was learned.

## 9. MVP acceptance criteria

- [ ] The documented setup instructions launch the application successfully.
- [ ] The bundled sample portfolio loads without external services or API keys.
- [ ] A valid CSV matching the agreed schema produces the expected analysis.
- [ ] The two-row example produces the exact totals and displayed percentages listed above.
- [ ] Filtering to `DEMO_A` shows a $1,000.00 cost basis, $1,200.00 market value, $200.00 unrealized gain, 20.00% gain, and 100.00% allocation.
- [ ] Portfolio percentage calculations use aggregate cost basis rather than an average of holding percentages.
- [ ] Missing columns, empty files, malformed CSVs, duplicate symbols, missing numeric values, negative prices, nonpositive quantities, and nonfinite values produce useful errors without crashing the app.
- [ ] A zero cost basis preserves monetary calculations and displays undefined gain/loss percentages as `N/A`.
- [ ] Missing sector values are represented as `Unknown` without losing holdings.
- [ ] Zero portfolio market value and empty filter results have clear UI states.
- [ ] Shared filters update the summary, charts, table, and export consistently.
- [ ] Uploading a different dataset resets stale filter selections.
- [ ] Exported values match the active selection and contain the calculated fields.
- [ ] Currency, price source, and snapshot-date status are visible.
- [ ] The working application and AI-assisted development process can be demonstrated in five minutes or less.

## 10. Decisions for the detailed development plan

The defaults below allow planning to proceed; revise them if the real dataset or project preferences differ.

| Decision | Proposed default |
| --- | --- |
| Dataset | Synthetic sample CSV plus user uploads; replace or adapt if the course CSV becomes available. |
| Portfolio model | One snapshot, one row per symbol, positive share quantities, one currency. |
| Cost basis input | User-supplied average cost per share. |
| Currency | USD, explicitly labeled throughout the app. |
| Price freshness | Uploaded snapshot prices; optional manually supplied snapshot date. |
| Framework | Streamlit with pandas and Plotly. |
| Initial execution | Local development and demo; decide separately whether to host. |
| AI functionality | AI assists development; an in-app AI feature is optional future work. |
| Repository destination | Select the GitHub repository when preparing the code submission. |

## 11. Course submission checklist

- **Project documentation:** A Google Doc explaining the stock portfolio analyzer, dataset, prompts, iterations, screenshots, and lessons learned.
- **Video demo:** A recording of five minutes or less that explains the app, describes the use of AI coding tools, and demonstrates the working result.
- **Code:** Upload the project code to GitHub and submit the repository link.
- **Submission form:** [Week 1 project submission](https://forms.gle/VpQz7ZnsgL1bYRqv6).
- **Handout deadline:** Sunday, October 11, 2026, at 11:59 p.m. Pacific Time for Builder of the Week consideration. The handout permits later submissions through the same form.

The handout encourages independent development and reserves the solution kit for situations where progress is blocked. It also states that replicated solutions will not receive scores. This brief is based on the handout; the solution kit has not been consulted.

## 12. Prompt to create the detailed development plan

> Use this Stock Portfolio Analyzer project brief to create a detailed development plan for the Path A MVP. Preserve the distinction between course requirements and proposed defaults. Inspect any available repository files and sample data before planning. Identify unresolved assumptions, then organize the work into small implementation milestones with dependencies, file responsibilities, acceptance checks, and expected outputs. Include focused verification for portfolio calculations, CSV validation, filter consistency, and export accuracy. Include the README, development evidence, and course submission deliverables. Keep the MVP limited to a single-currency portfolio snapshot; place optional features in a separate future-work section. Produce the plan before beginning implementation.
