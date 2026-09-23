using System.Drawing;
namespace DungeonVisionBot;
record DetectionResult(bool Found) { public Point Center => new(1,1); }
class ScenarioStep { public string TimeoutClickTarget="leave", TimeoutFollowupClickTarget="exit"; public int TimeoutClickTargetWaitSeconds=1, TimeoutFollowupWaitSeconds=1, TimeoutRestartDelaySeconds=0; }
class RestartCycleException:Exception {}
class Settings { public int PollIntervalMs=1, ClickSettleMs=1; }
static class NativeMethods { public static void SetForegroundWindow(nint h) {} }
class Detector { public bool Touch,Result; public Task<DetectionResult> DetectAsync(string id, Bitmap b, CancellationToken ct) => Task.FromResult(new DetectionResult(id=="abyss_touch_screen" ? Touch : true)); }
class Input { public int Clicks; public Action? AfterClick; public void ClickClientPoint(nint h,Point p){Clicks++;AfterClick?.Invoke();} }
internal sealed partial class ScenarioEngine
{
 nint _hwnd; readonly Settings _settings=new(); readonly Detector _detector=new(); readonly Input _input=new(); public event Action<string>? Log;
 enum AbyssFlowState { ClearConfirmed,ResultConfirmed }
 int clearCalls; bool outside;
 Task<nint> ResolveRequiredGameWindowAsync(CancellationToken ct)=>Task.FromResult((nint)1);
 Task<Bitmap> CaptureGameWindowAsync(CancellationToken ct)=>Task.FromResult(new Bitmap(1,1));
 Task<DetectionResult> DetectAbyssResultRetryAsync(Bitmap b,CancellationToken ct)=>Task.FromResult(new DetectionResult(_detector.Result));
 void AbyssTransitionTo(AbyssFlowState s,string r){}
 Task AdvanceAbyssClearScreenAsync(DetectionResult r,CancellationToken ct){clearCalls++;return Task.CompletedTask;}
 Task WaitForAbyssHomeAfterNormalExitAsync(CancellationToken ct){outside=true;return Task.CompletedTask;}
 static void Check(bool v,string m){if(!v)throw new Exception(m);}
 static ScenarioEngine Expired()=>new(){_abyssCombatStartedAt=Environment.TickCount64-600_001};
 static async Task Main()
 {
  var e=Expired();e._detector.Touch=true;e._abyssExitInProgress=true;
  await e.ExitAbyssAfterCombatTimeoutAsync(new(),default);
  Check(e.clearCalls==1&&e._input.Clicks==0&&!e._abyssExitInProgress,"clear at deadline must win");
  e=Expired();e._detector.Result=true;await e.ExitAbyssAfterCombatTimeoutAsync(new(),default);
  Check(e._input.Clicks==0&&!e._abyssExitInProgress,"result must veto exit");
  e=Expired();e._input.AfterClick=()=>e._detector.Touch=true;
  await e.ExitAbyssAfterCombatTimeoutAsync(new(),default);
  Check(e._input.Clicks==1&&e.clearCalls==1&&!e._abyssExitInProgress,"clear before confirmation must cancel");
  e=Expired();bool startedAfterClick=false;e.Log+=s=>{if(s.Contains("퇴장 입력 시작"))startedAfterClick=e._input.Clicks>0;};
  try {await e.ExitAbyssAfterCombatTimeoutAsync(new(),default);throw new Exception("restart missing");} catch(RestartCycleException){}
  Check(e._input.Clicks==2&&e.outside&&e._abyssCombatStartedAt==null&&startedAfterClick,"timeout exit and reset");
  e=new(){_abyssCombatStartedAt=Environment.TickCount64};
  try {await e.ExitAbyssAfterCombatTimeoutAsync(new(),default);throw new Exception("early exit allowed");}catch(InvalidOperationException){}
  Check(e._input.Clicks==0,"no early input");
  e=Expired();using var cts=new CancellationTokenSource();cts.Cancel();
  try{await e.ExitAbyssAfterCombatTimeoutAsync(new(),cts.Token);}catch(OperationCanceledException){}
  Check(e._input.Clicks==0&&!e._abyssExitInProgress,"cancellation");
  Console.WriteLine("PASS: six production timeout control-flow regressions");
 }
}
