using System.Collections;
using System.Drawing;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Text.Json;

internal static class Program
{
    private static int _failures;

    private static async Task<int> Main(string[] args)
    {
        if (args.Length != 3)
        {
            Console.Error.WriteLine("Usage: AbyssOfflineRegressionTests <FishingAutomation.dll> <FishingAutomation source dir> <fixture dir>");
            return 2;
        }

        string assemblyPath = Path.GetFullPath(args[0]);
        string sourceDir = Path.GetFullPath(args[1]);
        string fixtureDir = Path.GetFullPath(args[2]);
        string assemblyDir = Path.GetDirectoryName(assemblyPath)!;
        Environment.SetEnvironmentVariable("PATH", assemblyDir + Path.PathSeparator + Environment.GetEnvironmentVariable("PATH"));

        AssemblyLoadContext.Default.Resolving += (_, name) =>
        {
            string candidate = Path.Combine(assemblyDir, name.Name + ".dll");
            return File.Exists(candidate) ? AssemblyLoadContext.Default.LoadFromAssemblyPath(candidate) : null;
        };

        Assembly production = Assembly.LoadFrom(assemblyPath);
        string resultPath = Path.Combine(fixtureDir, "abyss_result_real.jpg");
        string clearPath = Path.Combine(fixtureDir, "abyss_clear_touch_real.jpg");
        Require(File.Exists(resultPath), "real result fixture exists");
        Require(File.Exists(clearPath), "real clear/touch fixture exists");

        using var result = new Bitmap(resultPath);
        using var clear = new Bitmap(clearPath);

        Console.WriteLine($"FIXTURE result={result.Width}x{result.Height} clear={clear.Width}x{clear.Height}");

        // Call the exact private V0.1.55+ production visual-row detector by reflection.
        bool resultFound = InvokeResultVisualDetector(production, result, out Rectangle resultRetry);
        Require(resultFound, $"real result screenshot is recognized as Abyss result; retry={resultRetry}");
        Require(Math.Abs(resultRetry.Left + resultRetry.Width / 2 - 400) <= 35,
            $"retry ROI remains centered near x=400; actual={resultRetry.Left + resultRetry.Width / 2}");
        Require(resultRetry.Top >= 850, $"retry ROI remains in lower result area; actual={resultRetry}");

        bool clearMisclassified = InvokeResultVisualDetector(production, clear, out Rectangle clearRetry);
        Require(!clearMisclassified, $"clear/touch screenshot is NOT misclassified as result; retry={clearRetry}");

        using var scaled799 = Resize(result, 799, 1000);
        using var scaled800x999 = Resize(result, 800, 999);
        Require(InvokeResultVisualDetector(production, scaled799, out var r799),
            $"799x1000 result remains recognized; retry={r799}");
        Require(InvokeResultVisualDetector(production, scaled800x999, out var r999),
            $"800x999 result remains recognized; retry={r999}");

        // Exercise the production TargetDetector and production target JSON/templates.
        string targetsJson = Directory.EnumerateFiles(sourceDir, "targets.json", SearchOption.AllDirectories)
            .FirstOrDefault(p => File.ReadAllText(p).Contains("abyss_dungeon_clear_visual", StringComparison.Ordinal))
            ?? throw new FileNotFoundException("Could not locate targets.json containing abyss_dungeon_clear_visual.");

        string baseDir = Directory.GetParent(Path.GetDirectoryName(targetsJson)!)!.FullName;
        Console.WriteLine($"TARGETS {targetsJson}");
        Console.WriteLine($"BASE    {baseDir}");

        object detector = BuildTargetDetector(production, targetsJson, baseDir);
        var clearTitle = await DetectAsync(production, detector, "abyss_dungeon_clear_visual", clear);
        var touch = await DetectAsync(production, detector, "abyss_touch_screen", clear);
        Console.WriteLine($"CLEAR title={clearTitle}");
        Console.WriteLine($"CLEAR touch={touch}");

        // Production V0.1.54+ accepts the clear title as the stable anchor and has a
        // guarded fallback when the small "touch screen" template is weak/missed.
        Require(clearTitle.Found,
            $"real clear screenshot matches abyss_dungeon_clear_visual; score={clearTitle.Score:0.000}");

        string engineSource = File.ReadAllText(Path.Combine(sourceDir, "dungeon", "ScenarioEngine.cs"));
        Require(engineSource.Contains("missing clear/touch templates is NOT treated as a successful", StringComparison.Ordinal),
            "V0.1.54 clear-screen safety guard remains in production source");
        Require(engineSource.Contains("Step 5 is not complete until the actual result screen is confirmed.", StringComparison.Ordinal),
            "V0.1.54 result-screen confirmation guard remains in production source");

        var resultClearTitle = await DetectAsync(production, detector, "abyss_dungeon_clear_visual", result);
        var resultTouch = await DetectAsync(production, detector, "abyss_touch_screen", result);
        Require(!(resultClearTitle.Found && resultTouch.Found),
            $"real result screenshot is not mistaken for confirmed clear pair; clear={resultClearTitle.Score:0.000}, touch={resultTouch.Score:0.000}");

        if (_failures == 0)
        {
            Console.WriteLine("V0158_OFFLINE_ABYSS_REGRESSION_OK");
            return 0;
        }

        Console.Error.WriteLine($"V0158_OFFLINE_ABYSS_REGRESSION_FAILED count={_failures}");
        return 1;
    }

