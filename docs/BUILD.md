**한국어** | [English](BUILD.en.md)

# 빌드 — Windows `.exe` 패키징

pytorrent-desktop을 PyInstaller로 Windows 독립 실행형 배포물로 패키징하는 방법을
정의합니다. 패키징 아키텍처(one-folder 결정 근거, 번들 대상, 설치 프로그램 연결
지점)는 [`ARCHITECTURE.md`](ARCHITECTURE.md) §10을 참고하세요.

## 산출물 형태: one-folder

`pytorrent-desktop.spec`은 **one-folder**(`COLLECT`) 빌드를 만듭니다 — 단일
`.exe`(`--onefile`)가 아닙니다. 이유([`ARCHITECTURE.md`](ARCHITECTURE.md) §10.1):

- 실행할 때마다 `%TEMP%`에 자체 압축 해제하는 one-file보다 시작이 빠릅니다.
- 네이티브 `libtorrent` 확장(`.pyd`)과 PySide6/Qt 플랫폼 플러그인
  (`platforms/qwindows.dll`)이 `dist/pytorrent-desktop/` 아래 평범한 파일로
  존재해서, 클린 머신에서 무엇이 빠졌는지 진단하기 가장 쉽습니다.
- 자체 압축 해제 실행 파일보다 백신 오탐이 적습니다.
- 나중에 Inno Setup 설치 프로그램(§10.3)이 그대로 소비할 수 있는 안정적인
  기반입니다.

산출물: `dist/pytorrent-desktop/pytorrent-desktop.exe` + 같은 폴더의 지원 파일들
(`_internal/` 아래 Python 런타임, libtorrent, PySide6/Qt, `styles.qss`).
배포 시에는 이 `dist/pytorrent-desktop/` 폴더 전체를 zip으로 묶어서 전달합니다.

## 로컬 빌드

```powershell
# 1. 빌드용 의존성 설치 (pyinstaller는 pyproject.toml의 [project.optional-dependencies].build)
uv pip install --python .venv/Scripts/python.exe -e ".[build]"

# 2. 커밋된 spec으로 빌드
.venv/Scripts/pyinstaller --noconfirm pytorrent-desktop.spec
```

(`uv` 없이 `pip install -e ".[build]"` + `pyinstaller pytorrent-desktop.spec`도
동일하게 동작합니다.)

결과:
```
dist/pytorrent-desktop/
  pytorrent-desktop.exe
  _internal/
    libtorrent/...
    PySide6/plugins/platforms/qwindows.dll  (필수 Qt 플랫폼 플러그인)
    pytorrent_desktop/ui/styles.qss
    ... (Python 런타임 + 기타 의존성)
```

`build/`와 `dist/`는 매번 새로 생성되는 산출물이므로 커밋되지 않습니다
(`.gitignore`). 반대로 손수 작성한 `pytorrent-desktop.spec`은 CI와 로컬 빌드가
같은 정의를 공유하도록 예외 처리되어 **커밋 대상**입니다.

### 실행 확인 (스모크 테스트)

GUI 앱이라 완전한 수동 확인(창이 뜨고 조작 가능한지)은 사람이 해야 하지만,
"프로세스가 즉시 죽지 않고 이벤트 루프에 들어갔는지"는 헤드리스로 확인할 수
있습니다:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
Start-Process dist\pytorrent-desktop\pytorrent-desktop.exe
# 몇 초 후에도 살아있으면 libtorrent 로드 + Qt 초기화 + styles.qss 로드가
# 성공했다는 뜻입니다.
```

CI의 두 빌드 워크플로 모두 이 스모크 테스트를 자동으로 수행합니다.

## CI/CD에서의 빌드

### PR 빌드 가드 — `.github/workflows/build.yml`

`main`으로의 PR과 수동 실행(`workflow_dispatch`)에서 windows-latest 러너가
`pytorrent-desktop.spec`으로 빌드하고 헤드리스 스모크 테스트를 통과시킨 뒤,
결과물을 **workflow artifact**(`pytorrent-desktop-windows`, 14일 보관)로
업로드합니다. GitHub Release는 만들지 않습니다 — 목적은 태그를 찍기 전에
패키징 회귀(새 의존성이 spec에 반영되지 않아 `.exe`가 깨지는 등)를 잡아내는
것입니다.

### 릴리스 빌드 — `.github/workflows/release.yml`

`v*` 태그 push 시:
1. `release` 잡이 `CHANGELOG.md`에서 릴리스 노트를 뽑아 GitHub Release를 만듭니다
   (기존 동작, 변경 없음).
2. `build-windows-exe` 잡(`release`에 의존)이 windows-latest에서
   `pytorrent-desktop.spec`으로 빌드 → 스모크 테스트 → `dist/pytorrent-desktop/`을
   `pytorrent-desktop-<tag>-windows.zip`으로 압축 → 해당 릴리스의 자산으로
   업로드합니다.

이 두 워크플로는 `pyinstaller>=6.6`(pyproject.toml의 `build` extra)과 Python
3.12를 사용합니다 — [`ARCHITECTURE.md`](ARCHITECTURE.md) §1이 명시한 대로
libtorrent 휠 가용성 때문에 3.12/3.13을 타겟해야 합니다.

## 참고 — 아직 하지 않는 것

- 코드 서명: 없음(자체 서명 인증서도 없음). 배포 시 SmartScreen 경고가 뜰 수
  있습니다 — post-MVP 과제.
- Inno Setup 설치 프로그램, magnet 프로토콜 핸들러 등록: 아직 없음.
  [`ARCHITECTURE.md`](ARCHITECTURE.md) §10.3이 연결 지점을 문서화해 둔 상태입니다.
- one-file "포터블" 빌드: 현재 산출물은 one-folder뿐입니다. §10.1은 이를 편의용
  옵션으로만 언급하며 지금 자동화 범위에는 포함되지 않습니다.
