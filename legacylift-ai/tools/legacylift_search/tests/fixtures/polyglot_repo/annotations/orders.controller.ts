@Controller("orders")
export class OrdersController {

  @Get("/")
  findAll(): string {
    return "all";
  }

  @Post("/")
  create(): string {
    return "created";
  }
}
