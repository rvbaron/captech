"""Eligibility service for provider validation."""


class EligibilityService:
    """Service to check provider eligibility."""

    def __init__(self, rules):
        self.rules = rules

    def check(self, provider_id):
        """Check if provider is eligible."""
        if not provider_id:
            return False
        return self.validate_provider(provider_id)

    def validate_provider(self, provider_id):
        """Validate provider against rules."""
        return self.rules.apply(provider_id)
