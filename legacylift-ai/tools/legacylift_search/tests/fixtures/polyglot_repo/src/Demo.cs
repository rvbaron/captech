namespace Demo.Services
{
    public class CustomerService
    {
        public bool Validate(string customerId)
        {
            if (string.IsNullOrEmpty(customerId))
                return false;
            return CheckEligibility(customerId);
        }

        private bool CheckEligibility(string id)
        {
            // Eligibility check logic
            return id.Length > 0;
        }
    }
}
