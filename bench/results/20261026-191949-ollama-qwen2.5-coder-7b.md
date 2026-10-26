## Benchmark: `ollama:qwen2.5-coder:7b`

**Fixed 11/17** (65%) · first-attempt fixes: 9 · mean attempts when fixed: 1.18 · median time: 157.6s

| Case | Category | Result | Attempts | Time | Root cause found by the model |
|---|---|---|---|---|---|
| config_wrong_key | wrong key | fixed | 1 | 116s | The `http_options` function is trying to access a key 'timeout_seconds' which does not exist in the configuration dictionary. |
| discount_threshold | boundary condition | not fixed | 3 | 158s | The `discount` function is returning 0 instead of 10% off for orders of $1000 or more. |
| invoice_decimal_places | formatting | fixed | 1 | 102s | The `format_amount` function is not formatting the amount to two decimal places consistently. |
| leaderboard_order | sort order | not fixed | 3 | 279s | The `top` function is returning player names in the wrong order because it does not reverse the sorted list before slicing. |
| mean_integer_division | arithmetic | fixed | 1 | 80s | The `mean` function is using integer division (`//`), which truncates the decimal part, causing it to return an incorrect result for non-int |
| missing_middle_name | None handling | not fixed | 3 | 337s | The `full_name` function is including `None` in the parts list when a middle name is not provided, causing a `TypeError` when trying to join |
| mutable_default_cart | shared state | fixed | 1 | 71s | The `Cart` class's `__init__` method initializes `items` with a default mutable list, which causes all instances to share the same list. |
| pagination_off_by_one | off-by-one | fixed | 1 | 96s | The `paginate` function is incorrectly calculating the start and end indices for slicing the items list. |
| port_exception_type | exception contract | fixed | 1 | 109s | The `parse_port` function attempts to convert non-numeric values to integers, which raises a `ValueError`. The tests check for this behavior |
| renamed_import | import error | fixed | 1 | 104s | The `slugify` function is not defined in `textutils.py`, but it is being imported and used in `articles.py`. The correct function name shoul |
| restock_mutates_input | shared state | fixed | 2 | 181s | The `restock` function is mutating the input dictionary instead of returning a new one. |
| retry_attempt_count | off-by-one | fixed | 1 | 106s | The `retry` function is not correctly handling the number of attempts and is raising a `RetryError` prematurely. |
| tax_rate_units | cross-file contract | not fixed | 3 | 245s | The tax amount is being calculated incorrectly in the `tax_amount` function. The tax rate for 'reduced' category should be applied as a perc |
| weekend_check | boundary condition | not fixed | 3 | 433s | The `next_business_day` function incorrectly calculates the next business day, causing it to roll over Saturday instead of moving to Monday. |
| batch_loop_off_by_one | off-by-one | fixed | 1 | 204s | The `sum` method in `BatchTotals.java` is excluding the last element from the sum calculation. |
| free_shipping_boundary | boundary condition | not fixed | 3 | 561s | The `orderAtTheThresholdShipsFree` test expects shipping to be free when the subtotal is exactly at the free-shipping threshold (5000 cents) |
| missing_middle_null | null handling | fixed | 2 | 304s | The `fullName` method is incorrectly handling null middle names by invoking `isEmpty()` on them, which leads to a NullPointerException. |
