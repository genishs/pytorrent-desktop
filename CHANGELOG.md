**한국어** | [English](CHANGELOG.en.md)

# 변경 이력 (Changelog)

pytorrent-desktop의 모든 주요 변경 사항을 여기에 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 따르며, 버전 규칙은
[로드맵](docs/ROADMAP.md)을 따릅니다 (`0.MINOR.PATCH`, **핵심 기능은 모두 0.5.0에서 동작**).

## [Unreleased]

post-0.5: magnet 프로토콜 핸들러, Inno Setup 설치본, I2P. [로드맵](docs/ROADMAP.md) 참고.

## [0.5.1a] - 2026-07-05

**btdig형 검색 (실험적/알파, develop 전용).** 기본 비활성 + 명시적 법적 동의 게이트 뒤에서만 작동. *main 미배포 — develop에서 실험/검증 중.*

### Added (추가)
- **플러그인형 검색 구조** — `core/search/base.py`: `SearchProvider`/`SearchResult` + 레지스트리(Qt 무의존). `core/search/btdig.py`: btdig HTTP 질의 + `BeautifulSoup`(html.parser) 파싱 → magnet. 오류는 `SearchError`로 감싸 graceful.
- **검색 UI** — `SearchDialog`(질의·결과 테이블·법적 고지 배너·선택 결과 다운로드 추가), 메인 윈도우 "검색" 버튼(활성화 시).
- **법적 동의 게이트(D8)** — 검색 사용 전, (1)법적 위험 (2)다운로드 대상 S/W 라이선스 위반 가능성 (3)본인 전적 책임을 고지하고 체크+동의해야만 작동. 미동의 시 차단. 동의는 `SearchSettings.consent_accepted`로 config에 저장.
- **설정** — `SearchSettings`(enabled=False 기본, btdig_base_url, consent_accepted=False), 설정 다이얼로그 검색 탭. config.json 라운드트립.
- 의존성 `requests`·`beautifulsoup4` 추가. 테스트: 파서(HTML 픽스처), 레지스트리, 동의 게이트, 다이얼로그(pytest-qt, mock 제공자 — **라이브 네트워크 없음**). 전체 181 통과.

### Notes (참고)
- **DHT 크롤러/인덱서는 만들지 않음.** btdig는 사용자가 base URL로 설정하는 첫 제공자일 뿐.
- 실험 기능이라 git-flow상 develop에만 존재하며 main 승격은 별도 검토.

## [0.5.0] - 2026-07-05

**core 완성 & Windows `.exe` 패키징.** 6개 핵심 기능 중 5개(검색 제외)가 기능 완성 — .torrent/magnet 다운로드, 순차 큐, 완료 후 동작, 프라이버시. 최종 사용자는 Python 없이 `.exe`로 실행.

### Added (추가)
- **PyInstaller 패키징** — `pytorrent-desktop.spec`(one-folder, windowed): libtorrent 네이티브 확장·PySide6 Qt 플러그인·`ui/styles.qss` 번들. `docs/BUILD.md`(한/영) 빌드 문서.
- **릴리스 자산 자동 빌드** — `.github/workflows/release.yml`에 `build-windows-exe` 잡: `v*` 태그 시 windows-latest에서 `.exe` 빌드→헤드리스 스모크→zip을 GitHub Release 자산으로 업로드.
- **PR 빌드 가드** — `.github/workflows/build.yml`: PR/수동 트리거로 `.exe`를 빌드해 workflow 아티팩트로 업로드(빌드 회귀 감시).

### Changed (변경)
- `pyproject`/`__init__` 버전 `0.4.0` → `0.5.0`.

### Notes (참고)
- 로컬 빌드 검증: `dist/pytorrent-desktop/pytorrent-desktop.exe` 생성 + 헤드리스 스모크(이벤트 루프 진입) 통과.
- ⚠️ **수동 검증 대기(이 검증 전까지 "core complete"는 잠정)**: 실제 합법 토렌트 E2E 다운로드, 킬스위치 실 프록시+패킷캡처 누수 차단 — 둘 다 헤드리스로 불가.

## [0.4.0] - 2026-07-04

**프라이버시 & 자동화.** IP 숨기기(프록시)와 완료 후 동작.

