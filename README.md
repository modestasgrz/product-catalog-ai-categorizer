# product-catalog-ai-categorizer

A marketplace team gets partner listing exports as CSV files: thousands of rows of messy, multi-language text (Lithuanian, Latvian, Polish, English, often mixed), and someone has to put every listing into the right category by hand.

This CLI does that step with Claude. Every row gets a category from the marketplace's tree, a link, a confidence and a one-sentence reason. Rows it can't place confidently are never silently guessed. They go to a review queue with the reason why.

A demo of a multi-language catalog categorizer. Everything in this repo runs on generated mock data for a fictional marketplace, **Elkwood Experiences** (experience gifts, 40 categories).

## Usage

```bash
uv sync
export ANTHROPIC_API_KEY=...            # read from the environment, never stored
uv run categorize data/listings.csv --out-dir out/
```

| Flag | Default | What it does |
| --- | --- | --- |
| `--tree` | `data/category_tree.json` | category tree (JSON) |
| `--out-dir` | the input's folder | where the three output files go |
| `--concurrency` | `8` | parallel model calls (1–32) |
| `--threshold` | `0.70` | confidence below this goes to review |
| `--limit` | all rows | classify only the first N rows (cheap test runs) |
| `--model` | `claude-sonnet-5-5` | Claude model |

Input: any CSV with `title`, `description` and `location` columns (matched case- and space-insensitively). All other columns are kept. The file can be UTF-8 (with or without BOM), cp1257 (Baltic Windows exports) or latin1, delimited by `,` or `;`.

Exit codes: `0` done (even if some rows failed: those rows are flagged), `2` bad input or config (missing key, missing columns, bad tree, bad flag), `3` the API key was rejected (the rows already finished stay written).

Score a run against the answer key:

```bash
uv run python -m categorizer.evaluate out/listings_categorized.csv data/gold.csv --out out/eval_report.json
```

## Output columns

Three files land in `--out-dir`:

- `<name>_categorized.csv`: every input row, with these columns first and the original columns after them, unchanged:

| Column | Meaning |
| --- | --- |
| `status` | `ok` (confident), `review` (confidence below threshold), `unknown` (nothing in the tree fits, or the row is empty), `error` (the model call failed after retries, or returned something invalid) |
| `category_name` | category name from the tree (empty for unknown/error) |
| `confidence` | 0.00–1.00 |
| `reason` | one sentence from the model naming the runner-up, or the failure reason (`model call failed: RateLimitError 429`, `invalid model output`, `model refused`, `empty title and description`) |
| `category_id` | tree id, or `unknown` |
| `category_url` | link to the category page |

- `<name>_review.csv`: only the `review`, `unknown` and `error` rows. This is the human's queue.
- `<name>_run_report.json`: row counts per status, tokens (incl. prompt-cache reads), estimated cost in USD, duration, encoding detected.

How it stays reliable:
- Each row is classified on its own, in parallel. One failed row never stops the run.
- The SDK retries rate limits, 5xx and overload errors with backoff (6 retries, 60 s timeout). An answer that doesn't fit the schema or names a category outside the tree is asked once more, then flagged.
- Results are written every 50 rows, so a crash keeps what was done.
- Listing text reaches the model only inside an escaped `<listing>` block, and the model's answer is validated against a schema and the tree before it is used.
- The category list sits in a cached system prompt.

## How the answer key was made

1. **Category tree:** `data/category_tree.json`, 6 groups and 40 categories, written by hand.
2. **Base listings:** `data/base_listings.csv`, 200 listings written by hand: 50 each in Lithuanian, Latvian, Polish and English. 160 are clear cases (4 per category), 20 are things the marketplace doesn't sell (tyre change, phone repair, a bare "gift voucher"…) whose correct answer is `unknown`, and 20 are packages that honestly fit two categories (e.g. a dinner cruise). Each carries its intended category.
3. **Messy listings:** `tools/generate_listings.py --seed 42` turns every base listing into 5 variants. Most of the four extra variants get 1–2 kinds of mess: typos, stripped diacritics, empty description or location, a phrase in another language, HTML leftovers, ALL CAPS titles, cut-off descriptions. On top of that, 6 rows have title and description emptied, and 2 rows carry a prompt-injection sentence telling the model to pick a specific category. The result is `data/listings.csv` (1,000 rows), `data/listings_legacy_cp1257.csv` (40 rows, Baltic encoding, `;`) and the generator's labels in `data/labels.csv`.
4. **Sample:** `tools/sample_gold.py --seed 42` draws 100 rows from `listings.csv`: both injection rows, 8 two-category rows, 6 unknown rows and 84 random ones.
5. **Blind re-label:** a fresh Claude Opus agent, with no access to the generator labels, labelled the same 100 rows seeing only the tree and each row's title, description and location. It agreed with the generator on 99 of 100.
6. **Settling:** the disagreement was settled by the build's reviewer (a Claude agent acting for the owner) and is marked `source=settled` with a one-line note in `data/gold.csv`. All other rows are `source=generator`.

Limits of this key:
- The listings are generated, and whoever wrote them also wrote the tree, so real partner exports will be messier in ways this set doesn't cover.
- The 100 rows are variants of 79 distinct base listings, so a few base listings count more than once.
- Rows with an empty title and description are marked `unknown` without a model call, so they are always scored correct.
- Two-category rows accept either id.

## Results

Pending: filled in from the first full run on `data/listings.csv` (`out/listings_run_report.json` + `out/eval_report.json`). No number is shown here until that run exists.

## Known limits

- **Refusals:** the SDK's structured-output helper validates the model's JSON inside the call. If the model refuses with plain text, the call fails validation before the refusal itself can be read. The row then ends as `invalid model output` after one extra call, not as `model refused`, and that call's tokens aren't counted in the cost estimate. Refusals on gift listings are expected to be near zero.
- One category per row (two-category packages get the closer one; the answer key accepts both).
- The cost in the run report is an estimate from token counts and list prices, not a bill.
- Cells that would start a spreadsheet formula are guarded only in the model-written `reason`. Input cells are passed through unchanged.

## Development

```bash
make check   # ruff, mypy (strict), security scans, unit + security tests
make test    # unit + security tests
uv run pytest tests/acceptance/product-catalog-categorizer   # acceptance tests (spec ACs)
```

Spec with acceptance criteria and locked decisions: `specs/product-catalog-categorizer.md`. Tests never call the API: the Anthropic client is faked.
