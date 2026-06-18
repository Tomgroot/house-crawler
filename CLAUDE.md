# House Crawler — Claude Agent Instructions

## Visual PR screenshots

Whenever you create a PR that includes a visual change to the Streamlit dashboard
(any edit touching `app.py`, `analysis/charts.py`, or other UI files), you **must**
also update `.github/screenshot_target.json` in the same commit.

Set `"path"` to the Streamlit page most relevant to the change:

| Page | `path` value |
|---|---|
| Dashboard (default) | `""` |
| Neighborhoods chart | `""` (sidebar nav, same URL) |
| Any page | `""` |

Optionally set `"selector"` to a CSS selector to capture only a specific element,
or set `"full_page": false` to capture only the viewport.

Example for a dashboard change:

```json
{
  "path": "",
  "full_page": true
}
```

Example targeting a specific chart element:

```json
{
  "path": "",
  "selector": ".stPlotlyChart",
  "full_page": false
}
```

The CI workflow (`.github/workflows/visual-confirmation.yml`) will automatically
start the app, run `scripts/take_screenshot.py`, and post the screenshot as a PR
comment so reviewers can verify the visual result.