### Added (추가)
- **프라이버시**(엔진) — `configure_privacy(ProxyConfig | None)`: SOCKS5 + `anonymous_mode` + `proxy_hostnames` + 피어/트래커 프록시, 킬스위치 ON이면 DHT/LSD/UPnP/NAT-PMP 비활성으로 직접 연결 차단(D1). host/port 검증→`ProxyConfigError`. `privacy_status()`, `set_listen_port()`. 상태바에 프록시 상태 표시.
- **설정 저장**(`core/config.py`) — `ConfigStore`가 `config.json`(%APPDATA%)에 기본 저장경로·프록시(host/port/user/killswitch)·완료 후 동작·포트를 원자적 저장/로드(손상 시 기본값 폴백). **프록시 비밀번호는 스키마에 없음 — 메모리에만**(D2).
- **설정 다이얼로그**(`ui/dialogs.py`) — 일반/프라이버시/완료 후 동작 탭.
- **완료 후 동작**(D3) — 옵트인. 전 토렌트 완료 시 **취소 가능한 30초 카운트다운** 후 앱 종료 또는 시스템 종료. 시스템 종료는 `core/system_actions.py`의 단일 seam으로 격리 — **카운트다운 만료 없이는 도달 불가**, Windows에서만 실행, 실행 전 resume flush.
- **테스트** — 프록시 settings 적용 검증, config 라운드트립(비밀번호 미저장), 카운트다운/취소, 종료 seam이 mock으로만 호출됨. 전체 124개 통과.

### Changed (변경)
- `pyproject`/`__init__` 버전 `0.3.0` → `0.4.0`.

### Notes (참고)
- **킬스위치 실제 누수 차단 검증은 실제 프록시 + 패킷 캡처가 필요해 헤드리스 테스트로는 불가** — 설정 조합 적용은 단위 테스트했으나 실환경 검증은 수동 필요(코드/독스트링에 명시).
- I2P 익명 모드(post-0.5), `.exe` 패키징(v0.5)은 범위 밖.

## [0.3.0] - 2026-07-04

**영속성 & 순차 큐.** 재시작 후 세션 복원과 한 번에 하나씩 다운로드.

### Added (추가)
- **세션 복원** — `core/resume_store.py`의 `ResumeStore`: `%APPDATA%\pytorrent-desktop\resume\<key>.fastresume` 저장/로드, **원자적 쓰기**(`.tmp`+`os.replace`), 손상 파일은 `resume/bad/`로 격리. 시작 시 로드→세션 복원.
- **`core/config.py`** — `AppPaths`(Windows `%APPDATA%`, 그 외 XDG 폴백). `EngineConfig.data_dir` 기본값을 실제 앱 데이터 경로로.
- **종료 시 resume flush 시퀀스**(ARCHITECTURE §4.3) — `session.pause()`→핸들별 `save_resume_data`→알림 드레인(성공·**실패 알림 모두** outstanding 감소로 hang 방지)→timeout 시 log. 추가 시/주기(60s, `need_save_resume_data`)/완료(`torrent_finished_alert`) 저장은 동일 경로 공유. `remove()`는 `.fastresume`도 삭제(재기동 시 부활 방지).
- **순차 단일 다운로드 큐** — `set_sequential_queue`(active_downloads=1 + auto_managed), `move_in_queue(up/down/top/bottom)`. UI: 툴바 "순차 다운로드" 토글 + 컨텍스트 메뉴 "위로/아래로 이동".
- **테스트** — ResumeStore 라운드트립·원자성·격리, 세션 복원, 종료 드레인의 실패-알림 감소 회귀, 큐 순서. 전체 76개 통과.

### Changed (변경)
- `pyproject`/`__init__` 버전 `0.2.0` → `0.3.0`.

### Notes (참고)
- SOCKS5 프록시/킬스위치·완료 후 종료(v0.4), `.exe` 패키징(v0.5)은 범위 밖.

## [0.2.0] - 2026-07-04

**GUI.** PySide6 데스크톱 UI를 v0.1.0 엔진에 연결.

### Added (추가)
- **메인 윈도우**(`ui/main_window.py`) — 툴바(추가▾[.torrent/magnet]·일시정지·재개·삭제), `QTableView` + `TorrentTableModel`(이름/크기/진행률/↓속도/↑속도/피어/상태), **1초 `QTimer`로 `engine.snapshot()` 폴링**(변경 없으면 in-place 갱신해 선택 유지), 하단 상태바(전체 ↓↑ 속도·활성/전체), 우클릭 컨텍스트 메뉴. 엔진 호출은 `EngineError` 처리 → QMessageBox.
- **다이얼로그**(`ui/dialogs.py`) — `AddTorrentDialog`(.torrent/magnet 탭 + 저장 경로 + "일시정지로 추가", 라이브 검증), `RemoveDialog`(목록만/데이터삭제, 기본 목록만).
- **진입점**(`__main__.py`) — `QApplication` + `ui/styles.qss` 로드(없으면 graceful) + 종료 시 `engine.shutdown()`.
- **스타일**(`ui/styles.qss`) — 라이트 테마 QSS 전 위젯 커버. **`docs/DESIGN.md`**(한/영) 디자인 토큰·통합 노트.
- **pytest-qt UI 테스트** — `tests/conftest.py`(offscreen) + 모델/다이얼로그/메인윈도우 테스트. 전체 스위트 53개 통과(엔진 14 + GUI 39).

