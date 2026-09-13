using DungeonVisionBot;

namespace FishingAutomation;

public sealed partial class MainForm
{
    private readonly List<Button> _tabs = new();
    private readonly List<Button> _dungeonButtons = new();
    private readonly Label _stageTime = new();
    private readonly Label _timeoutValue = new();
    private readonly Label _miniStatus = new();
    private readonly Label _miniInfo = new();
    private readonly Label _currentDungeonValue = new();
    private readonly Label _readyBadge = new();
    private readonly Label _failureValue = new();
    private readonly Label _averageValue = new();
    private readonly Label _startTimeValue = new();
    private readonly Label _sysGameValue = new();
    private readonly Label _sysTemplateValue = new();
    private readonly Label _sysOcrValue = new();
    private readonly Label _sysInputValue = new();
    private readonly Label _sysTelegramValue = new();
    private readonly Label _sysUpdateValue = new();
    private readonly Label _telegramQuickValue = new();
    private readonly Label _updateStatusValue = new();
    private Panel _fullView = null!;
    private Panel _miniView = null!;
    private Control _dungeonPicker = null!;
    private Control _logView = null!;
    private TableLayoutPanel _dashboard = null!;
    private Button _logToggle = null!;
    private Button _updateButton = null!;
    private bool _mini, _logExpanded = true;
    private Size _fullSize;
    private DateTime? _stageStartedAt, _restartAt, _dungeonStoppedAt, _fishingStoppedAt;
    private int _stageLimit = 600, _timeoutExits;
    private string? _runError;

    private static readonly Color NavBg = Color.FromArgb(5, 26, 46);
    private static readonly Color CardBg = Color.FromArgb(10, 39, 66);
    private static readonly Color CardBg2 = Color.FromArgb(9, 34, 58);
    private static readonly Color Accent = Color.FromArgb(20, 132, 255);
    private static readonly Color AccentSoft = Color.FromArgb(20, 83, 145);
    private static readonly Color Muted = Color.FromArgb(155, 183, 209);

    private Button SmallButton(string caption, Action action)
    {
        var b = new Button
        {
            Text = caption,
            AutoSize = false,
            Height = 38,
            Width = 135,
            FlatStyle = FlatStyle.Flat,
            BackColor = CardBg2,
            ForeColor = TitleText,
            Margin = new Padding(4),
            Cursor = Cursors.Hand,
            Font = new Font("맑은 고딕", 9f, FontStyle.Bold)
        };
        b.FlatAppearance.BorderColor = Border;
        b.FlatAppearance.MouseOverBackColor = AccentSoft;
        b.Click += (_, _) => action();
        return b;
    }

