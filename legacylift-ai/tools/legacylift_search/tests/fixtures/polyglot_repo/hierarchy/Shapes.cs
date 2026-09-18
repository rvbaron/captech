namespace Shapes
{
    public interface IShape
    {
        double Area();
    }

    public class Shape
    {
        public virtual double Area() => 0;
    }

    // Bare base class (Shape) + in-repo interface (IShape) + generic external
    // base (IComparable<Circle>) + qualified external base (System.IDisposable).
    public class Circle : Shape, IShape, IComparable<Circle>, System.IDisposable
    {
        public double Area() => 3.14;
        public int CompareTo(Circle other) => 0;
        public void Dispose() { }
    }

    // Positional record: base is wrapped in primary_constructor_base_type.
    public record CircleDto(int Id) : ShapeDto(Id), IEquatable<CircleDto>;

    public record ShapeDto(int Id);

    // enum underlying type must NOT produce a hierarchy edge to `byte`.
    public enum ShapeKind : byte
    {
        Round,
        Square
    }
}
