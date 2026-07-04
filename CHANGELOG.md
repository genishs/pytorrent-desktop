**한국어** | [English](CHANGELOG.en.md)

# 변경 이력 (Changelog)

pytorrent-desktop의 모든 주요 변경 사항을 여기에 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 따르며, 버전 규칙은
[로드맵](docs/ROADMAP.md)을 따릅니다 (`0.MINOR.PATCH`, **핵심 기능은 모두 0.5.0에서 동작**).

## [Unreleased]

다음 마일스톤: **0.2.0 — GUI**. [로드맵](docs/ROADMAP.md) 참고.

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
