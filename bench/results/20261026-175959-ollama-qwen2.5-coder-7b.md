## Benchmark: `ollama:qwen2.5-coder:7b`

**Fixed 7/14** (50%) · first-attempt fixes: 7 · mean attempts when fixed: 1 · median time: 154.8s

| Case | Category | Result | Attempts | Time | Root cause found by the model |
|---|---|---|---|---|---|
| config_wrong_key | wrong key | fixed | 1 | 102s | The `http_options` function expects a 'timeout_seconds' key in the configuration dictionary, but it should be 'timeout'. |
| discount_threshold | boundary condition | not fixed | 3 | 265s | The `discount` function is not correctly calculating the discount for orders of $1000 or more. |
| invoice_decimal_places | formatting | fixed | 1 | 141s | The `format_amount` function is rounding to one decimal place, but the tests expect two decimal places. |
| leaderboard_order | sort order | not fixed | 3 | 411s | The `top` function is returning player names instead of a list of dictionaries with rank, player, and score. |
| mean_integer_division | arithmetic | fixed | 1 | 136s | The `mean` function is using integer division (`//`), which truncates the decimal part, causing it to return an incorrect result. |
| missing_middle_name | None handling | not fixed | 3 | 549s | The backslash at the end of the line continuation character is causing a syntax error. |
| mutable_default_cart | shared state | fixed | 1 | 90s | The `Cart` class's `__init__` method initializes `items` with a default mutable list, which is shared across instances. |
| pagination_off_by_one | off-by-one | fixed | 1 | 107s | The `paginate` function is incorrectly calculating the start and end indices for slicing the items list. |
| port_exception_type | exception contract | fixed | 1 | 117s | The `parse_port` function attempts to convert non-numeric values to integers, which raises a `ValueError`. The tests for non-numeric and out |
| renamed_import | import error | fixed | 1 | 107s | The `slugify` function is not defined in `textutils.py`, but it is being imported and used in `articles.py`. The correct function name shoul |
| restock_mutates_input | shared state | not fixed | 3 | 216s | The `restock` function is modifying the input dictionary `stock`, which violates its contract of leaving the input unchanged. |
| retry_attempt_count | off-by-one | not fixed | 3 | 169s | The `flaky` function increments `calls['n']` only twice, causing the retry mechanism to fail after two attempts instead of three. |
| tax_rate_units | cross-file contract | not fixed | 3 | 250s | The test expects the GST rate to be returned as a percentage (e.g., 18 for 18%), but the function returns it as a decimal (e.g., 0.18 for 18 |
| weekend_check | boundary condition | not fixed | 3 | 413s | The `next_business_day` function incorrectly returns Saturday as the next business day. |
