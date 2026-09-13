using System.Reflection;
using FishingAutomation;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Application.EnableVisualStyles();
        using var form = new MainForm();
        object Get(string name) => typeof(MainForm).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(form)!;
        void Set(string name, object value) => typeof(MainForm).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(form, value);
        object? Call(string name) => typeof(MainForm).GetMethod(name, BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(form, null);
        void Check(bool value, string label) { if (!value) throw new Exception(label); Console.WriteLine("PASS: " + label); }

        // Never Show the form: Shown starts Telegram polling/update checks.
        var modes = (ComboBox)Get("_mode");
        Check(modes.Items.Cast<string>().SequenceEqual(new[] { "낚시", "던전", "어비스", "생활" }), "original modes plus life");
        foreach (string mode in new[] { "낚시", "던전", "어비스", "생활" })
        {
            modes.SelectedItem = mode;
            Call("UpdateStats");
            Check(((Label)Get("_currentDungeonValue")).Text == (mode == "어비스" ? "허상의 정박지" : mode == "생활" ? "옷감 가공" : mode), "mode UI: " + mode);
        }
        var number = (NumericUpDown)Get("_woolTarget");
        Check(number.Minimum == 1 && number.Maximum == 9999 && number.Value == 1000, "quantity default and limits");
        Check(((List<string>)Get("_lifeProblems")).Count > 0, "missing images are visibly unready");
        ((Task)Call("StartLifeAsync")!).GetAwaiter().GetResult();
        Check(Get("_lifeTask") is null, "missing images prevent engine and input startup");
        Check(((Label)Get("_statusValue")).Text.Contains("이미지"), "blocked start has clear status");
        number.Value = 2345;
        Check(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "life", "settings.json")).Contains("2345"), "quantity setting saved");
        Check(((string)Call("GetRemoteStatus")!).Contains("목표 2345"), "Telegram status includes life target without sending");

        var pending = new TaskCompletionSource();
        using var cts = new CancellationTokenSource();
        Set("_lifeTask", pending.Task);
        Set("_lifeCts", cts);
        Check((bool)typeof(MainForm).GetProperty("AnyRunning", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(form)!, "life participates in shared run lock");
        Call("StopSelected");
        Check(cts.IsCancellationRequested, "existing stop route cancels life");
        pending.SetResult();
        Set("_lifeCts", null!);
        Console.WriteLine("WINDOWS UI SMOKE OK. No game clicks, keyboard input, Telegram requests, or update requests were made.");
    }
}
