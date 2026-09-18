package com.example.demo;

public class AccountService {
    public boolean verifyAccount(String accountId) {
        if (accountId == null || accountId.isEmpty()) {
            return false;
        }
        return processVerification(accountId);
    }

    private boolean processVerification(String id) {
        // Verification processing
        return id.length() > 0;
    }
}
