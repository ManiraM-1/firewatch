package com.firewatch.bench.customers;

import java.util.HashMap;
import java.util.Map;

/** Formats customer names for the checkout confirmation. */
public final class CustomerDirectory {

    public record Customer(String first, String middle, String last) {
    }

    private final Map<String, Customer> customers = new HashMap<>();

    public void add(String id, Customer customer) {
        customers.put(id, customer);
    }

    public String fullName(String id) {
        Customer customer = customers.get(id);
        String middle = customer.middle();
        if (middle.isEmpty()) {
            return customer.first() + " " + customer.last();
        }
        return customer.first() + " " + middle + " " + customer.last();
    }

    public String greeting(String id) {
        return "Welcome back, " + fullName(id) + "!";
    }
}