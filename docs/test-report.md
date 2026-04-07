# Template Stress Test Report

## Scope
- Template targets: **56**
- Non-template targets: **5**
- Iterations per target: **100**
- Total runs: **6100**
- Modes cycled per target: **question**, **csv**, **json**
- Execution mode: deterministic offline mocks (`SCRAPERL_DISABLE_LIVE_LLM=1`)

## Aggregate Result
- Completed: **6100**
- Partial: **0**
- Failed: **0**
- Pass rate (completed/total): **100.00%**
- Schema failures: **0**
- Output-format mismatches: **0**
- Duration: **81.16 seconds**

## Per-Template Results
| Template | Runs | Completed | Partial | Failed |
|---|---:|---:|---:|---:|
| `airbnb` | 100 | 100 | 0 | 0 |
| `aliexpress` | 100 | 100 | 0 | 0 |
| `amazon` | 100 | 100 | 0 | 0 |
| `arxiv` | 100 | 100 | 0 | 0 |
| `bbc` | 100 | 100 | 0 | 0 |
| `bitbucket` | 100 | 100 | 0 | 0 |
| `bloomberg` | 100 | 100 | 0 | 0 |
| `booking` | 100 | 100 | 0 | 0 |
| `cnn` | 100 | 100 | 0 | 0 |
| `coindesk` | 100 | 100 | 0 | 0 |
| `coinmarketcap` | 100 | 100 | 0 | 0 |
| `coursera` | 100 | 100 | 0 | 0 |
| `devto` | 100 | 100 | 0 | 0 |
| `ebay` | 100 | 100 | 0 | 0 |
| `edx` | 100 | 100 | 0 | 0 |
| `etsy` | 100 | 100 | 0 | 0 |
| `facebook` | 100 | 100 | 0 | 0 |
| `freecodecamp` | 100 | 100 | 0 | 0 |
| `geeksforgeeks` | 100 | 100 | 0 | 0 |
| `github` | 100 | 100 | 0 | 0 |
| `gitlab` | 100 | 100 | 0 | 0 |
| `glassdoor` | 100 | 100 | 0 | 0 |
| `googlescholar` | 100 | 100 | 0 | 0 |
| `hackernews` | 100 | 100 | 0 | 0 |
| `huggingface` | 100 | 100 | 0 | 0 |
| `imdb` | 100 | 100 | 0 | 0 |
| `indeed` | 100 | 100 | 0 | 0 |
| `instagram` | 100 | 100 | 0 | 0 |
| `investopedia` | 100 | 100 | 0 | 0 |
| `kaggle` | 100 | 100 | 0 | 0 |
| `leetcode` | 100 | 100 | 0 | 0 |
| `linkedin` | 100 | 100 | 0 | 0 |
| `medium` | 100 | 100 | 0 | 0 |
| `npm` | 100 | 100 | 0 | 0 |
| `nytimes` | 100 | 100 | 0 | 0 |
| `openreview` | 100 | 100 | 0 | 0 |
| `paperswithcode` | 100 | 100 | 0 | 0 |
| `pinterest` | 100 | 100 | 0 | 0 |
| `producthunt` | 100 | 100 | 0 | 0 |
| `pypi` | 100 | 100 | 0 | 0 |
| `quora` | 100 | 100 | 0 | 0 |
| `reddit` | 100 | 100 | 0 | 0 |
| `reuters` | 100 | 100 | 0 | 0 |
| `soundcloud` | 100 | 100 | 0 | 0 |
| `spotify` | 100 | 100 | 0 | 0 |
| `stackoverflow` | 100 | 100 | 0 | 0 |
| `substack` | 100 | 100 | 0 | 0 |
| `tiktok` | 100 | 100 | 0 | 0 |
| `twitch` | 100 | 100 | 0 | 0 |
| `udemy` | 100 | 100 | 0 | 0 |
| `vimeo` | 100 | 100 | 0 | 0 |
| `walmart` | 100 | 100 | 0 | 0 |
| `wikipedia` | 100 | 100 | 0 | 0 |
| `x` | 100 | 100 | 0 | 0 |
| `youtube` | 100 | 100 | 0 | 0 |
| `zillow` | 100 | 100 | 0 | 0 |

## Non-Template Results
| Asset | Runs | Completed | Partial | Failed |
|---|---:|---:|---:|---:|
| `https://unknown-synth-alpha.test` | 100 | 100 | 0 | 0 |
| `https://unknown-synth-beta.test` | 100 | 100 | 0 | 0 |
| `https://unknown-synth-gamma.test` | 100 | 100 | 0 | 0 |
| `open source scraping tools benchmark` | 100 | 100 | 0 | 0 |
| `synthetic market intelligence dashboard comparison` | 100 | 100 | 0 | 0 |

## Failure Samples
- No failures captured.

## Notes
- Templates are used as **reference hints** (navigation targets/field hints), not rigid scraper scripts.
- Agent flow evaluates **assets + instructions + output_format + output_instructions** per request.
- Output schema validation checks strict column adherence for CSV/JSON runs.
- Raw machine summary: `docs/reports/template-stress-summary.json`.

---

## Additional Run: Non-Template Existing Domains (Question/CSV/JSON)

- Target domains: **35** (non-template existing sites)
- Output modes: **question**, **csv**, **json**
- Total cases: **105** (35 × 3)
- Completed: **105**
- Partial: **0**
- Failed: **0**
- Schema failures: **0**
- Output-format mismatches: **0**
- Duration: **1.8 seconds** (deterministic offline fixture mode)

Raw summary: `docs/reports/non-template-existing-summary.json`.
