using DungeonVisionBot;
using FishingAutomation.Life;

namespace FishingAutomation;

public sealed partial class MainForm
{
    private readonly NumericUpDown _woolTarget = new();
    private readonly Label _lifeStageValue = new();
    private readonly Label _lifeTemplateValue = new();
    private Control? _lifePanel;
    private TableLayoutPanel? _lifeModeLayout;
    private Button? _lifeNav;
    private LifeSettings _lifeSettings = new();
    private string? _lifeSettingsError;
    private List<string> _lifeProblems = new();
    private CancellationTokenSource? _lifeCts;
    private Task? _lifeTask;
    private string _lifeStage = "준비";
    private DateTime? _lifeStartedAt, _lifeStoppedAt;
    private int _lifeBatches, _lifeLoops;
    private int? _lifeWool;
    private bool LifeRunning => _lifeTask is { IsCompleted: false } || _activeMode == "생활";
    private string LifeBase => Path.Combine(AppContext.BaseDirectory, "life");
    private string LifeSettingsPath => Path.Combine(LifeBase, "settings.json");

    private Control BuildLifeSettingsPanel()
    {
        try { _lifeSettings = LifeSettings.Load(LifeSettingsPath); }
        catch (Exception ex) { _lifeSettingsError = ex.Message; }
        var panel = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 3,
            Margin = Padding.Empty, Visible = false };
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 52));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 48));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        panel.RowStyles.Add(new RowStyle(SizeType.Percent, 55));
        panel.RowStyles.Add(new RowStyle(SizeType.Percent, 45));
        panel.Controls.Add(TextLabel("양털 목표 수량", 9), 0, 0);
        _woolTarget.Minimum = 1;
        _woolTarget.Maximum = 9999;
        _woolTarget.Value = _lifeSettings.WoolTarget;
        _woolTarget.ThousandsSeparator = true;
        _woolTarget.Font = new Font("맑은 고딕", 11, FontStyle.Bold);
        _woolTarget.Dock = DockStyle.Fill;
        _woolTarget.Margin = new Padding(5, 4, 5, 0);
        _woolTarget.ValueChanged += (_, _) =>
        {
            try
            {
                _lifeSettings.WoolTarget = decimal.ToInt32(_woolTarget.Value);
                _lifeSettings.Save(LifeSettingsPath);
                _lifeSettingsError = null;
                _log.Write($"[생활] 양털 목표 수량 저장: {_lifeSettings.WoolTarget}");
            }
            catch (Exception ex) { _lifeSettingsError = ex.Message; _log.Write("[생활] 설정 저장 실패: " + ex.Message); }
            UpdateLifePanel();
        };
        panel.Controls.Add(_woolTarget, 1, 0);
        foreach (var label in new[] { _lifeStageValue, _lifeTemplateValue })
        {
            label.Dock = DockStyle.Fill;
            label.AutoEllipsis = true;
            label.ForeColor = Muted;
            label.Font = new Font("맑은 고딕", 9);
            label.Padding = new Padding(10, 0, 4, 0);
            label.TextAlign = ContentAlignment.MiddleLeft;
        }
        panel.Controls.Add(_lifeStageValue, 0, 1);
        panel.SetColumnSpan(_lifeStageValue, 2);
        panel.Controls.Add(_lifeTemplateValue, 0, 2);
        panel.SetColumnSpan(_lifeTemplateValue, 2);
        _lifePanel = panel;
        RefreshLifeReadiness();
        return panel;
    }

    private void RefreshLifeReadiness()
    {
        try
        {
            var cfg = AutomationConfig.Load(Path.Combine(AppContext.BaseDirectory, "config.json"));
            var profile = LifeProfile.Load(Path.Combine(LifeBase, "profile.json"));
            _lifeProblems = profile.Validate(LifeBase, cfg.ClientWidth, cfg.ClientHeight);
        }
        catch (Exception ex) { _lifeProblems = new() { "생활 이미지 설정 확인 필요: " + ex.Message }; }
        UpdateLifePanel();
    }

    private void UpdateLifePanel()
    {
        bool selected = (_activeMode ?? SelectedMode) == "생활";
        if (_lifePanel is not null) _lifePanel.Visible = selected;
        if (_lifeModeLayout is not null) _lifeModeLayout.RowStyles[2].Height = selected ? 36 : 74;
        if (_dashboard is not null)
        {
            _dashboard.RowStyles[0].Height = selected ? 60 : 47;
            _dashboard.RowStyles[1].Height = selected ? 40 : 53;
        }
        _woolTarget.Enabled = !AnyRunning;
        if (_lifeNav is not null)
        {
            _lifeNav.Enabled = !AnyRunning;
            _lifeNav.BackColor = selected ? Accent : NavBg;
        }
        _lifeStageValue.Text = $"현재 단계: {_lifeStage}" + (_lifeWool is { } n ? $" · 양털 {n:N0}" : "");
        _lifeTemplateValue.Text = _lifeSettingsError is not null ? "목표 수량 저장 확인 필요"
            : _lifeProblems.Count > 0 ? "단계 이미지 등록 필요 · F8 재확인" : "옷감 가공 준비 완료";
        _lifeTemplateValue.ForeColor = _lifeSettingsError is null && _lifeProblems.Count == 0 ? Green : Color.Orange;
    }

    private async Task StartLifeAsync()
    {
        _starting = true;
        _cancelStart = false;
        _lifeCts = new CancellationTokenSource();
        string? error = null;
        try
        {
            RefreshLifeReadiness();
            if (_lifeSettingsError is not null) throw new InvalidOperationException(_lifeSettingsError);
            if (_lifeProblems.Count > 0)
            {
                SetStatus("생활 이미지 준비 필요", Color.Orange);
                _log.Write("[생활] 시작 전 확인: " + string.Join(" / ", _lifeProblems));
                return;
            }
            _lifeSettings.Save(LifeSettingsPath);
            var cfg = AutomationConfig.Load(Path.Combine(AppContext.BaseDirectory, "config.json"));
            var shared = LoadJson<AppSettings>(Path.Combine(AppContext.BaseDirectory, "dungeon", "config", "appsettings.json"));
            var profile = LifeProfile.Load(Path.Combine(LifeBase, "profile.json"));
            var token = _lifeCts.Token;
            if (_cancelStart || IsDisposed) return;
            _activeMode = "생활";
            _mode.Enabled = false;
            _lifeStartedAt = DateTime.Now;
            _lifeStoppedAt = null;
            _lifeBatches = _lifeLoops = 0;
            _lifeWool = null;
            _lifeStage = "시작 준비";
            _networkRetryCount = 0;
            int target = _lifeSettings.WoolTarget;
            SetStatus("생활 실행 중", Blue);
            _lifeTask = Task.Run(async () =>
            {
                token.ThrowIfCancellationRequested();
                using var engine = new LifeEngine(cfg, shared, profile, LifeBase, target, _log);
                Ui(() => _inputValue.Text = engine.InputName);
                engine.Progress += (stage, batches, loops, wool) => Ui(() =>
                {
                    _lifeStage = stage;
                    _lifeBatches = batches;
                    _lifeLoops = loops;
                    if (wool is not null) _lifeWool = wool;
                    UpdateStats();
                });
                await engine.RunAsync(token);
            }, token);
            _starting = false;
            UpdateStats();
            await _lifeTask;
        }
        catch (OperationCanceledException) { _log.Write("[생활] 정지(F10/원격 정지)"); }
        catch (Exception ex)
        {
            error = ex.Message;
            _log.Write("[생활] 오류: " + error);
            _logExpanded = true;
            ApplyLogVisibility();
            _ = _notifier.SendAlertAsync("생활 매크로 오류", error, true);
        }
        finally
        {
            _starting = false;
            bool ran = _activeMode == "생활";
            if (ran) { _activeMode = null; _lifeStoppedAt = DateTime.Now; }
            _mode.Enabled = true;
            _lifeCts?.Dispose();
            _lifeCts = null;
            _lifeStage = error is not null ? "오류로 중지" : ran ? "중지" : "준비";
            UpdateAbyssSelectorVisibility();
            if (ran) SetStatus(error is null ? "생활 중지" : "생활 오류로 중지", error is null ? Green : Color.Salmon);
            else if (error is not null) SetStatus("생활 시작 실패", Color.Salmon);
            UpdateStats();
        }
    }

    private void StopLife()
    {
        if (_lifeCts is { IsCancellationRequested: false })
        {
            _lifeCts.Cancel();
            _lifeStage = "정지 요청 처리 중";
        }
    }

    private void UpdateLifeStats()
    {
        var elapsed = _lifeStartedAt.HasValue ? (_lifeStoppedAt ?? DateTime.Now) - _lifeStartedAt.Value : TimeSpan.Zero;
        _elapsedValue.Text = elapsed.ToString(@"hh\:mm\:ss");
        _roundValue.Text = _lifeBatches.ToString();
        _successValue.Text = _lifeBatches.ToString();
        _failureValue.Text = "—";
        _rateValue.Text = "—";
        _averageValue.Text = _lifeBatches > 0 ? TimeSpan.FromSeconds(elapsed.TotalSeconds / _lifeBatches).ToString(@"mm\:ss") : "—";
        _startTimeValue.Text = _lifeStartedAt?.ToString("HH:mm:ss") ?? "—";
    }
}
