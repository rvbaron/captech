using Microsoft.AspNetCore.Mvc;

namespace Demo.Api
{
    [Authorize]
    public class OrdersController : ControllerBase
    {
        [HttpGet("orders")]
        public IActionResult GetOrders()
        {
            return Ok();
        }

        [HttpPost("orders")]
        public IActionResult CreateOrder(Order order)
        {
            return Ok();
        }
    }

    public class Order
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [MaxLength(50)]
        [Column("customer_name")]
        public string CustomerName { get; set; }
    }
}
