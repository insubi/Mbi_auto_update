#!/usr/bin/env python3
import base64, json, pathlib, sys

root = pathlib.Path(sys.argv[1]).resolve()
parts = pathlib.Path(__file__).with_name('v32_parts')


def patch(rel, old, new):
    p = root / rel
    s = p.read_text(encoding='utf-8-sig')
    if old not in s:
        raise SystemExit('patch marker missing: ' + rel)
    p.write_text(s.replace(old, new, 1), encoding='utf-8-sig')

patch('FishingAutomation/UpdateManager.cs',
      'public const string CurrentVersion = "v31";',
      'public const string CurrentVersion = "v32";')

patch('FishingAutomation/Dungeon/Models.cs',
      '    public double Threshold { get; set; } = 0.75;\n    public int MaxEditDistance { get; set; } = 1;',
      '    public double Threshold { get; set; } = 0.75;\n'
      '    public double TemplateScaleMin { get; set; } = 1.0;\n'
      '    public double TemplateScaleMax { get; set; } = 1.0;\n'
      '    public double TemplateScaleStep { get; set; } = 0.10;\n'
      '    public int MaxEditDistance { get; set; } = 1;')

patch('FishingAutomation/Dungeon/TargetDetector.cs',
'''        if (t.Kind.Equals("template", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(t.TemplatePath)) return DetectionResult.NotFound;
            return _template.Find(frame, roi, t.TemplatePath, t.Threshold);
        }

        throw new NotSupportedException($"알 수 없는 타깃 종류: {t.Kind}");''',
'''        if (t.Kind.Equals("template", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(t.TemplatePath)) return DetectionResult.NotFound;
            return _template.FindMultiScale(
                frame, roi, t.TemplatePath, t.Threshold,
                t.TemplateScaleMin, t.TemplateScaleMax, t.TemplateScaleStep);
        }

        if (t.Kind.Equals("hybrid", StringComparison.OrdinalIgnoreCase))
        {
            if (!string.IsNullOrWhiteSpace(t.TemplatePath))
            {
                var visual = _template.FindMultiScale(
                    frame, roi, t.TemplatePath, t.Threshold,
                    t.TemplateScaleMin, t.TemplateScaleMax, t.TemplateScaleStep);
                if (visual.Found) return visual;
            }

            if (!string.IsNullOrWhiteSpace(t.Text))
            {
                return await _ocr.FindTextAsync(
                    frame, roi, t.Text, t.MaxEditDistance, t.OcrRetryAt2x, ct);
            }

            return DetectionResult.NotFound;
        }

        throw new NotSupportedException($"알 수 없는 타깃 종류: {t.Kind}");''')

matcher = parts / 'TemplateMatcher.cs.txt'
if not matcher.is_file():
    raise SystemExit('missing TemplateMatcher.cs.txt')
(root / 'FishingAutomation/Dungeon/TemplateMatcher.cs').write_text(
    matcher.read_text(encoding='utf-8-sig'), encoding='utf-8-sig')

b64_path = parts / 'scene_skip_phone_q85.jpg.b64'
image = base64.b64decode(b64_path.read_text(encoding='ascii').strip(), validate=True)
if len(image) < 1000:
    raise SystemExit('scene template image is unexpectedly small')

for rel in [
    'FishingAutomation/dungeon/templates/scene_skip_phone.jpg',
    'FishingAutomation/abyss/templates/scene_skip_phone.jpg',
    'FishingAutomation/dungeon_config/templates/scene_skip_phone.jpg',
]:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(image)

for rel in [
    'FishingAutomation/dungeon/config/targets.json',
    'FishingAutomation/abyss/config/targets.json',
    'FishingAutomation/dungeon_config/targets.json',
]:
    p = root / rel
    data = json.loads(p.read_text(encoding='utf-8-sig'))
    scene = next((x for x in data if x.get('Id') == 'scene_skip'), None)
    if scene is None:
        raise SystemExit('scene_skip missing: ' + rel)
    scene.update({
        'Kind': 'hybrid',
        'TemplatePath': 'templates/scene_skip_phone.jpg',
        'Threshold': 0.62,
        'TemplateScaleMin': 0.50,
        'TemplateScaleMax': 1.40,
        'TemplateScaleStep': 0.08,
        'Text': '장면 넘기기',
        'MaxEditDistance': 1,
        'OcrRetryAt2x': True,
    })
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

(root / 'CHANGES_v32_SCENE_SKIP_HYBRID.txt').write_text(
    'MABI AUTO v32\n'
    '- 장면 넘기기: 이미지 다중 스케일 우선 + 한국어 OCR 폴백\n'
    '- 던전/어비스 모두 적용\n', encoding='utf-8')

print('Applied v32 scene-skip hybrid update')
