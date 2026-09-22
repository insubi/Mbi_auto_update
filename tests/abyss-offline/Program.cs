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
            Console.Error.WriteLine("Usage: AbyssOfflineRegressionTests <FishingAutomation.dll> <FishingAutomation source dir> <actual-result-b64>");
            return 2;
        }

        string assemblyPath = Path.GetFullPath(args[0]);
        string sourceDir = Path.GetFullPath(args[1]);
        string resultB64Path = Path.GetFullPath(args[2]);
        string assemblyDir = Path.GetDirectoryName(assemblyPath)!;

        Environment.SetEnvironmentVariable(
            "PATH",
            assemblyDir + Path.PathSeparator + Environment.GetEnvironmentVariable("PATH"));

        AssemblyLoadContext.Default.Resolving += (_, name) =>
        {
            string candidate = Path.Combine(assemblyDir, name.Name + ".dll");
            return File.Exists(candidate)
                ? AssemblyLoadContext.Default.LoadFromAssemblyPath(candidate)
                : null;
        };

        Assembly production = Assembly.LoadFrom(assemblyPath);

        Require(File.Exists(resultB64Path), "actual-capture result fixture payload exists");
        using var actualResult = BuildActualResultFrame(resultB64Path);
        Require(actualResult.Width == 800 && actualResult.Height == 1000,
            $"actual result frame reconstructed as 800x1000; actual={actualResult.Width}x{actualResult.Height}");

        // Call the exact private V0.1.55+ production visual-row detector by reflection.
        bool resultFound = InvokeResultVisualDetector(production, actualResult, out Rectangle resultRetry);
        Require(resultFound, $"actual-capture result buttons are recognized; retry={resultRetry}");
        Require(Math.Abs(resultRetry.Left + resultRetry.Width / 2 - 400) <= 35,
            $"retry ROI remains centered near x=400; actual={resultRetry.Left + resultRetry.Width / 2}");
        Require(resultRetry.Top >= 850,
            $"retry ROI remains in lower result area; actual={resultRetry}");

        using var scaled799 = Resize(actualResult, 799, 1000);
        using var scaled800x999 = Resize(actualResult, 800, 999);
        Require(InvokeResultVisualDetector(production, scaled799, out var r799),
            $"799x1000 actual-derived result remains recognized; retry={r799}");
        Require(InvokeResultVisualDetector(production, scaled800x999, out var r999),
            $"800x999 actual-derived result remains recognized; retry={r999}");

        // Exercise production TargetDetector + production targets.json + production templates.
        string targetsJson = Directory.EnumerateFiles(sourceDir, "targets.json", SearchOption.AllDirectories)
            .FirstOrDefault(p => File.ReadAllText(p).Contains("abyss_dungeon_clear_visual", StringComparison.Ordinal))
            ?? throw new FileNotFoundException("Could not locate targets.json containing abyss_dungeon_clear_visual.");

        string detectorBaseDir = Directory.GetParent(Path.GetDirectoryName(targetsJson)!)!.FullName;
        Console.WriteLine($"DETECTOR_BASE {detectorBaseDir}");
        object detector = BuildTargetDetector(production, targetsJson, detectorBaseDir);
        using var clearFrame = BuildProductionTemplateFrame(sourceDir, targetsJson,
            "abyss_dungeon_clear_visual", "abyss_touch_screen");

        bool clearMisclassified = InvokeResultVisualDetector(production, clearFrame, out Rectangle clearRetry);
        Require(!clearMisclassified,
            $"production clear/touch frame is NOT misclassified as result; retry={clearRetry}");

        var clearTitle = await DetectAsync(detector, "abyss_dungeon_clear_visual", clearFrame);
        var touch = await DetectAsync(detector, "abyss_touch_screen", clearFrame);
        Console.WriteLine($"CLEAR title={clearTitle}");
        Console.WriteLine($"CLEAR touch={touch}");

        Require(clearTitle.Found,
            $"production clear visual target detects its own template; score={clearTitle.Score:0.000}");
        Require(touch.Found,
            $"production touch-screen target detects its own template; score={touch.Score:0.000}");

        var resultClearTitle = await DetectAsync(detector, "abyss_dungeon_clear_visual", actualResult);
        var resultTouch = await DetectAsync(detector, "abyss_touch_screen", actualResult);
        Require(!(resultClearTitle.Found && resultTouch.Found),
            $"actual result fixture is not mistaken for confirmed clear pair; clear={resultClearTitle.Score:0.000}, touch={resultTouch.Score:0.000}");

        string engineSource = File.ReadAllText(Path.Combine(sourceDir, "dungeon", "ScenarioEngine.cs"));
        Require(engineSource.Contains("missing clear/touch templates is NOT treated as a successful", StringComparison.Ordinal),
            "V0.1.54 clear-screen safety guard remains in production source");
        Require(engineSource.Contains("Step 5 is not complete until the actual result screen is confirmed.", StringComparison.Ordinal),
            "V0.1.54 result-screen confirmation guard remains in production source");

        if (_failures == 0)
        {
            Console.WriteLine("V0158_OFFLINE_ABYSS_REGRESSION_OK");
            return 0;
        }

        Console.Error.WriteLine($"V0158_OFFLINE_ABYSS_REGRESSION_FAILED count={_failures}");
        return 1;
    }

    private static Bitmap BuildActualResultFrame(string b64Path)
    {
        string b64 = string.Concat(File.ReadAllLines(b64Path)).Trim();
        byte[] bytes = Convert.FromBase64String(b64);
        using var ms = new MemoryStream(bytes, writable: false);
        using var small = new Bitmap(ms);

        if (small.Width != 250 || small.Height != 50)
            throw new InvalidOperationException(
                $"Actual result crop must be 250x50, got {small.Width}x{small.Height}.");

        var enlarged = new Bitmap(500, 100);
        using (Graphics g = Graphics.FromImage(enlarged))
            g.DrawImage(small, new Rectangle(0, 0, 500, 100));

        var frame = new Bitmap(800, 1000);
        using (Graphics g = Graphics.FromImage(frame))
        {
            g.Clear(Color.Black);
            // Derived from the user's real 800x1000 result capture:
            // original crop x=150..650, y=890..990, downsampled 2x only for repository storage.
            g.DrawImageUnscaled(enlarged, 150, 890);
        }

        enlarged.Dispose();
        return frame;
    }

    private static Bitmap BuildProductionTemplateFrame(
        string sourceDir,
        string targetsJson,
        params string[] targetIds)
    {
        using JsonDocument doc = JsonDocument.Parse(File.ReadAllText(targetsJson));
        var frame = new Bitmap(800, 1000);
        using Graphics g = Graphics.FromImage(frame);
        g.Clear(Color.Black);

        foreach (string id in targetIds)
        {
            JsonElement target = doc.RootElement.EnumerateArray()
                .FirstOrDefault(e =>
                    e.TryGetProperty("Id", out var idProp) &&
                    string.Equals(idProp.GetString(), id, StringComparison.OrdinalIgnoreCase));

            if (target.ValueKind == JsonValueKind.Undefined)
                throw new InvalidOperationException($"Production target missing: {id}");

            if (!target.TryGetProperty("TemplatePath", out JsonElement templateProp) ||
                string.IsNullOrWhiteSpace(templateProp.GetString()))
            {
                throw new InvalidOperationException($"Production target has no template: {id}");
            }

            Rectangle roi = ReadRoi(target.GetProperty("Roi"));
            string templatePath = ResolveTemplatePath(sourceDir, templateProp.GetString()!);
            using var template = new Bitmap(templatePath);

            int x = roi.Left + Math.Max(0, (roi.Width - template.Width) / 2);
            int y = roi.Top + Math.Max(0, (roi.Height - template.Height) / 2);
            g.DrawImageUnscaled(template, x, y);
            Console.WriteLine($"TEMPLATE {id} path={templatePath} roi={roi} size={template.Width}x{template.Height} at={x},{y}");
        }

        return frame;
    }

    private static Rectangle ReadRoi(JsonElement roi)
    {
        if (roi.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException("V0.1.58 fixture builder expects object ROI.");

        int x = roi.GetProperty("X").GetInt32();
        int y = roi.GetProperty("Y").GetInt32();
        int width = roi.GetProperty("Width").GetInt32();
        int height = roi.GetProperty("Height").GetInt32();
        return new Rectangle(x, y, width, height);
    }

    private static string ResolveTemplatePath(string sourceDir, string configuredPath)
    {
        string normalized = configuredPath
            .Replace('/', Path.DirectorySeparatorChar)
            .Replace('\\', Path.DirectorySeparatorChar);

        string direct = Path.Combine(sourceDir, normalized);
        if (File.Exists(direct))
            return direct;

        string fileName = Path.GetFileName(normalized);
        string? found = Directory.EnumerateFiles(sourceDir, fileName, SearchOption.AllDirectories)
            .FirstOrDefault();

        return found ?? throw new FileNotFoundException(
            $"Could not locate production template '{configuredPath}' under {sourceDir}.");
    }

    private static bool InvokeResultVisualDetector(
        Assembly production,
        Bitmap bitmap,
        out Rectangle retryRoi)
    {
        Type engineType = production.GetType("DungeonVisionBot.ScenarioEngine", throwOnError: true)!;
        object engine = RuntimeHelpers.GetUninitializedObject(engineType);
        MethodInfo method = engineType.GetMethod(
            "TryDetectAbyssResultButtonRow",
            BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(
                engineType.FullName,
                "TryDetectAbyssResultButtonRow");

        object?[] invokeArgs = { bitmap, Rectangle.Empty };
        bool found = (bool)(method.Invoke(engine, invokeArgs) ?? false);
        retryRoi = invokeArgs[1] is Rectangle rect ? rect : Rectangle.Empty;
        return found;
    }

    private static object BuildTargetDetector(
        Assembly production,
        string targetsJson,
        string baseDir)
    {
        Type targetType = production.GetType("DungeonVisionBot.TargetDefinition", true)!;
        Type listType = typeof(List<>).MakeGenericType(targetType);
        object targets = JsonSerializer.Deserialize(
            File.ReadAllText(targetsJson),
            listType,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidOperationException("targets.json deserialized to null.");

        Type detectorType = production.GetType("DungeonVisionBot.TargetDetector", true)!;
        foreach (ConstructorInfo ctor in detectorType.GetConstructors(
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
        {
            ParameterInfo[] p = ctor.GetParameters();
            if (p.Length == 2 && p[1].ParameterType == typeof(string))
            {
                try
                {
                    return ctor.Invoke(new[] { targets, baseDir });
                }
                catch (ArgumentException)
                {
                }
            }
        }

        throw new MissingMethodException(
            detectorType.FullName,
            ".ctor(IEnumerable<TargetDefinition>, string)");
    }

    private static async Task<DetectionView> DetectAsync(
        object detector,
        string id,
        Bitmap frame)
    {
        MethodInfo method = detector.GetType().GetMethod(
            "DetectAsync",
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(
                detector.GetType().FullName,
                "DetectAsync");

        object taskObject = method.Invoke(
            detector,
            new object?[] { id, frame, CancellationToken.None })
            ?? throw new InvalidOperationException(
                $"DetectAsync({id}) returned null task.");

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

    private readonly record struct DetectionView(
        bool Found,
        double Score,
        Rectangle Bounds,
        string? ReadText)
    {
        public override string ToString() =>
            $"found={Found} score={Score:0.000} bounds={Bounds} text={ReadText ?? "<none>"}";
    }
}