    private static bool InvokeResultVisualDetector(Assembly production, Bitmap bitmap, out Rectangle retryRoi)
    {
        Type engineType = production.GetType("DungeonVisionBot.ScenarioEngine", throwOnError: true)!;
        object engine = RuntimeHelpers.GetUninitializedObject(engineType);
        MethodInfo method = engineType.GetMethod("TryDetectAbyssResultButtonRow",
            BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(engineType.FullName, "TryDetectAbyssResultButtonRow");

        object?[] invokeArgs = { bitmap, Rectangle.Empty };
        bool found = (bool)(method.Invoke(engine, invokeArgs) ?? false);
        retryRoi = invokeArgs[1] is Rectangle rect ? rect : Rectangle.Empty;
        return found;
    }

    private static object BuildTargetDetector(Assembly production, string targetsJson, string baseDir)
    {
        Type targetType = production.GetType("DungeonVisionBot.TargetDefinition", true)!;
        Type listType = typeof(List<>).MakeGenericType(targetType);
        object targets = JsonSerializer.Deserialize(
            File.ReadAllText(targetsJson),
            listType,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidOperationException("targets.json deserialized to null.");

        Type detectorType = production.GetType("DungeonVisionBot.TargetDetector", true)!;
        foreach (ConstructorInfo ctor in detectorType.GetConstructors(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
        {
            ParameterInfo[] p = ctor.GetParameters();
            if (p.Length == 2 && p[1].ParameterType == typeof(string))
            {
                try { return ctor.Invoke(new[] { targets, baseDir }); }
                catch (ArgumentException) { }
            }
        }

        throw new MissingMethodException(detectorType.FullName, ".ctor(IEnumerable<TargetDefinition>, string)");
    }

    private static async Task<DetectionView> DetectAsync(Assembly production, object detector, string id, Bitmap frame)
    {
        MethodInfo method = detector.GetType().GetMethod("DetectAsync",
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(detector.GetType().FullName, "DetectAsync");

        object taskObject = method.Invoke(detector, new object?[] { id, frame, CancellationToken.None })
            ?? throw new InvalidOperationException($"DetectAsync({id}) returned null task.");
        var task = (Task)taskObject;
        await task.ConfigureAwait(false);

        object result = taskObject.GetType().GetProperty("Result")!.GetValue(taskObject)!;
        Type rt = result.GetType();
        bool found = (bool)rt.GetProperty("Found")!.GetValue(result)!;
        double score = Convert.ToDouble(rt.GetProperty("Score")!.GetValue(result));
        Rectangle bounds = (Rectangle)rt.GetProperty("Bounds")!.GetValue(result)!;
        string? text = rt.GetProperty("ReadText")!.GetValue(result) as string;
        return new DetectionView(found, score, bounds, text);
    }

    private static Bitmap Resize(Bitmap source, int width, int height)
    {
        var resized = new Bitmap(width, height);
        using Graphics g = Graphics.FromImage(resized);
        g.DrawImage(source, new Rectangle(0, 0, width, height));
        return resized;
    }

    private static void Require(bool condition, string message)
    {
        if (condition)
        {
            Console.WriteLine("PASS " + message);
            return;
        }

        _failures++;
        Console.Error.WriteLine("FAIL " + message);
    }

    private readonly record struct DetectionView(bool Found, double Score, Rectangle Bounds, string? ReadText)
    {
        public override string ToString() => $"found={Found} score={Score:0.000} bounds={Bounds} text={ReadText ?? "<none>"}";
    }
}
