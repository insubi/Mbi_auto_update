using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace FishingAutomation.Life;

internal static class LifeRules
{
    public static string NormalizeLabel(string text) => string.Concat(
        text.Normalize(NormalizationForm.FormKC).Where(c => !char.IsWhiteSpace(c)));

    // Keep punctuation, especially '+'. Never fuzzy-match item identities.
    public static bool ExactItem(string text, string wanted) =>
        NormalizeLabel(text) == NormalizeLabel(wanted);

    public static int? ReadQuantity(string text)
    {
        string s = text.Normalize(NormalizationForm.FormKC).Trim();
        if (!Regex.IsMatch(s, @"^(?:[1-9][0-9]{0,3}|[1-9],[0-9]{3})$")) return null;
        return int.TryParse(s.Replace(",", ""), NumberStyles.None, CultureInfo.InvariantCulture, out int n)
            && n is >= 1 and <= 9999 ? n : null;
    }

    public static bool Complete(string text) => NormalizeLabel(text) == "100%";
}

internal sealed class ConsecutiveConfirmation(int required = 2)
{
    private int _count;
    private long _lastFrame = -1;
    public bool Observe(bool positive, long frameId)
    {
        if (frameId <= _lastFrame) return false;
        _lastFrame = frameId;
        _count = positive ? _count + 1 : 0;
        return _count >= required;
    }
    public void Reset() { _count = 0; _lastFrame = -1; }
}

internal readonly record struct GaugeSample(int Left, int Top, int Length);

internal sealed class GaugeMotion
{
    private GaugeSample? _previous;
    private int _changes;
    public bool Observe(GaugeSample? sample)
    {
        if (sample is null) { Reset(); return false; }
        if (_previous is { } old && Math.Abs(old.Left - sample.Value.Left) <= 7
            && Math.Abs(old.Top - sample.Value.Top) <= 7)
        {
            int change = Math.Abs(old.Length - sample.Value.Length);
            _changes = change >= 3 ? _changes + 1 : 0;
        }
        else _changes = 0;
        _previous = sample;
        return _changes >= 3;
    }
    public void Reset() { _previous = null; _changes = 0; }
}

internal sealed class QueuePolicy
{
    public bool Full { get; private set; }
    private readonly ConsecutiveConfirmation _complete = new();
    public bool CanAdd(bool slot7Occupied)
    {
        if (slot7Occupied) Full = true;
        return !Full;
    }
    public bool CanCollect(bool slot7Occupied, bool slot7Complete, long frame) =>
        Full && _complete.Observe(slot7Occupied && slot7Complete, frame);
    public void ReceivedAndEmpty() { Full = false; _complete.Reset(); }
}
