package demo.api;

import javax.persistence.Entity;
import org.springframework.web.bind.annotation.GetMapping;

@Entity
@Table(name = "orders")
public class Order {

    @Id
    private Long id;

    @NotNull
    @Column(name = "total")
    private Double total;

    @ManyToOne
    @JoinColumn(name = "customer_id")
    private Customer customer;
}

class OrderController {

    @GetMapping("/orders")
    public String list() {
        return "ok";
    }

    @PreAuthorize("hasRole('ADMIN')")
    @PostMapping("/orders")
    public String create() {
        return "ok";
    }
}

class Customer {
    private Long id;
}
