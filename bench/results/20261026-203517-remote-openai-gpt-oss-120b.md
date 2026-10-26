## Benchmark: `remote:openai/gpt-oss-120b`

**Fixed 2/2** (100%) · first-attempt fixes: 2 · mean attempts when fixed: 1 · median time: 2.8s

| Case | Category | Result | Attempts | Time | Root cause found by the model |
|---|---|---|---|---|---|
| pagination_off_by_one | off-by-one | fixed | 1 | 3s | The pagination start index is calculated as page * size, causing the first page to skip items and the last page to be empty; it should offse |
| tax_rate_units | cross-file contract | fixed | 1 | 2s | tax_amount multiplies by the GST percentage directly instead of converting it to a decimal, causing tax values to be 100x too large. |
