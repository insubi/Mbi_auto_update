# Mbi_auto_update

MABI AUTO 자동 업데이트/자동 빌드 배포 저장소입니다.

## 현재 버전
- v58 (v57 기능 유지, 배포 구조 안전 최적화)

## 배포 흐름
1. `release-source/`에 새 버전 소스 ZIP, 패치, 또는 `v*_apply.py`를 올립니다.
2. `Publish Release Source`가 이전 버전에 변경분을 적용해 초안 GitHub Release를 만듭니다.
3. `Build Windows Lite`가 Windows 환경에서 .NET 8로 실제 빌드합니다.
4. 파일 구성, 실행·Watchdog 시작, 기존 updater의 사용자 설정 보존을 검증합니다.
5. self-contained Windows x64 완성본과 SHA256 파일을 업로드한 뒤 Release를 공개합니다. 실패하면 초안으로 유지됩니다.

## 프로그램 자동 업데이트
- 프로그램은 실행 후 GitHub 최신 정식 Release를 자동 확인합니다.
- v52부터 새 버전이 있으면 시작 시 자동 다운로드 및 SHA256 검증 후 자동 적용합니다.
- 설정, 텔레그램 정보, 이미지 템플릿은 업데이트 시 유지됩니다.
- 새 버전 실행에 실패하면 기존 업데이트 복구 절차를 사용합니다.
- 수동 `업데이트 확인` 버튼도 계속 사용할 수 있습니다.

## 사용자가 받는 파일
완성본은 아래 형식입니다.
- `MabiAuto_v58_Windows_Lite.zip`
- `MabiAuto_v58_Windows_Lite.zip.sha256`

## v58 안전 최적화 범위
- 게임 동작 C# 소스는 v57 Windows 빌드 입력과 동일합니다. 업데이트 버전 상수와 어셈블리 버전만 v58로 변경합니다.
- v57 ZIP의 `Dungeon`/`dungeon` 중복은 Windows에서 사용하던 최종 파일 내용으로 통일합니다.
- Windows_Lite에는 실행 파일, 네이티브 종속성, 사용 중인 설정·템플릿, 기존 설치·설정·업데이트 도구만 포함합니다.
- `.pdb`, 로그, 임시 파일, C# 소스, 테스트 이미지, 드라이버 샘플/참고 파일은 배포 목록에 포함하지 않습니다.
- `release`와 `FishingAutomation`의 설정·템플릿 사본은 실행부·UI·진단·설정 도구가 각각 참조하므로 유지합니다.
- `release/MacroWatchdog.exe`, `tools/ApplyUpdate.ps1` 및 기존 updater 로직을 유지합니다.
- .NET self-contained, 단일 파일 압축, OpenCV/OCR/WinForms 종속성을 유지하고 trimming/AOT는 비활성화합니다.
- Actions의 `v58-packaging-verification` 아티팩트에 소스 해시, 전체 배포 파일 목록, 업데이트 보존 테스트 결과가 남습니다.
- Windows 빌드 스크립트는 검증된 v58용입니다. 후속 버전에서는 버전별 소스 감사와 배포 스크립트를 함께 갱신해야 합니다.

Windows Lite ZIP에는 실행에 필요한 .NET 런타임이 포함되므로 사용자 PC에 .NET SDK를 설치할 필요가 없습니다.
압축을 푼 뒤 Interception 드라이버가 이미 설치되어 있으면 `START.cmd`만 실행하면 됩니다.

## 개발/소스 ZIP
`CombinedFishingDungeon_*.zip` 같은 소스 ZIP은 자동 빌드 입력용입니다.
일반 사용자는 `*_Windows_Lite.zip`을 받는 것을 권장합니다.

## 보안
텔레그램 Bot Token, Chat ID 등 개인 설정이 들어간 파일은 Release에 업로드하지 마세요.
