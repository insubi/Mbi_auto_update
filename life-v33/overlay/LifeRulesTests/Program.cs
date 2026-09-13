using FishingAutomation.Life;

int checks = 0;
void Check(bool value, string message)
{
    if (!value) throw new Exception(message);
    checks++;
}
Check(LifeRules.ExactItem("황금 양털", "황금 양털"), "golden identity");
Check(!LifeRules.ExactItem("황금 양털+", "황금 양털"), "reject golden plus");
Check(!LifeRules.ExactItem("황금 양털＋", "황금 양털"), "reject fullwidth plus");
Check(!LifeRules.ExactItem("황금 양털", "양털"), "ordinary wool identity");
Check(!LifeRules.ExactItem("양털+", "양털"), "reject ordinary plus");
foreach (var (text, expected) in new[] { ("1", 1), ("9999", 9999), ("1,000", 1000), ("9,999", 9999), ("１０００", 1000) })
    Check(LifeRules.ReadQuantity(text) == expected, "quantity: " + text);
foreach (string invalid in new[] { "0", "10000", "1/9999", "99%", "l000", "1.000", "1 000", "1,00", "1000 9999", "" })
    Check(LifeRules.ReadQuantity(invalid) is null, "reject ambiguous quantity: " + invalid);
Check(LifeRules.Complete("100 %"), "completion exactly 100%");
foreach (string s in new[] { "1100%", "100", "99%", "1 00% 100%" }) Check(!LifeRules.Complete(s), "reject incomplete/ambiguous percentage");

var confirm = new ConsecutiveConfirmation();
Check(!confirm.Observe(true, 1), "one reading insufficient");
Check(!confirm.Observe(true, 1), "same screenshot never confirms");
Check(!confirm.Observe(false, 2), "negative resets confirmation");
Check(!confirm.Observe(true, 3), "after negative requires two");
Check(confirm.Observe(true, 4), "two new positive screenshots confirm");
var queue = new QueuePolicy();
Check(queue.CanAdd(false), "queue initially accepts work");
Check(!queue.CanCollect(false, true, 1), "slots 1-6 completed cannot trigger collect");
Check(!queue.CanAdd(true), "slot seven full stops additions immediately");
Check(!queue.CanAdd(false), "temporary recognition loss cannot unlock additions");
Check(!queue.CanCollect(true, false, 2), "wait for seventh completion");
Check(!queue.CanCollect(true, true, 3), "one seventh completion screenshot insufficient");
Check(!queue.CanCollect(true, true, 3), "same seventh screenshot cannot confirm");
Check(queue.CanCollect(true, true, 4), "collect after seventh completed twice");
queue.ReceivedAndEmpty();
Check(queue.CanAdd(false), "confirmed collection/empty resets queue");

var motion = new GaugeMotion();
for (int i = 0; i < 12; i++) Check(!motion.Observe(new(300, 400, 50)), "static green HUD is not gathering");
motion.Reset();
Check(!motion.Observe(new(300, 400, 20)), "initial bar is not motion");
Check(!motion.Observe(new(300, 400, 25)), "one change insufficient");
Check(!motion.Observe(new(300, 400, 30)), "two changes insufficient");
Check(motion.Observe(new(300, 400, 35)), "three consecutive length changes prove motion");
motion.Reset();
for (int i = 0; i < 10; i++) Check(!motion.Observe(new(300 + i * 12, 400, 30 + i * 5)), "moving scene objects are rejected");
motion.Reset();
for (int i = 0; i < 10; i++) Check(!motion.Observe(new(300, 400, 30 + i % 2)), "one pixel flicker is rejected");

string folder = Path.Combine(Path.GetTempPath(), "MabiLifeTests_" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(folder);
try
{
    string file = Path.Combine(folder, "settings.json");
    Check(LifeSettings.Load(file).WoolTarget == 1000, "default target");
    foreach (int n in new[] { 1, 1000, 9999 })
    {
        new LifeSettings { WoolTarget = n }.Save(file);
        Check(LifeSettings.Load(file).WoolTarget == n, "target persists across reload");
    }
    File.WriteAllText(file, "{\"WoolTarget\": 3333, \"FutureOption\": true}");
    LifeSettings.Load(file).Save(file);
    Check(File.ReadAllText(file).Contains("FutureOption"), "preserve unrelated settings");
    foreach (int n in new[] { 0, 10000 })
    {
        bool rejected = false;
        try { new LifeSettings { WoolTarget = n }.Save(file); } catch (ArgumentOutOfRangeException) { rejected = true; }
        Check(rejected, "out of range save rejected");
        Check(LifeSettings.Load(file).WoolTarget == 3333, "rejected save preserves previous file");
    }
    Check(new LifeProfile().Validate(folder, 800, 1000).Count > 0, "missing image/ROI profile blocks start");
}
finally { Directory.Delete(folder, true); }
Console.WriteLine($"PASS: {checks} life rule checks. No game input or Telegram messages were sent.");
