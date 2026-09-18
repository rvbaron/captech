interface Drawable {
    draw(): void;
}

interface Serializable {
}

// interface extends interface(s) -> inherits
interface Renderable extends Drawable, Serializable {
}

class Animal {
}

// class extends (-> inherits) + implements (two interfaces)
class Dog extends Animal implements Drawable, Serializable {
    draw(): void {
    }
}
