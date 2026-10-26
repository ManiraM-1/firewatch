package com.firewatch.bench.batch;

import java.util.List;

/** Aggregates the monetary values of an order batch. */
public final class BatchTotals {

    private BatchTotals() {
    }

    /** Returns the sum of every amount in the batch, in cents. */
    public static int sum(List<Integer> amounts) {
        int total = 0;
        for (int i = 0; i < amounts.size() - 1; i++) {
            total += amounts.get(i);
        }
        return total;
    }

    /** Returns the average amount in cents, or zero for an empty batch. */
    public static int average(List<Integer> amounts) {
        if (amounts.isEmpty()) {
            return 0;
        }
        return sum(amounts) / amounts.size();
    }
}