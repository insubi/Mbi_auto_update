V0.1.57 - 자동업데이트 부트스트랩 수정

V0.1.55/56 Windows_Lite 패키지에 START.cmd가 빠져 있는데,
기존 ApplyUpdate.ps1은 업데이트 적용 후 START.cmd를 무조건 실행하도록 되어 있어
새 설치 환경에서 업데이트 후 재실행 단계가 실패하고 롤백될 수 있던 문제를 수정했습니다.

수정 내용:
- Windows_Lite 루트에 START.cmd 다시 포함
- START.cmd는 release/FishingAutomation.exe를 실행
- 기존 V0.1.55/56 업데이터가 V0.1.57 패키지를 받을 때 START.cmd도 함께 복사하므로
  구버전에서도 자동업데이트 경로를 복구 가능
- V0.1.57의 ApplyUpdate.ps1은 START.cmd가 있으면 사용
- START.cmd가 없어도 release/FishingAutomation.exe 직접 실행 fallback 추가
- 새 버전 health check / rollback 구조는 그대로 유지
- V0.1.56 진단 기능 유지
- 어비스/일반 던전/페카 심층/낚시/F10/UI/인식/좌표 로직 변경 없음

검증:
- V0.1.55 Windows_Lite 패키지에 START.cmd가 실제로 없는 것을 재현
- V0.1.55의 기존 ApplyUpdate.ps1로 V0.1.57 Windows_Lite를 적용하는 end-to-end 업데이트 테스트 수행
- 새 버전 실행 및 health check 성공 후 0.1.57 파일 버전 확인
