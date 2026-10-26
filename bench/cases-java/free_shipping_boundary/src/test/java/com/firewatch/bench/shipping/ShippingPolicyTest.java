package com.firewatch.bench.shipping;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class ShippingPolicyTest {

    @Test
    void orderAtTheThresholdShipsFree() {
        assertEquals(0, ShippingPolicy.shippingCents(5000));
    }

    @Test
    void orderOneCentBelowTheThresholdPaysShipping() {
        assertEquals(599, ShippingPolicy.shippingCents(4999));
    }

    @Test
    void orderAboveTheThresholdShipsFree() {
        assertEquals(0, ShippingPolicy.shippingCents(5001));
    }

    @Test
    void totalAddsShippingBelowTheThreshold() {
        assertEquals(5598, ShippingPolicy.totalCents(4999));
    }
}