    private Button NavButton(string caption, Action action, bool selected = false)
    {
        var b = new Button
        {
            Text = caption,
            Dock = DockStyle.Top,
            Height = 58,
            FlatStyle = FlatStyle.Flat,
            BackColor = selected ? Color.FromArgb(19, 95, 176) : NavBg,
            ForeColor = Color.FromArgb(222, 238, 252),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(18, 0, 0, 0),
            Margin = new Padding(0, 2, 0, 2),
            Font = new Font("맑은 고딕", 10.5f, selected ? FontStyle.Bold : FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        b.FlatAppearance.BorderSize = 0;
        b.FlatAppearance.MouseOverBackColor = Color.FromArgb(12, 58, 99);
        b.Click += (_, _) => action();
        return b;
    }

    private Label TextLabel(string text, float size = 10) => new()
    {
        Text = text,
        AutoSize = false,
        Dock = DockStyle.Fill,
        ForeColor = TitleText,
        TextAlign = ContentAlignment.MiddleLeft,
        Font = new Font("맑은 고딕", size),
        AutoEllipsis = true,
        Padding = new Padding(10, 0, 10, 0)
    };

    private Label SectionTitle(string text) => new()
    {
        Text = text,
        Dock = DockStyle.Top,
        Height = 48,
        ForeColor = TitleText,
        Font = new Font("맑은 고딕", 12f, FontStyle.Bold),
        TextAlign = ContentAlignment.MiddleLeft,
        Padding = new Padding(16, 0, 0, 0)
    };

    private Panel Card(string title)
    {
        var panel = CreateCard();
        panel.Padding = new Padding(14);
        var head = SectionTitle(title);
        head.Padding = new Padding(2, 0, 0, 0);
        panel.Controls.Add(head);
        head.BringToFront();
        return panel;
    }

    private void BuildLayout()
    {
        _mode.Items.AddRange(new object[] { "낚시", "던전", "어비스", "생활" });
        _mode.SelectedIndex = 0;
        _abyssDungeon.Items.AddRange(new object[] { "허상의 정박지", "광기의 동굴", "흩어진 물길" });
        _abyssDungeon.SelectedIndex = 0;

        _fullView = new Panel { Dock = DockStyle.Fill, BackColor = WindowBg };
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3, Margin = Padding.Empty, Padding = Padding.Empty };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 78));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));

        root.Controls.Add(BuildHeader(), 0, 0);
        root.Controls.Add(BuildMainBody(), 0, 1);
        root.Controls.Add(BuildFooter(), 0, 2);
        _fullView.Controls.Add(root);
        Controls.Add(_fullView);

        _miniView = new Panel { Dock = DockStyle.Fill, Visible = false, Padding = new Padding(12), BackColor = NavBg };
        var ml = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3 };
        ml.RowStyles.Add(new RowStyle(SizeType.Percent, 45));
        ml.RowStyles.Add(new RowStyle(SizeType.Percent, 25));
        ml.RowStyles.Add(new RowStyle(SizeType.Percent, 30));
        foreach (var label in new[] { _miniStatus, _miniInfo })
        {
            label.Dock = DockStyle.Fill;
            label.ForeColor = TitleText;
            label.AutoEllipsis = true;
            label.TextAlign = ContentAlignment.MiddleLeft;
            label.Font = new Font("맑은 고딕", 10f, FontStyle.Bold);
            ml.Controls.Add(label);
        }
        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill };
        var ms = SmallButton("정지 (F10)", StopSelected); ms.BackColor = Color.FromArgb(170, 49, 63);
        actions.Controls.Add(ms);
        actions.Controls.Add(SmallButton("전체 화면", () => ToggleMini(false)));
        ml.Controls.Add(actions, 0, 2);
        _miniView.Controls.Add(ml);
        Controls.Add(_miniView);
        ApplyLogVisibility();
    }

    private Control BuildHeader()
    {
        var header = new Panel { Dock = DockStyle.Fill, BackColor = NavBg, Padding = new Padding(24, 8, 18, 8) };
        header.Paint += (_, e) => e.Graphics.DrawLine(new Pen(Color.FromArgb(20, 78, 119)), 0, header.Height - 1, header.Width, header.Height - 1);

        var title = new Label
        {
            Text = "MABI AUTO",
            Dock = DockStyle.Left,
            Width = 250,
            ForeColor = Color.White,
            Font = new Font("Segoe UI", 20f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft
        };
        var subtitle = new Label
        {
            Text = "마비노기 모바일 매크로  ·  Dashboard v33",
            Dock = DockStyle.Left,
            Width = 420,
            ForeColor = Muted,
            Font = new Font("맑은 고딕", 9.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(0, 8, 0, 0)
        };
        _readyBadge.Text = "●  매크로 준비됨";
        _readyBadge.Dock = DockStyle.Right;
        _readyBadge.Width = 170;
        _readyBadge.TextAlign = ContentAlignment.MiddleCenter;
        _readyBadge.ForeColor = Color.FromArgb(56, 241, 148);
        _readyBadge.BackColor = Color.FromArgb(5, 48, 64);
        _readyBadge.Font = new Font("맑은 고딕", 9.5f, FontStyle.Bold);

        header.Controls.Add(_readyBadge);
        header.Controls.Add(subtitle);
        header.Controls.Add(title);
        return header;
    }

    private Control BuildMainBody()
    {
        var body = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, Padding = Padding.Empty, Margin = Padding.Empty };
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 205));
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        body.Controls.Add(BuildSidebar(), 0, 0);
        body.Controls.Add(BuildDashboardGrid(), 1, 0);
        return body;
    }

    private Control BuildSidebar()
    {
        var side = new Panel { Dock = DockStyle.Fill, BackColor = NavBg, Padding = new Padding(10, 18, 10, 12) };
        var menu = new TableLayoutPanel { Dock = DockStyle.Top, Height = 406, ColumnCount = 1, RowCount = 7 };
        for (int i = 0; i < 7; i++) menu.RowStyles.Add(new RowStyle(SizeType.Absolute, 58));
        menu.Controls.Add(NavButton("⌂   홈", () => { }, true), 0, 0);
        menu.Controls.Add(NavButton("⚔   던전 설정", () => OpenPackagePath(Path.Combine("FishingAutomation", "abyss", "config"))), 0, 1);
        _lifeNav = NavButton("생활", () => { if (!AnyRunning && _activeMode is null) _mode.SelectedIndex = 3; });
        menu.Controls.Add(_lifeNav, 0, 2);
        menu.Controls.Add(NavButton("▣   이미지 설정", () => OpenPackagePath(Path.Combine("FishingAutomation", "abyss", "templates"))), 0, 3);
        menu.Controls.Add(NavButton("➤   텔레그램 알림", OpenPhoneAlertSetup), 0, 4);
        menu.Controls.Add(NavButton("▤   로그", OpenLogFolder), 0, 5);
        menu.Controls.Add(NavButton("⚙   설정", () => OpenPackagePath(Path.Combine("FishingAutomation", "config.json"))), 0, 6);

        var tip = new Label
        {
            Dock = DockStyle.Bottom,
            Height = 115,
            Text = "좋은 하루 되세요!\r\n\r\nF9 시작  ·  F10 정지\r\nF8 테스트 / 새로고침",
            ForeColor = Muted,
            Font = new Font("맑은 고딕", 9f),
            TextAlign = ContentAlignment.MiddleCenter
        };
        side.Controls.Add(tip);
        side.Controls.Add(menu);
        return side;
    }

    private Control BuildDashboardGrid()
    {
        _dashboard = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 2,
            Padding = new Padding(14),
            BackColor = WindowBg
        };
        _dashboard.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 41));
        _dashboard.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 32));
        _dashboard.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 27));
        _dashboard.RowStyles.Add(new RowStyle(SizeType.Percent, 47));
        _dashboard.RowStyles.Add(new RowStyle(SizeType.Percent, 53));

        _dashboard.Controls.Add(BuildRunStateCard(), 0, 0);
        _dashboard.Controls.Add(BuildCurrentDungeonCard(), 1, 0);
        _dashboard.Controls.Add(BuildQuickSettingsCard(), 2, 0);
        _logView = BuildLogPanel();
        _dashboard.Controls.Add(_logView, 0, 1);
        _dashboard.Controls.Add(BuildStatsCard(), 1, 1);
        _dashboard.Controls.Add(BuildSystemStatusCard(), 2, 1);
        return _dashboard;
    }

    private Control BuildRunStateCard()
    {
        var card = CreateCard();
        card.Margin = new Padding(6);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5, Padding = new Padding(18) };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 30));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 70));
        layout.Controls.Add(SectionTitle("실행 상태"), 0, 0);

        _statusValue.Dock = DockStyle.Fill;
        _statusValue.TextAlign = ContentAlignment.MiddleLeft;
        _statusValue.Font = new Font("맑은 고딕", 20f, FontStyle.Bold);
        _statusValue.ForeColor = Green;
        _statusValue.Padding = new Padding(14, 0, 0, 0);
        layout.Controls.Add(_statusValue, 0, 1);

        foreach (var label in new[] { _stageTime, _inputValue })
        {
            label.Dock = DockStyle.Fill;
            label.ForeColor = Muted;
            label.TextAlign = ContentAlignment.MiddleLeft;
            label.AutoEllipsis = true;
            label.Padding = new Padding(14, 0, 14, 0);
            label.Font = new Font("맑은 고딕", 9f);
        }
        layout.Controls.Add(_stageTime, 0, 2);
        layout.Controls.Add(_inputValue, 0, 3);
        layout.Controls.Add(BuildButtonsPanel(), 0, 4);
        card.Controls.Add(layout);
        return card;
    }

    private Control BuildCurrentDungeonCard()
    {
        var card = CreateCard();
        card.Margin = new Padding(6);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5, Padding = new Padding(18) };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 74));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        layout.Controls.Add(SectionTitle("현재 던전 / 모드"), 0, 0);
        _lifeModeLayout = layout;

        var tabs = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 4, RowCount = 1 };
        for (int i = 0; i < 4; i++)
        {
            int index = i;
            tabs.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
            var tab = SmallButton(_mode.Items[i].ToString()!, () => { if (!AnyRunning && _activeMode is null) _mode.SelectedIndex = index; });
            tab.Dock = DockStyle.Fill;
            _tabs.Add(tab);
            tabs.Controls.Add(tab, i, 0);
        }
        layout.Controls.Add(tabs, 0, 1);

        _currentDungeonValue.Dock = DockStyle.Fill;
        _currentDungeonValue.Font = new Font("맑은 고딕", 15f, FontStyle.Bold);
        _currentDungeonValue.ForeColor = Color.White;
        _currentDungeonValue.TextAlign = ContentAlignment.MiddleLeft;
        _currentDungeonValue.Padding = new Padding(10, 0, 0, 0);
        layout.Controls.Add(_currentDungeonValue, 0, 2);

        var picker = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3 };
        for (int i = 0; i < 3; i++)
        {
            int index = i;
            picker.RowStyles.Add(new RowStyle(SizeType.Percent, 33.333f));
            var button = SmallButton(_abyssDungeon.Items[i].ToString()!, () => { if (!AnyRunning && _activeMode is null) _abyssDungeon.SelectedIndex = index; });
            button.Dock = DockStyle.Fill;
            _dungeonButtons.Add(button);
            picker.Controls.Add(button, 0, i);
        }
        _dungeonPicker = picker;
        var modeContent = new Panel { Dock = DockStyle.Fill, Margin = Padding.Empty };
        modeContent.Controls.Add(picker);
        modeContent.Controls.Add(BuildLifeSettingsPanel());
        layout.Controls.Add(modeContent, 0, 3);

        var mini = SmallButton("미니 모드", () => ToggleMini(true));
        mini.Dock = DockStyle.Fill;
        layout.Controls.Add(mini, 0, 4);
        card.Controls.Add(layout);
        return card;
    }

    private Control BuildQuickSettingsCard()
    {
        var card = CreateCard();
        card.Margin = new Padding(6);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 7, Padding = new Padding(16) };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        for (int i = 1; i <= 6; i++) layout.RowStyles.Add(new RowStyle(SizeType.Percent, 16.666f));
        layout.Controls.Add(SectionTitle("빠른 설정"), 0, 0);
        layout.Controls.Add(QuickRow("텔레그램 알림", _telegramQuickValue, OpenPhoneAlertSetup), 0, 1);
        layout.Controls.Add(QuickRow("디버그 캡처", new Label(), () => OpenLogFolder(), "이상 상황만"), 0, 2);
        layout.Controls.Add(QuickRow("자동 재시작 대기", new Label(), null, "30초"), 0, 3);
        layout.Controls.Add(QuickRow("던전 시간 제한", new Label(), null, "10분"), 0, 4);
        layout.Controls.Add(QuickRow("창 크기 (고정)", new Label(), null, "800 × 1000"), 0, 5);

        var update = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
        update.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 56));
        update.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 44));
        _updateStatusValue.Text = "업데이트 확인 중...";
        _updateStatusValue.Dock = DockStyle.Fill;
        _updateStatusValue.ForeColor = Muted;
        _updateStatusValue.TextAlign = ContentAlignment.MiddleLeft;
        _updateStatusValue.Font = new Font("맑은 고딕", 8.5f);
        _updateButton = SmallButton("업데이트 확인", () => _ = CheckForUpdatesAsync(true));
        _updateButton.Dock = DockStyle.Fill;
        update.Controls.Add(_updateStatusValue, 0, 0);
        update.Controls.Add(_updateButton, 1, 0);
        layout.Controls.Add(update, 0, 6);
        card.Controls.Add(layout);
        return card;
    }

    private Control QuickRow(string caption, Label value, Action? action = null, string? defaultValue = null)
    {
        var row = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 60));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 40));
        row.Controls.Add(new Label { Text = caption, Dock = DockStyle.Fill, ForeColor = TitleText, TextAlign = ContentAlignment.MiddleLeft, Font = new Font("맑은 고딕", 9f) }, 0, 0);
        value.Text = defaultValue ?? "—";
        value.Dock = DockStyle.Fill;
        value.ForeColor = Color.FromArgb(113, 191, 255);
        value.TextAlign = ContentAlignment.MiddleRight;
        value.Font = new Font("맑은 고딕", 8.8f, FontStyle.Bold);
        if (action is not null)
        {
            value.Cursor = Cursors.Hand;
            value.Click += (_, _) => action();
        }
        row.Controls.Add(value, 1, 0);
        return row;
    }

    private Control BuildStatsCard()
    {
        var card = CreateCard();
        card.Margin = new Padding(6);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 7, Padding = new Padding(18) };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        for (int i = 1; i < 7; i++) layout.RowStyles.Add(new RowStyle(SizeType.Percent, 16.666f));
        layout.Controls.Add(SectionTitle("오늘의 기록"), 0, 0);
        layout.Controls.Add(StatRow("진행 횟수", _roundValue), 0, 1);
        layout.Controls.Add(StatRow("성공 횟수", _successValue), 0, 2);
        layout.Controls.Add(StatRow("실패 / 시간초과", _failureValue), 0, 3);
        layout.Controls.Add(StatRow("평균 소요 시간", _averageValue), 0, 4);
        layout.Controls.Add(StatRow("시작 시간", _startTimeValue), 0, 5);
        card.Controls.Add(layout);
        return card;
    }

    private Control StatRow(string caption, Label value)
    {
        var row = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 60));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 40));
        row.Controls.Add(new Label { Text = caption, Dock = DockStyle.Fill, ForeColor = Muted, TextAlign = ContentAlignment.MiddleLeft, Font = new Font("맑은 고딕", 9.5f) }, 0, 0);
        value.Dock = DockStyle.Fill;
        value.ForeColor = TitleText;
        value.TextAlign = ContentAlignment.MiddleRight;
        value.Font = new Font("맑은 고딕", 10f, FontStyle.Bold);
        row.Controls.Add(value, 1, 0);
        return row;
    }

    private Control BuildSystemStatusCard()
    {
        var card = CreateCard();
        card.Margin = new Padding(6);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 7, Padding = new Padding(18) };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        for (int i = 1; i < 7; i++) layout.RowStyles.Add(new RowStyle(SizeType.Percent, 16.666f));
        layout.Controls.Add(SectionTitle("시스템 상태"), 0, 0);
        layout.Controls.Add(StatusRow("게임 창 인식", _sysGameValue), 0, 1);
        layout.Controls.Add(StatusRow("이미지 템플릿", _sysTemplateValue), 0, 2);
        layout.Controls.Add(StatusRow("OCR", _sysOcrValue), 0, 3);
        layout.Controls.Add(StatusRow("키보드 입력", _sysInputValue), 0, 4);
        layout.Controls.Add(StatusRow("텔레그램 연결", _sysTelegramValue), 0, 5);
        layout.Controls.Add(StatusRow("업데이트 서버", _sysUpdateValue), 0, 6);
        card.Controls.Add(layout);
        return card;
    }

    private Control StatusRow(string caption, Label value)
    {
        var row = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 60));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 40));
        row.Controls.Add(new Label { Text = "●  " + caption, Dock = DockStyle.Fill, ForeColor = Color.FromArgb(64, 229, 145), TextAlign = ContentAlignment.MiddleLeft, Font = new Font("맑은 고딕", 9f) }, 0, 0);
        value.Dock = DockStyle.Fill;
        value.ForeColor = Green;
        value.TextAlign = ContentAlignment.MiddleRight;
        value.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
        row.Controls.Add(value, 1, 0);
        return row;
    }

    private Control BuildFooter()
    {
        var footer = new Panel { Dock = DockStyle.Fill, BackColor = NavBg, Padding = new Padding(16, 0, 16, 0) };
        footer.Controls.Add(new Label { Text = "작은 반복이, 더 큰 모험을 만듭니다.", Dock = DockStyle.Left, Width = 360, ForeColor = Muted, TextAlign = ContentAlignment.MiddleLeft, Font = new Font("맑은 고딕", 8.5f) });
        footer.Controls.Add(new Label { Text = "v33  |  Mabi Auto", Dock = DockStyle.Right, Width = 150, ForeColor = Muted, TextAlign = ContentAlignment.MiddleRight, Font = new Font("Segoe UI", 8.5f) });
        return footer;
    }

    private void ApplyLogVisibility()
    {
        if (_logView is not null) _logView.Visible = true;
        if (_logToggle is not null) _logToggle.Text = "실행 로그";
    }

    private void ToggleMini(bool enabled)
    {
        if (_mini == enabled) return;
        SuspendLayout();
        _mini = enabled;
        if (enabled)
        {
            if (WindowState != FormWindowState.Normal) WindowState = FormWindowState.Normal;
            _fullSize = Size;
            MinimumSize = new Size(420, 230);
            Size = new Size(560, 280);
        }
        else
        {
            MinimumSize = new Size(1120, 720);
            Size = _fullSize;
        }
        _fullView.Visible = !enabled;
        _miniView.Visible = enabled;
        TopMost = enabled;
        if (enabled) _miniView.BringToFront(); else _fullView.BringToFront();
        ResumeLayout(true);
    }

    private void TrackProgress(string mode, string text)
    {
        if (text.Contains("판 시작")) { _stageStartedAt = _restartAt = null; SetStatus("입장 대기", Blue); }
        if (text.Contains("대기:"))
        {
            if (text.Contains("abyss_touch_screen"))
            {
                _stageStartedAt = DateTime.Now;
                var match = System.Text.RegularExpressions.Regex.Match(text, @"/ (\d+)s");
                _stageLimit = match.Success ? int.Parse(match.Groups[1].Value) : 600;
                SetStatus("던전 진행 중 · 클리어 화면 대기", Blue);
            }
            else if (text.Contains("abyss_treasure_chest")) { _stageStartedAt = null; SetStatus("보상 확인 · 보물상자 대기", Blue); }
            else if (text.Contains("abyss_exit") || text.Contains("abyss_leave_dungeon")) SetStatus("퇴장 중", Blue);
            else SetStatus(text.Split(']')[0].TrimStart('['), Blue);
        }
        if (text.Contains("[자동복구]")) SetStatus("자동 복구 중", Color.Orange);
        if (text.Contains("퇴장 절차 시작")) { _timeoutExits++; _stageStartedAt = null; SetStatus("10분 제한 초과 · 퇴장 중", Color.Orange); }
        if (text.Contains("강제 퇴장 완료"))
        {
            var match = System.Text.RegularExpressions.Regex.Match(text, @"-> (\d+)초");
            _restartAt = DateTime.Now.AddSeconds(match.Success ? int.Parse(match.Groups[1].Value) : 30);
            SetStatus("재시작 대기", Color.Orange);
        }
        if (text.Contains("판 완료")) { _stageStartedAt = null; SetStatus("완료 · 다음 입장 준비", Green); }
    }

    private void UpdateDashboard()
    {
        if (_dashboard is null) return;
        bool idle = !AnyRunning && _activeMode is null;
        for (int i = 0; i < _tabs.Count; i++)
        {
            _tabs[i].Enabled = idle;
            _tabs[i].BackColor = i == _mode.SelectedIndex ? Accent : CardBg2;
        }
        for (int i = 0; i < _dungeonButtons.Count; i++)
        {
            _dungeonButtons[i].Enabled = idle;
            _dungeonButtons[i].BackColor = i == _abyssDungeon.SelectedIndex ? AccentSoft : CardBg2;
        }
        bool abyss = (_activeMode ?? SelectedMode) == "어비스";
        bool life = (_activeMode ?? SelectedMode) == "생활";
        _dungeonPicker.Visible = abyss;
        _currentDungeonValue.Text = life ? "옷감 가공" : abyss ? SelectedAbyssDungeon : (_activeMode ?? SelectedMode);
        _timeoutValue.Text = abyss ? _timeoutExits.ToString() : "—";
        UpdateLifePanel();

        if (life) _stageTime.Text = "현재 단계: " + _lifeStage;
        else if (_restartAt.HasValue && DungeonRunning)
            _stageTime.Text = $"다시 시작까지 {Math.Max(0, (int)Math.Ceiling((_restartAt.Value - DateTime.Now).TotalSeconds))}초";
        else if (_stageStartedAt.HasValue && DungeonRunning)
        {
            var elapsed = DateTime.Now - _stageStartedAt.Value;
            _stageTime.Text = $"던전 경과 {elapsed:mm\\:ss} · 퇴장까지 {Math.Max(0, _stageLimit - (int)elapsed.TotalSeconds)}초";
        }
        else _stageTime.Text = abyss ? "10분 초과 시 자동 퇴장 · 실패 시 Smart Recovery" : "F9 시작 · F10 정지 · F8 테스트 / 새로고침";

        _miniInfo.Text = $"{(abyss ? SelectedAbyssDungeon : _activeMode ?? SelectedMode)} · {_stageTime.Text}";
        _readyBadge.Text = AnyRunning ? "●  매크로 실행 중" : "●  매크로 준비됨";
        _readyBadge.ForeColor = AnyRunning ? Color.FromArgb(89, 190, 255) : Color.FromArgb(56, 241, 148);

        var ns = _notifier.Settings;
        bool telegramConfigured = ns.Enabled && !string.IsNullOrWhiteSpace(ns.BotToken) && !string.IsNullOrWhiteSpace(ns.ChatId);
        bool telegramReady = telegramConfigured && _diagTelegramConnected == true;
        _telegramQuickValue.Text = telegramReady ? "ON" : telegramConfigured ? "CHECK" : "OFF";
        _telegramQuickValue.ForeColor = telegramReady ? Green : telegramConfigured ? Color.Orange : Color.Salmon;
        _sysTelegramValue.Text = !telegramConfigured ? "설정 필요" : _diagTelegramConnected is null ? "확인 중" : telegramReady ? "정상" : "연결 실패";
        _sysTelegramValue.ForeColor = telegramReady ? Green : telegramConfigured ? Color.Orange : Color.Salmon;

        int windows = WindowTools.EnumerateVisibleWindows().Count;
        _sysGameValue.Text = windows > 0 ? "정상" : "확인 필요";
        _sysGameValue.ForeColor = windows > 0 ? Green : Color.Orange;
        _sysInputValue.Text = _fishingBot.InputReady ? "정상" : "확인 필요";
        _sysInputValue.ForeColor = _fishingBot.InputReady ? Green : Color.Orange;
        _sysOcrValue.Text = _diagOcrAvailable is null ? "확인 중" : _diagOcrAvailable == true ? "정상" : "확인 필요";
        _sysOcrValue.ForeColor = _diagOcrAvailable == true ? Green : Color.Orange;
        bool templatesReady = life ? _lifeProblems.Count == 0 : TemplatesReady();
        _sysTemplateValue.Text = templatesReady ? "정상" : "확인 필요";
        _sysTemplateValue.ForeColor = templatesReady ? Green : Color.Orange;
        _sysUpdateValue.Text = _diagUpdateServer is null ? "확인 중" : _diagUpdateServer == true ? "정상" : "연결 실패";
        _sysUpdateValue.ForeColor = _diagUpdateServer == true ? Green : Color.Orange;
    }

    private bool TemplatesReady()
    {
        try
        {
            string root = UpdateManager.FindPackageRoot();
            return File.Exists(Path.Combine(root, "FishingAutomation", "templates", "hook.png"))
                && File.Exists(Path.Combine(root, "FishingAutomation", "templates", "gauge.png"))
                && File.Exists(Path.Combine(root, "FishingAutomation", "abyss", "templates", "menu.png"));
        }
        catch { return false; }
    }

    private void OpenPackagePath(string relative)
    {
        try
        {
            string path = Path.Combine(UpdateManager.FindPackageRoot(), relative);
            if (!File.Exists(path) && !Directory.Exists(path)) return;
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo { FileName = path, UseShellExecute = true });
        }
        catch { }
    }

    private void OpenPhoneAlertSetup()
    {
        try
        {
            string root = UpdateManager.FindPackageRoot();
            string file = Path.Combine(root, "SETUP_PHONE_ALERT.cmd");
            if (File.Exists(file)) System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo { FileName = file, WorkingDirectory = root, UseShellExecute = true });
        }
        catch { }
    }

    private void OpenLogFolder()
    {
        try
        {
            string root = UpdateManager.FindPackageRoot();
            string release = Path.Combine(root, "release");
            string path = Directory.Exists(release) ? release : root;
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo { FileName = path, UseShellExecute = true });
        }
        catch { }
    }
}
