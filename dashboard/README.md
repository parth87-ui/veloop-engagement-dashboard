# VELOOP Rewards — User Behavior & Engagement Intelligence Dashboard

**Prepared by:** Parth Khandelwal · VELOOP Rewards Data Analyst Task 02

🔗 **Live dashboard:** https://veloop-data-analyst-task02.vercel.app/

> **Simulated data – not actual VELoop Rewards user data.** The dashboard uses the fictional dataset provided for this task.
> Figures demonstrate the method and findings; they do not represent real users, retention or business performance.

## What the dashboard contains

| Section | What you can see |
|---|---|
| **Overview** | Key numbers (users, activation, return, task completion), daily active users, the user journey and key findings |
| **User Behaviour** | Active users over time, how often users visit, session length, active days and user groups |
| **Features** | Which features are used and completed, which ones users come back to, where attempts are lost, and task results |
| **Retention** | Next-day, first-week, second-week and fourth-week return, weekly retention curve and return by month joined |
| **Insights & Actions** | Where users drop off, the biggest problems found, and recommended actions with how to test them and what success looks like |

**Filters:** acquisition source, device, user group, feature and date range. Every metric has an ⓘ tooltip explaining it.
Panels marked *Overall* show all users and are not changed by the filters.

The full data-quality review, anomaly checks, methodology and source code are in the project repository and the report.

## Accuracy checks

The numbers are produced by the analysis pipeline in this repository (`../analysis`). Automated tests confirm that:

- with no filters, every KPI, the funnel and the return rates equal the pipeline outputs (`src/lib/metrics.test.ts`);
- for every single filter value (each source, device, segment and feature) and two date windows, the dashboard's
  calculations equal values computed independently with pandas (`src/lib/filters.test.ts`, 35 cases).

## Data privacy

The dashboard loads only aggregated and identifier-free data (`public/data/`). No names, email addresses or other
personal details are included.

## Run locally

Requires Node.js 18 or later. From this `dashboard/` folder:

```bash
npm install
npm run dev
```

```bash
npm test
```

## Deploy on Vercel

Import the repository in Vercel and set **Root Directory = `dashboard`**. Framework (Vite), build command and output
directory are detected automatically (`vercel.json`).

Built with React · TypeScript · Vite · Tailwind CSS · Recharts.