### Changed (변경)
- `pyproject`/`__init__` 버전 `0.1.0` → `0.2.0`.

### Notes (참고)
- "일시정지로 추가"는 add 후 `pause()` 2단계로 구현(엔진 add 시그니처 유지).
- 설정 다이얼로그·SOCKS5 프록시(v0.4), 순차 큐 UI(v0.3), 완료 후 종료(v0.4)는 이 마일스톤 범위 밖.

## [0.1.0] - 2026-07-04

**엔진 기반(Engine foundation).** libtorrent 위의 GUI 무의존 엔진과, v0.1.0을 향한 프로젝트 기반·프로세스 구축.

### Added (추가)
- **`core.engine.TorrentEngine` 실구현** — `EngineConfig`/`ProxyConfig` 설정 객체, D4 확장 `TorrentStatus`(info_hash·name·save_path·크기·진행률·속도·피어/시드·상태·큐위치·error; error는 `status().errc`에서 도출), `.torrent`/magnet 추가 시 사전 검증 + 중복 탐지(D5 v1/v2/hybrid `info_hashes().get_best()` 키잉), 일시정지/재개/제거, `snapshot()`, idempotent `shutdown()`.
- **타입 있는 에러 계층** `core/errors.py` — `EngineError` 기반 `InvalidMagnetError`/`TorrentFileError`/`DuplicateTorrentError`/`SavePathError`/`UnknownTorrentError` 등.
- **헤드리스 엔진 테스트 14개**(`tests/`) — 네트워크 없이 생성/종료·타입 에러·중복 추가·확장 상태 형태 검증. (로컬 ruff clean, 14 passed)
- **설계 문서**: `docs/ARCHITECTURE.md`(엔진 API 계약·동시성·종료 시퀀스·프라이버시/킬스위치·순차 큐·검색 플러그인 시임·패키징, libtorrent 2.0.13 검증), `docs/UX-SPEC.md`(화면·다이얼로그·상태 전이·엣지케이스·11개 수용 시나리오·와이어프레임), `docs/DECISIONS.md`(결정 로그).
- **GitHub Actions CI**(`.github/workflows/ci.yml`) — Ubuntu+Windows / Python 3.12에서 ruff + pytest + libtorrent/엔진 스모크.
- **릴리스 프로세스** — `.github/workflows/release.yml`(태그 `v*` → CHANGELOG 노트로 GitHub Release, 0.x는 prerelease), PR 템플릿, `docs/PROCESS.md`(브랜치 전략·PR→CI→merge→태그→릴리스 흐름), main 브랜치 보호(PR 필수 + CI 2개 체크 통과 필수).
- **문서 다국어화(D7)** — 한글 기본(`X.md`) + 영어(`X.en.md`) 병행, 상단 언어 전환 링크.
- `pytest-qt` 개발 의존성 추가(UI 테스트는 v0.2.0 GUI와 함께 도입).

### Changed (변경)
- `pyproject` 버전 `0.1.0.dev0` → `0.1.0`.
- 문서 기본 언어를 한국어로 전환(영어는 `.en.md` 병행).

### Notes (참고)
- resume data 영속화·순차 큐(v0.3), SOCKS5 프록시/킬스위치(v0.4), GUI(v0.2)는 의도적으로 스텁으로 남김 — 호출부에 후속 마일스톤 훅을 문서화.
- Python 3.14용 `libtorrent` 휠 부재 — 개발은 3.11–3.13 고정(uv가 3.12 자동 설치).

## [0.1.0.dev0] - 2026-07-04

프로젝트 부트스트랩.

### Added (추가)
- 프로젝트 스캐폴드: `src/` 레이아웃, `pyproject.toml`(hatchling, Python 3.11–3.13 고정, `libtorrent==2.0.13`, PySide6), MIT `LICENSE`.
- `core.engine.TorrentEngine` 초기 스캐폴드(파사드 + TODO 스텁).
- `README.md`(합법적 사용 안내), `docs/SCOPE.md`, `docs/ROADMAP.md`, 이 변경 이력 문서.
- 검증됨: uv로 관리되는 Python 3.12 환경(Windows)에서 `libtorrent 2.0.13` 기반 엔진 부팅.

### Notes (참고)
- Python 3.14용 `libtorrent` 휠은 아직 없음 — 개발 환경은 3.11–3.13으로 고정.
