## Benchmark: `remote:openai/gpt-oss-120b`

**Fixed 17/17** (100%) · first-attempt fixes: 17 · mean attempts when fixed: 1 · median time: 4.5s

| Case | Category | Result | Attempts | Time | Root cause found by the model |
|---|---|---|---|---|---|
| config_wrong_key | wrong key | fixed | 1 | 3s | http_options accesses a non‑existent key 'timeout_seconds' causing KeyError; it should use the 'timeout' key from the config. |
| discount_threshold | boundary condition | fixed | 1 | 3s | The discount function only applies when amount is greater than the threshold, but the spec and tests require it to apply at the threshold (> |
| invoice_decimal_places | formatting | fixed | 1 | 2s | format_amount formats amounts with only one decimal place, causing missing trailing zeros in currency strings |
| leaderboard_order | sort order | fixed | 1 | 3s | rank sorts scores ascending, causing wrong order; should sort by descending score with alphabetical tie-breaking |
| mean_integer_division | arithmetic | fixed | 1 | 3s | mean() uses integer division (//) causing loss of fractional part, leading to incorrect mean values in tests. |
| missing_middle_name | None handling | fixed | 1 | 3s | full_name includes a None middle name in the parts list, causing TypeError when joining |
| mutable_default_cart | shared state | fixed | 1 | 3s | Cart uses a mutable default argument for items, causing all instances to share the same list and leading to state leakage between tests. |
| pagination_off_by_one | off-by-one | fixed | 1 | 4s | Pagination uses 1-indexed pages but calculates start offset as page*size, skipping the first page and returning empty for out-of-range pages |
| port_exception_type | exception contract | fixed | 1 | 12s | parse_port raises generic Exception instead of ValueError for invalid inputs, causing tests expecting ValueError to fail |
| renamed_import | import error | fixed | 1 | 10s | articles.py imports slugify, but textutils defines slugify_text instead, causing ImportError |
| restock_mutates_input | shared state | fixed | 1 | 13s | restock mutates the input stock dict instead of returning a new mapping, causing the original to change |
| retry_attempt_count | off-by-one | fixed | 1 | 12s | The retry loop iterates only attempts-1 times because it uses range(1, attempts), causing premature RetryError and incorrect call count. |
| tax_rate_units | cross-file contract | fixed | 1 | 4s | tax_amount multiplies by the GST percentage directly instead of converting it to a fraction, causing tax values to be 100× too large. |
| weekend_check | boundary condition | fixed | 1 | 16s | is_weekend only treats Sunday as weekend, causing Saturday to be counted as a business day and breaking related functions |
| batch_loop_off_by_one | off-by-one | fixed | 1 | 31s | The sum method skips the last element due to an off‑by‑one loop condition, causing incorrect totals and failing average calculation. |
| free_shipping_boundary | boundary condition | fixed | 1 | 13s | ShippingPolicy.shippingCents uses a strict greater-than check, so an order exactly at the free‑shipping threshold (5000 cents) incorrectly i |
| missing_middle_null | null handling | fixed | 1 | 13s | fullName() throws NullPointerException when a customer's middle name is null because it calls isEmpty() on a null reference. |
