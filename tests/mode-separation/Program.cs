using System.Drawing;
using DungeonVisionBot;
var left = new Rectangle(120, 910, 80, 25);
var middle = new Rectangle(320, 912, 90, 25);
var right = new Rectangle(510, 909, 160, 25);
var cases = new[] {
    ("result row", left, middle, right, true),
    ("retry alone", Rectangle.Empty, middle, Rectangle.Empty, false),
    ("missing exit", Rectangle.Empty, middle, right, false),
    ("missing retry", left, Rectangle.Empty, right, false),
    ("missing other", left, middle, Rectangle.Empty, false),
    ("wrong order", middle, left, right, false),
    ("unrelated text on different row", left, new Rectangle(320, 400, 90, 25), right, false),
    ("OCR merged buttons", left, new Rectangle(190,910,370,25), right, false),
    ("row boundaries only touch", left, new Rectangle(320,935,90,25), right, false)
};
foreach (var (name, exit, retry, other, expected) in cases)
{
    if (AbyssResultLayout.IsConfirmed(exit, retry, other) != expected)
        throw new Exception(name);
    Console.WriteLine("PASS " + name);
}
