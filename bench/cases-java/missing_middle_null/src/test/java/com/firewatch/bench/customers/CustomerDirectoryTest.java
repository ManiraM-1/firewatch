package com.firewatch.bench.customers;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CustomerDirectoryTest {

    private final CustomerDirectory directory = new CustomerDirectory();

    @BeforeEach
    void setUp() {
        directory.add("ada", new CustomerDirectory.Customer("Ada", null, "Lovelace"));
        directory.add("grace", new CustomerDirectory.Customer("Grace", "Brewster", "Hopper"));
    }

    @Test
    void formatsNameWhenMiddleNameIsMissing() {
        assertEquals("Ada Lovelace", directory.fullName("ada"));
    }

    @Test
    void keepsMiddleNameWhenPresent() {
        assertEquals("Grace Brewster Hopper", directory.fullName("grace"));
    }

    @Test
    void greetingUsesFormattedName() {
        assertEquals("Welcome back, Ada Lovelace!", directory.greeting("ada"));
    }
}