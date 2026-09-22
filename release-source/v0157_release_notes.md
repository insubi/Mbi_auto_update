V0.1.57 - 자동업데이트 복구 및 부트스트랩 수정

자동업데이트가 동작하지 않던 원인을 실제 V0.1.55 Windows_Lite 패키지와 구형 업데이터로 재현해 확인했습니다.

확인된 원인:
- V0.1.55/56 Windows_Lite 루트에 START.cmd가 빠져 있었음
- 기존 ApplyUpdate.ps1은 업데이트 적용 후 START.cmd를 무조건 실행하도록 되어 있었음
- 더 근본적으로, 구형 ApplyUpdate.ps1이 BOM 없는 UTF-8로 저장돼 있어 Windows PowerShell 5.1에서 한글 문자열이 깨지며 ParserError가 발생할 수 있었음

V0.1.57 수정:
- Windows_Lite 루트에 START.cmd 복구
- 새 ApplyUpdate.ps1을 UTF-8 BOM + CRLF로 저장해 Windows PowerShell 5.1 호환
- 업데이트 후 START.cmd 우선 실행
- START.cmd가 없어도 release/FishingAutomation.exe를 직접 실행하는 fallback 추가
- 기존 health check / rollback 구조 유지
- V0.1.55/56 설치본용 1회 복구 파일 REPAIR_AUTO_UPDATE.cmd 제공
  - 기존 tools/ApplyUpdate.ps1에 UTF-8 BOM 추가
  - START.cmd 생성
  - 이후 프로그램 재실행 시 내장 자동업데이트가 다시 동작할 수 있게 복구

안전 범위:
- V0.1.56 진단 기능 그대로 유지
- 어비스 / 일반 던전 / 페카 심층 / 낚시 / F10 / UI / 인식 조건 / 클릭 좌표 변경 없음
- 자동업데이트 부트스트랩과 버전 메타데이터 외 게임 동작 파일은 변경 금지 검증

릴리즈 전 검증:
- V0.1.55 Windows_Lite에 START.cmd가 없는 상태 재현
- V0.1.55의 BOM 없는 updater ParserError 재현
- 1회 복구 CMD 적용 후 동일한 V0.1.55 updater로 V0.1.57 ZIP 적용
- 새 EXE 0.1.57.0 확인
- startup health check 성공 및 업데이트 commit 확인
