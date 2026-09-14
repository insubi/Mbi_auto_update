# Mbi_auto_update

MABI AUTO 자동 업데이트/자동 빌드 배포 저장소입니다.

## 현재 버전
- v52

## 배포 흐름
1. `release-source/`에 새 버전 소스 ZIP, 패치, 또는 `v*_apply.py`를 올립니다.
2. `Publish Release Source`가 이전 버전에 변경분을 적용해 새 GitHub Release를 만듭니다.
3. `Build Windows Lite`가 Windows 환경에서 .NET 8로 실제 빌드합니다.
4. self-contained Windows x64 완성본과 SHA256 파일을 같은 Release에 자동 업로드합니다.

## 프로그램 자동 업데이트
- 프로그램은 실행 후 GitHub 최신 정식 Release를 자동 확인합니다.
- v52부터 새 버전이 있으면 시작 시 자동 다운로드 및 SHA256 검증 후 자동 적용합니다.
- 설정, 텔레그램 정보, 이미지 템플릿은 업데이트 시 유지됩니다.
- 새 버전 실행에 실패하면 기존 업데이트 복구 절차를 사용합니다.
- 수동 `업데이트 확인` 버튼도 계속 사용할 수 있습니다.

## 사용자가 받는 파일
완성본은 아래 형식입니다.
- `MabiAuto_v52_Windows_Lite.zip`
- `MabiAuto_v52_Windows_Lite.zip.sha256`

Windows Lite ZIP에는 실행에 필요한 .NET 런타임이 포함되므로 사용자 PC에 .NET SDK를 설치할 필요가 없습니다.
압축을 푼 뒤 Interception 드라이버가 이미 설치되어 있으면 `START.cmd`만 실행하면 됩니다.

## 개발/소스 ZIP
`CombinedFishingDungeon_*.zip` 같은 소스 ZIP은 자동 빌드 입력용입니다.
일반 사용자는 `*_Windows_Lite.zip`을 받는 것을 권장합니다.

## 보안
텔레그램 Bot Token, Chat ID 등 개인 설정이 들어간 파일은 Release에 업로드하지 마세요.
