package hierarchy;

interface Drawable {
    void draw();
}

interface Serializable {
}

// interface extends interface(s) -> inherits
interface Renderable extends Drawable, Serializable {
}

class Animal {
}

// class extends (superclass -> inherits) + implements (super_interfaces),
// including a generic interface base (Comparable<Dog>).
public class Dog extends Animal implements Drawable, Comparable<Dog> {
    public void draw() {
    }

    public int compareTo(Dog other) {
        return 0;
    }
}
