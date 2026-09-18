from framework import app


@requires_auth
@app.get("/health")
def health():
    return "ok"


@app.post("/orders")
def create_order():
    return "created"


class OrderService:
    @staticmethod
    def helper():
        return 1
