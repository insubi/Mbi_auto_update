using System.Runtime.InteropServices;

namespace FishingAutomation.Life;

// A separate adapter adds chords without changing either existing input engine.
internal sealed class LifeKeyboard : IDisposable
{
    private nint _context;
    private readonly int _device;
    public int Device => _device;

    public LifeKeyboard(int preferred)
    {
        _context = interception_create_context();
        if (_context == 0) throw new InvalidOperationException("생활 키보드 Interception 초기화 실패");
        nint buffer = Marshal.AllocHGlobal(1000);
        try
        {
            var candidates = Enumerable.Range(1, 10).OrderBy(d => d == preferred ? 0 : 1);
            foreach (int d in candidates)
                if (interception_get_hardware_id(_context, d, buffer, 1000) >= 2) { _device = d; break; }
            if (_device == 0) throw new InvalidOperationException("생활 기능에 사용할 Interception 키보드가 없습니다.");
        }
        catch { Dispose(); throw; }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    private void Send(ushort code, bool up)
    {
        var stroke = new KeyStroke { Code = code, State = (ushort)(up ? 1 : 0) };
        if (interception_send(_context, _device, ref stroke, 1) != 1)
            throw new InvalidOperationException("생활 키보드 입력 전송 실패");
    }

    public void Tap(ushort code, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        try { Send(code, false); Thread.Sleep(50); }
        finally { Send(code, true); }
        ct.ThrowIfCancellationRequested();
    }

    private void Chord(ushort key, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        try { Send(0x1D, false); Tap(key, ct); }
        finally { Send(0x1D, true); }
    }

    public Task ReplaceSearchTextAsync(string text, Action ensureWindow, CancellationToken ct)
    {
        var done = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var thread = new Thread(() =>
        {
            IDataObject? previous = null;
            bool changed = false;
            Exception? failure = null;
            try
            {
                ct.ThrowIfCancellationRequested();
                previous = Clipboard.GetDataObject();
                Clipboard.SetText(text, TextDataFormat.UnicodeText);
                changed = true;
                ensureWindow();
                Chord(0x1E, ct); // Ctrl+A
                ensureWindow();
                Chord(0x2F, ct); // Ctrl+V, Korean text is independent of IME mode.
                Thread.Sleep(250);
                ct.ThrowIfCancellationRequested();
            }
            catch (Exception ex) { failure = ex; }
            finally
            {
                try
                {
                    // Preserve all formats and never overwrite a newer user clipboard.
                    if (changed && Clipboard.ContainsText() && Clipboard.GetText() == text)
                    {
                        if (previous is not null) Clipboard.SetDataObject(previous, true);
                        else Clipboard.Clear();
                    }
                }
                catch { /* Clipboard ownership may have changed while the game read it. */ }
            }
            if (failure is OperationCanceledException) done.TrySetCanceled(ct);
            else if (failure is not null) done.TrySetException(failure);
            else done.TrySetResult();
        }) { IsBackground = true, Name = "Life search clipboard" };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        return done.Task;
    }

    public void Dispose()
    {
        if (_context != 0) { interception_destroy_context(_context); _context = 0; }
    }
    [StructLayout(LayoutKind.Sequential)] private struct KeyStroke
    { public ushort Code, State; public uint Information; }
    [DllImport("interception.dll", CallingConvention = CallingConvention.Cdecl)] private static extern nint interception_create_context();
    [DllImport("interception.dll", CallingConvention = CallingConvention.Cdecl)] private static extern void interception_destroy_context(nint context);
    [DllImport("interception.dll", CallingConvention = CallingConvention.Cdecl)] private static extern uint interception_get_hardware_id(nint context, int device, nint buffer, int bytes);
    [DllImport("interception.dll", CallingConvention = CallingConvention.Cdecl)] private static extern int interception_send(nint context, int device, ref KeyStroke stroke, uint count);
}
