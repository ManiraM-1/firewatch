package com.firewatch.bench.batch;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;

import org.junit.jupiter.api.Test;

class BatchTotalsTest {

    @Test
    void sumsEveryAmountInTheBatch() {
        assertEquals(10, BatchTotals.sum(List.of(1, 2, 3, 4)));
    }

    @Test
    void sumsAShortBatch() {
        assertEquals(6, BatchTotals.sum(List.of(1, 2, 3)));
    }

    @Test
    void emptyBatchSumsToZero() {
        assertEquals(0, BatchTotals.sum(List.of()));
    }

    @Test
    void averageIncludesTheLastAmount() {
        assertEquals(2, BatchTotals.average(List.of(1, 2, 3)));
    }
}