# Skill: draw a chart or diagram with Mermaid

Use this skill only when the learner asks for a chart, graph, plot, diagram,
figure, timeline or flow. Written for CrocoCash from the Mermaid documentation
(mermaid.js.org). The app checks and renders the code; never show raw code.

## Output
Return JSON: {"text": "<one or two short sentences explaining the picture>", "mermaid": "<Mermaid code>"}.
- "mermaid" holds only Mermaid code: no ``` fences, no comments, no HTML.
- Pick ONE diagram type from the list below. Start with its keyword on line 1.
- Keep it small: at most 12 data points, 10 nodes, 6 pie slices.
- Labels in plain English, under 30 characters. Use only letters, digits,
  spaces, %, zł, -, and periods inside labels. Put labels with spaces in double quotes.
- Numbers are illustrative unless they come from the lesson or the question context.
  Say so in "text" (for example: "Example numbers, not a forecast.").
- Never draw a chart that recommends a product, predicts a price, or shows a
  specific stock, fund or ticker.

## Line or bar chart: xychart-beta
xychart-beta
    title "Savings with 5% a year"
    x-axis [2026, 2027, 2028, 2029, 2030]
    y-axis "zł" 0 --> 1300
    line [1000, 1050, 1103, 1158, 1216]

- Use `bar [...]` instead of `line [...]` for a bar chart. Both may appear once each.
- The number of values must equal the number of x-axis labels.
- y-axis range must cover every value.

## Share of a whole: pie
pie title "Example 60/40 mix"
    "Shares" : 60
    "Bonds" : 40

## Steps, choices or cause and effect: flowchart
flowchart TD
    A["Unexpected bill"] --> B{"Emergency fund?"}
    B -->|Yes| C["Pay from the fund"]
    B -->|No| D["Costly borrowing"]

- Node ids are single letters or words without spaces; the label goes in quotes.
- Use TD (top-down) for steps, LR (left-right) for timelines.

## Events over time: timeline
timeline
    title "A 12-year plan"
    2026 : Start monthly saving
    2030 : Review the mix
    2038 : Goal reached

## Forbidden
click, call, href, javascript:, %%{init}, style/classDef with url(), <script>, <br> or any HTML.
