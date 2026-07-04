**한국어** | [English](DECISIONS.en.md)

# 의사결정 로그

가벼운 ADR(아키텍처 결정 기록)입니다. 각 항목은 결정 내용, 이유, 되돌릴 수 있는지를 담습니다.
**(PM default, AFK)** 표시가 있는 결정은 오너가 자리를 비운 동안 PM이 자율적으로 되돌릴 수
있는/안전한 선택지를 골라 내린 것이며, product-lead나 오너가 언제든 페널티 없이 재검토할
수 있습니다.

## D1 — 킬 스위치는 `force_proxy`가 아니라 `anonymous_mode` 기반의 "누출 없음"으로 구현
**결정:** SOCKS5 프록시와 킬 스위치가 설정된 경우, 정확성은 `anonymous_mode=true` +
`proxy_hostnames=true`(피어/트래커/DHT 이름 조회를 모두 프록시로 라우팅)와 DHT/LSD/UPnP/NAT-PMP
비활성화에 근거합니다. 피어 탐색은 트래커 + PEX로만 폴백합니다. `force_proxy`는 더 이상
보장 수단이 아니라 지원 중단된(deprecated) 별칭으로 취급합니다.
**이유:** libtorrent 2.0.13 기준 아키텍처 검증 결과 `force_proxy`는 지원 중단되었으며,
`anonymous_mode` + `proxy_hostnames`가 누출을 막는 공식 경로임이 확인되었습니다.
**되돌릴 수 있는가:** 예(설정 값 변경 + v0.4 출시 전 누출 테스트). **(PM default, AFK)**

## D2 — 프록시 비밀번호는 MVP에서 메모리에만 저장
**결정:** MVP 동안에는 SOCKS5 비밀번호를 메모리에만 보관합니다. "기억하기" 기능을 추가하게
되면 MVP 이후 Windows DPAPI로 영속화합니다.
**이유:** 평문 비밀 값을 그대로 배포하는 것을 피하기 위함이며, DPAPI 연동은 핵심 기능에
필수적이지 않습니다.
**되돌릴 수 있는가:** 예. **(PM default, AFK)**

## D3 — 완료 후 동작: 옵트인 + 취소 가능한 30초 카운트다운
**결정:** 완료 후 동작의 기본값은 **없음(None)**입니다. 사용자가 "앱 종료" 또는
"시스템 종료"를 활성화한 경우, **취소 가능한 30초 카운트다운** 다이얼로그를 거친 뒤에만
실행됩니다. 이 다이얼로그 없이 시스템 종료가 실행되는 일은 없습니다.
**이유:** 확인 절차 없이 시스템 종료를 실행하는 것은 안전하지 않으며, 카운트다운을 두면
강력하고 되돌리기 어렵게 느껴지는 동작도 복구 가능해집니다. (product-planner가 OPEN-3로
제기한 사항.)
**되돌릴 수 있는가:** 예. **(PM default, AFK)**

## D4 — `TorrentStatus`를 아키텍처의 최종 형태로 확장
**결정:** `TorrentStatus`는 `info_hash, name, save_path, total_bytes,
downloaded_bytes, progress, download_rate, upload_rate, num_peers, num_seeds, state,
is_paused, is_finished, queue_position, error` 필드를 가집니다(libtorrent 2.0에는
`error` 상태 enum이 없으므로 error는 `status().errc`에서 읽음). UI의 에러 텍스트는 이
`error`에서 도출됩니다.
**이유:** UX 스펙의 에러/대기(queued) 상태와 컬럼 구성에 이 필드들이 필요하며, 엔진과 UI
사이에 단일한 데이터 모델을 유지하기 위함입니다.
**되돌릴 수 있는가:** 추가적인(additive) 변경이므로 가능. **(PM default, AFK)**

## D5 — info-hash 기반 키 관리로 v1/v2/hybrid를 모두 처리
**결정:** 핸들/resume 파일의 키는 단순 v1 해시가 아니라 libtorrent 2.0의 `info_hashes`
(v1/v2/hybrid를 인식)를 사용한 토렌트의 info-hash로 관리합니다.
**이유:** v2 및 hybrid 토렌트에 대한 정확성을 보장하고, 충돌이나 resume 누락을 방지하기
위함입니다.
**되돌릴 수 있는가:** 내부 구현 사항. **(PM default, AFK)**

## D6 — UI 테스트는 pytest-qt 사용(Playwright는 Qt 데스크톱 앱에 적용 불가)
**결정:** PySide6 GUI의 자동화된 UI 테스트는 **pytest-qt**(`QtBot`으로 클릭/키 입력을
시뮬레이션하고 위젯·시그널을 assert)를 사용하며, CI에서는 `QT_QPA_PLATFORM=offscreen`
(Linux에서는 xvfb 추가)으로 헤드리스 실행합니다. Playwright/Selenium은 웹 브라우저를
자동화하는 도구로 네이티브 Qt 위젯을 구동할 수 없으므로, 웹 UI가 추가되지 않는 한
적용되지 않습니다. **pywinauto**를 이용한 실제 창 수준의 Windows 엔드투엔드 자동화는
MVP 이후 선택 사항입니다. UI 테스트는 GUI와 함께(v0.2.0) 도입됩니다.
**이유:** 이 앱은 웹이 아니라 네이티브 Qt 데스크톱 GUI이며, pytest-qt가 인프로세스로
동작하고 CI 친화적인 표준 도구이기 때문입니다. (오너가 "Playwright 등"이라고 요청했으나,
자동화된 UI 테스트라는 의도는 적합한 도구로 충족했습니다.)
**되돌릴 수 있는가:** 예. **(PM default, AFK — 참고:** 굳이 Playwright를 원한다면 이는
웹 UI로의 전환을 의미하며, 이는 제가 대신 결정하지 않은 방향 전환입니다.)

## D7 — 문서 언어: 한국어를 기본으로, 영어는 다중언어 버전으로 병행
**결정:** 문서와 사용자 대면 메시지는 기본적으로 **한국어**(`X.md`)로 작성하고, 다중언어
지원으로 영어 버전(`X.en.md`)을 함께 제공합니다. 각 파일 최상단에서 서로의 대응 문서로
연결합니다. 새 문서는 한국어를 먼저 작성합니다. 코드 식별자는 영어를 유지하며, 커밋
메시지는 한국어를 우선합니다.
**이유:** 오너의 선호.
**되돌릴 수 있는가:** 예. **(PM default, AFK)**

## 오너에게 대기 중인 사항(복귀 시 재검토, 진행 차단 아님)
- 킬 스위치가 안전한 트래커+PEX 기본값(D1) 외에 "프록시를 통한 익명 DHT
  (UDP-associate)" 고급 모드를 제공해야 하는지 여부. 기본값은 그대로 출시하며, 토글
  기능은 MVP 이후 개선 사항입니다.
- 프록시 비밀번호(D2)를 영속화할지 여부 — "비밀번호 기억하기" UX 결정이 필요합니다.
