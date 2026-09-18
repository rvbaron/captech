class Base:
    def area(self):
        return 0


class Mixin:
    pass


class Circle(Base, Mixin):
    def area(self):
        return 3.14


class Standalone:
    pass
