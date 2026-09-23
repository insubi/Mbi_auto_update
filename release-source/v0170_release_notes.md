# Mabi Auto V0.1.70

V0.1.69 텔레그램 전리품 명령 수신 문제를 수정한 버전입니다.

## 원인

`MainForm.Telegram.cs`에는 `/item`, `/itemreset` 처리 코드가 있었지만,
`TelegramNotifier.cs`의 수신 허용 목록에는 기존 `/status /stop /restart /help`만 등록되어 있어
새 명령이 핸들러까지 전달되기 전에 무시되고 있었습니다.

## 수정

- 텔레그램 수신 허용 목록에 `/item` 추가
- 텔레그램 수신 허용 목록에 `/itemreset` 추가
- `/help` 안내에도 두 명령 추가
- 기존 `/status /stop /restart /help` 유지

## 유지 사항

- 전리품 11종 카운팅/저장 방식 변경 없음
- 이번 실행 / 오늘 / 누적 통계 유지
- `/itemreset`은 누적만 즉시 초기화
- 어비스 진행/사망/클리어/다시 하기 로직 변경 없음
