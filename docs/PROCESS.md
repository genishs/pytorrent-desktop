**한국어** | [English](PROCESS.en.md)

# 개발 프로세스

`0.x` 마일스톤을 어떻게 브랜치·PR·CI·태그·릴리스로 흘려보내는지 정의합니다.
버전/기능 대응은 [`ROADMAP.md`](ROADMAP.md), 변경 이력은
[`../CHANGELOG.md`](../CHANGELOG.md), 문서 언어 정책은 [`DECISIONS.md`](DECISIONS.md)의
D7을 따릅니다.

## 브랜치 전략

- **`main`** — 항상 배포 가능한 상태를 유지합니다. 직접 push는 브랜치 보호 규칙으로
  막혀 있으며, **PR을 통해서만** 병합됩니다.
- **`release/vX.Y.0`** — 마일스톤 작업 브랜치. [`ROADMAP.md`](ROADMAP.md)의
  0.1~0.5 표에서 다음 마일스톤을 확인한 뒤 이 이름으로 브랜치를 만듭니다
  (예: `release/v0.1.0`).
- **`fix/*`, `docs/*`** — 마일스톤 범위가 아닌 짧은 수정(버그 패치, 문서만 변경 등)도
  같은 흐름(PR → CI 통과 → 병합)을 따르되, 별도 태그/릴리스 없이 다음 마일스톤
  릴리스에 포함될 수 있습니다.

## 마일스톤 → PR → 병합 흐름

1. [`ROADMAP.md`](ROADMAP.md)에서 다음 마일스톤(`vX.Y.0`)과 범위를 확인합니다.
2. `main`에서 `release/vX.Y.0` 브랜치를 만들고 해당 범위를 구현합니다.
3. 작업 중(또는 PR 직전) [`../CHANGELOG.md`](../CHANGELOG.md)와
   [`../CHANGELOG.en.md`](../CHANGELOG.en.md)에 `## [X.Y.Z] - YYYY-MM-DD` 섹션을
   추가합니다. `release.yml`이 릴리스 노트를 만들 때 이 섹션을 그대로 읽어갑니다.
4. `main`으로 PR을 엽니다. `.github/PULL_REQUEST_TEMPLATE.md` 체크리스트
   (수용 기준 링크, CHANGELOG 갱신, 테스트 통과, 문서 한/영 동기)를 채웁니다.
5. **CI(`.github/workflows/ci.yml`, ubuntu-latest + windows-latest, py3.12,
   ruff + pytest + libtorrent 스모크)가 통과해야 병합할 수 있습니다.** 이는
   브랜치 보호 규칙의 필수 status check로 강제됩니다 — CI 통과가 곧 머지 게이트입니다.
6. 리뷰 후 병합합니다(솔로 운영 구간에서는 self-review로 체크리스트를 확인하는 것으로
   대체 가능). 병합 전략은 **Squash and merge**를 권장합니다 — 마일스톤 브랜치의
   여러 커밋을 `main`에는 깔끔한 커밋 하나로 남깁니다.
7. 병합 후 `main`에서 태그 `vX.Y.0`을 만들어 push합니다.
8. 태그 push가 `.github/workflows/release.yml`을 트리거하여, CHANGELOG의 해당
   섹션으로 GitHub Release를 자동 생성합니다.

## 버전 태깅 규칙

- 태그 형식은 `vX.Y.Z`(`v` 접두어 포함)이며, `CHANGELOG.md`의 섹션 헤더는
  `v` 없이 `X.Y.Z`로 씁니다(예: 태그 `v0.1.0` ↔ 헤더 `## [0.1.0]`). `release.yml`이
  태그에서 `v`를 떼어내고 매칭하므로 두 표기를 맞춰야 합니다.
- 1.0 이전 버전 규칙은 [`ROADMAP.md`](ROADMAP.md#버전-관리-정책)을 따릅니다:
  MINOR = 로드맵 마일스톤(0.1 → 0.5), PATCH = 마일스톤 내 수정/보완.
- 태그는 **병합된 `main` 커밋에만** 생성합니다. `release/*` 브랜치에 직접
  태깅하지 않습니다.

## 릴리스 절차

1. 태그를 만들기 전에 `main`의 `CHANGELOG.md`와 `CHANGELOG.en.md`에 해당 버전
   섹션이 있는지 확인합니다(없으면 `release.yml`이 섹션을 찾지 못했다는 안내
   문구로 릴리스 노트를 대신 채웁니다).
2. ```
   git checkout main && git pull
   git tag vX.Y.0
   git push origin vX.Y.0
   ```
3. `.github/workflows/release.yml`이 태그 push로 실행되어, `CHANGELOG.md`에서
   해당 섹션을 추출하고 `softprops/action-gh-release`로 GitHub Release를
   생성합니다. `0.x` 버전은 프리릴리스로 표시되고, `1.0.0`부터 정식 릴리스로
   전환됩니다.
4. **아티팩트(Windows `.exe`) 업로드는 아직 연결되어 있지 않습니다.** 지금은
   릴리스 노트만 생성됩니다. `v0.5.0`에서 PyInstaller 패키징이 구현되면
   `release.yml` 하단에 뼈대로 남겨둔 빌드/업로드 잡의 주석을 해제해 연결합니다
   ([`ROADMAP.md`](ROADMAP.md)의 0.5.0 항목 참고).

## 브랜치 보호 (`main`)

다음 규칙이 GitHub 저장소 설정(브랜치 보호 규칙)으로 적용되어 있습니다:

- PR을 통해서만 병합 가능(직접 push 금지).
- 필수 status check: CI의 두 잡 `test (ubuntu-latest, py3.12)`,
  `test (windows-latest, py3.12)` 모두 통과해야 병합 가능.
- 관리자(admin)도 예외 없이 규칙을 따름(`enforce_admins`).

적용에 사용한 정확한 명령과 결과는 저장소 관리자(형상관리 담당)의 설정 기록을
참고하세요. 규칙을 바꾸거나 다시 적용해야 한다면:

```
gh api --method PUT repos/genishs/pytorrent-desktop/branches/main/protection \
  --input protection.json
```

(`protection.json`은 `required_status_checks.contexts`에 위 두 체크 이름을,
`required_pull_request_reviews`와 `enforce_admins: true`를 담은 JSON입니다.)
