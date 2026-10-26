package com.firewatch.bench.shipping;

/** Shipping rules for the storefront. */
public final class ShippingPolicy {

    public static final int FREE_SHIPPING_CENTS = 5000;
    public static final int STANDARD_SHIPPING_CENTS = 599;

    private ShippingPolicy() {
    }

    /** Orders that reach the free-shipping threshold ship for free. */
    public static int shippingCents(int subtotalCents) {
        if (subtotalCents > FREE_SHIPPING_CENTS) {
            return 0;
        }
        return STANDARD_SHIPPING_CENTS;
    }

    /** Returns the order total including shipping. */
    public static int totalCents(int subtotalCents) {
        return subtotalCents + shippingCents(subtotalCents);
    }
}