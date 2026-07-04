**한국어** | [English](DESIGN.en.md)

# 비주얼 디자인 & 퍼블리싱 스펙 — pytorrent-desktop v0.2.0

담당: design-publisher. 이 문서는 [`UX-SPEC.md`](UX-SPEC.md)의 레이아웃/상태/카피를
전제로, 실제 색상·타이포그래피·간격·컴포넌트 스타일을 정하고 그 근거를 남긴다.
발행물(publishing artifact)은 [`../src/pytorrent_desktop/ui/styles.qss`](../src/pytorrent_desktop/ui/styles.qss)
하나이며, 이 문서는 그 QSS의 "왜"를 설명하는 짝 문서다.

**범위:** 시각 디자인 + QSS 퍼블리싱만. `main_window.py`, `models.py`,
`dialogs.py`, `__main__.py`, `tests/`는 developer 담당이며 이 작업에서 건드리지
않았다. 아이콘은 UX-SPEC에 이미 명시된 유니코드 글리프(`▾ ❚❚ ▶ 🗑 ⚙ ● ⚠`)를
그대로 사용한다 — 외부 이미지/아이콘 폰트 자산 없음.

## 1. 테마 선택 — 라이트

라이트 하나로 일관되게 정했다(다크 미제공). 근거:
- SCOPE/UX-SPEC 어디에도 다크 모드 요건이 없고, 데스크톱 파일-전송 유틸리티(예:
  qBittorrent, Transmission)의 기본값도 라이트다 — 사용자 기대치에 맞음.
- 라이트 단일 테마가 대비(contrast)를 검증하기 쉽고, MVP 범위에서 테마 전환
  로직을 developer가 추가로 구현할 필요가 없다.
- 색상 자체는 브랜드 색이 아닌 중립 팔레트(slate/blue-gray 계열)로 골라, 나중에
  브랜드 색이 정해지면 accent 토큰 하나만 교체하면 되게 했다.

## 2. 디자인 토큰

### 2.1 색상

모든 값은 [WCAG 2.1](https://www.w3.org/TR/WCAG21/) AA 기준 본문 텍스트
대비(4.5:1) 이상을 흰 배경(`#FFFFFF`) 또는 표면색(`#F5F6F8`/`#F0F1F4`) 위에서
확인했다.

| 토큰 | 값 | 용도 |
|---|---|---|
| `bg-app` | `#F5F6F8` | 윈도우/다이얼로그 바탕 |
| `bg-surface` | `#FFFFFF` | 테이블, 카드, 다이얼로그 본문, 툴바 |
| `bg-surface-alt` | `#F0F1F4` | 테이블 헤더, 지브라 짝수행, 탭 비활성 배경 |
| `border` | `#D9DCE3` | 기본 구분선 (테이블 외곽, 툴바 하단, 인풋) |
| `border-strong` | `#C4C9D2` | 버튼/인풋 테두리 |
| `text-primary` | `#1E2430` | 본문/제목 텍스트 (대비 12.9:1 on 흰 배경) |
| `text-secondary` | `#5C6472` | 보조 텍스트, 헤더 라벨, 힌트 (대비 5.4:1) |
| `text-disabled` | `#ABB1BC` | 비활성 텍스트 |
| `accent` | `#2F6FEB` | 강조 — 진행중 상태, 기본 버튼, 포커스 링, 선택 |
| `accent-hover` | `#2560D6` | accent 호버 |
| `accent-pressed` | `#1E4FB8` | accent 눌림 |
| `accent-tint` | `#EAF1FE` | accent 옅은 배경 (선택 행, 정보 배너) |
| `success` | `#1E9E5C` | 완료/시딩중 진행바·상태 |
| `danger` | `#D6423F` | 오류 상태, 파괴적 버튼, 인풋 검증 실패 |
| `danger-tint` | `#FDEBEA` | 오류 배경 |
| `warning` | `#B8790A` | kill switch 경고, 프록시 연결 끊김 |
| `warning-tint` | `#FFF4E0` | 경고 배너 배경 |
| `neutral` | `#9AA1AC` | 대기중/일시정지/확인중 — 중립(회색조) 진행바 |

**시맨틱 매핑 근거 (UX-SPEC §1.3, §5.1의 "의미만" 지시를 구체화):**
진행중 = `accent`(파란색 계열, "지금 활동 중"이라는 느낌), 대기·일시정지·확인중 =
`neutral`(회색조 — "지금은 아무 일도 안 일어남"을 시각적으로 낮은 채도로 표현),
완료·시딩중 = `success`(초록 — 목표 달성), 오류 = `danger`(빨강 — 즉시 눈에 띄어야
함). 오류 상태는 진행바를 회색으로 유지하되 **테두리만** 빨갛게 둘러, "마지막
진행률은 그대로 보여주되 문제가 있다"는 UX-SPEC의 이중 의미(진행률 유지 + 오류
표시)를 하나의 위젯에서 동시에 표현한다.

### 2.2 타이포그래피

- 서체: `Segoe UI` (Windows 기본), 한글은 `Malgun Gothic`로 폴백. 별도 폰트
  임베딩 없음 — 독립 실행형 `.exe` 배포(SCOPE #10) 시 폰트 라이선스/용량 이슈를
  피하기 위해 OS 내장 서체만 사용.
- 크기 스케일 (pt 단위 — Windows point-size는 시스템 DPI 스케일링과 자연스럽게
  맞물림): 본문/기본 `9pt`, 테이블 헤더/힌트/상태바/뱃지 `8pt`, 다이얼로그 제목
  `11pt` bold, 섹션 라벨(설정 다이얼로그의 "일반"/"다운로드" 등) `8pt` bold.

### 2.3 간격 · 형태

| 토큰 | 값 |
|---|---|
| `space-xs` | 4px |
| `space-sm` | 8px |
| `space-md` | 12px |
| `space-lg` | 16px |
| `space-xl` | 24px |
| `radius-sm` | 4px (뱃지, 진행바 chunk) |
| `radius-md` | 6px (버튼, 인풋, 테이블, 다이얼로그 카드, 배너) |
| 테이블 행 높이 | 그리드라인 `#E4E6EB`, 지브라 스트라이핑 사용(`alternate-background-color`) — 열이 많고(7개) 행이 촘촘한 표에서 행 추적성을 높임 (UX-SPEC §6 "수십~수백 개" 케이스 대비) |
| 진행바 높이 | `16px` 고정 — 텍스트(`62%`)가 오버레이되므로 너무 얇으면 가독성이 떨어지고, 너무 두꺼우면 행 높이를 과도하게 키움 |

## 3. 컴포넌트별 결정

### 3.1 툴바 (`QToolBar`/`QToolButton`)

플랫(flat) 버튼 + 호버 시에만 배경/테두리 표시 — 다섯 개 버튼이 항상 테두리
박스로 그려지면 시각적으로 무거워 보이고, 텍스트+유니코드 아이콘 조합
(`❚❚ 일시정지` 등)이 이미 정보를 충분히 전달하므로 배경은 상호작용 피드백
용도로만 남겼다. 비활성 버튼(예: 선택 없을 때 "삭제")은 텍스트만 옅게
`text-disabled`로 낮추고 배경은 그대로 투명 — "존재하지만 지금은 안 됨"을
표현.

### 3.2 테이블 (`QTableView`/`QHeaderView`)

- 헤더는 `bg-surface-alt` 배경 + `text-secondary` 텍스트로 본문 행과 명확히
  분리하고, 정렬 화살표가 라벨과 겹치지 않도록 우측 패딩을 확보했다(UX-SPEC
  §1.3 "모든 컬럼 헤더 클릭 시 정렬/화살표 표시" MUST 요건). 화살표 자체는 Qt
  기본 렌더링을 그대로 사용 — 커스텀 이미지 자산을 추가하지 않기 위함.
- 선택 행은 `accent-tint` 계열(`#DCE9FD`)로, 포커스를 잃은 선택(`:!active`)은
  더 옅은 회조 톤으로 구분해 "선택은 되어 있지만 지금 포커스는 다른 곳"을 표현
  — 다이얼로그를 열었다가 닫았을 때 이전 선택이 사라진 것처럼 보이는 혼란을
  방지.
- 호버 하이라이트는 QSS만으로는 동작하지 않는다 — developer가 뷰에
  `setMouseTracking(True)`를 설정해야 `QTableView::item:hover`가 매 프레임
  갱신된다(마우스 버튼을 누르지 않고 움직여도). QSS 상단 주석에 명시.

### 3.3 진행률 셀 (`QProgressBar`)

퍼센트 텍스트를 바 위에 오버레이하는 요건(UX-SPEC §1.3 "%텍스트 오버레이")은
`QProgressBar.setFormat("%p%")` + `setAlignment(Qt::AlignCenter)`로 **코드에서**
설정해야 한다 — Qt 스타일시트는 `QProgressBar`의 텍스트 정렬 속성을 지원하지
않는다(공식 Qt Style Sheet 문서의 stylable-widget 대상 프로퍼티 목록에 없음).
QSS는 트랙/청크 색상·테두리·모서리만 담당한다.

7개 상태(다운로드중/일시정지/대기중/확인중/완료/시딩중/오류/메타데이터수신중)를
전부 별도 색으로 구분하면 팔레트가 과해지므로, UX-SPEC §5.1의 지시대로 **의미
그룹 4개**로 묶었다(§2.1 표 참조). 동적 프로퍼티 `rowState`를 developer가 각
행의 상태에 따라 세팅하는 방식을 QSS 상단 계약(contract) 주석에 명시했다.

### 3.4 버튼 (`QPushButton`)

기본 버튼(테두리만 있는 흰 배경)과 `variant="primary"`(칠해진 accent) 두
단계로 위계를 나눴다 — 다이얼로그마다 "취소"는 항상 기본형, 주 행동("추가"/
"저장")은 primary로 시각적 우선순위를 준다. 삭제 다이얼로그의 "데이터까지
삭제" 선택 시 버튼 라벨이 "영구 삭제"로 바뀌는 것(UX-SPEC §3 SHOULD)에 맞춰
`variant="danger"`를 별도로 두었다 — 파괴적 동작은 accent와 다른 색(빨강)으로
분명히 분리해야 실수 클릭을 줄일 수 있다.

### 3.5 다이얼로그 공통 (`QDialog`) · 탭 (`QTabWidget`)

추가 다이얼로그의 두 입력 방식(파일 경로 vs magnet URI)은 UX-SPEC §2.1이 이미
"탭으로 분리"를 지시했으므로, 탭 위계를 헤더보다 한 단계 낮은 톤(`bg-surface-alt`
비활성 탭, `bg-surface` 활성 탭 + bold)으로 스타일링해 현재 선택된 입력 방식이
분명하게 보이도록 했다.

### 3.6 인풋/체크박스/라디오 · 인라인 검증

- `QLineEdit`는 기본 상태에서 이미 은은한 테두리를 갖고, 포커스 시 accent
  테두리로 전환 — 접근성 기준(포커스 가시성)을 만족.
- 인라인 오류(잘못된 magnet, 쓰기 권한 없는 저장 경로 등, UX-SPEC §2.3/§4/§6)는
  `QLineEdit[state="error"]`로 테두리+배경을 붉게, 그 아래 문구는
  `QLabel[role="error"]`로 처리하도록 계약을 정의했다. "추가"/"저장" 버튼은
  이 상태와 별개로 developer가 유효성 로직에서 `setEnabled(False)`로 제어—
  QSS는 비활성 버튼의 톤 다운만 책임진다.

### 3.7 상태바 · 배너 · 토스트

프록시 3-상태(§1.4: 미설정/연결됨/연결실패)는 `QLabel[role="proxy-off|ok|warn"]`
세 변형으로 매핑했다 — 미설정은 중립 회색(경고가 아님을 명확히), 연결됨은
`success`, 연결실패는 `warning`(빨강이 아니라 amber를 쓴 이유: 이 경고는 즉시
데이터 유실을 뜻하지 않고 kill switch가 이미 트래픽을 막고 있는 "안전하게
차단된" 상태이기 때문 — `danger`는 토렌트 행의 실제 오류에만 남겨 두어 두
경고 레벨을 시각적으로 구분).

세션 복원 실패 배너("N개 항목을 복원하지 못했습니다", UX-SPEC §6)와 프록시
연결 실패 최초 감지 토스트는 아직 구현된 위젯이 없어 미리 스타일만
`QFrame[role="banner-warning"]` / `QFrame[role="toast"]`로 준비해 두었다 —
developer가 위젯을 만들 때 이 프로퍼티만 세팅하면 된다.

## 4. UX-SPEC 대조표 (요건 → 퍼블리싱 반영)

| UX-SPEC 항목 | QSS 반영 |
|---|---|
| §1.3 정렬 화살표 표시 (MUST) | `QHeaderView::down-arrow/up-arrow` + 헤더 우측 패딩 |
| §1.3 진행률 % 오버레이 | QSS는 색/모양만; 정렬·포맷은 코드 책임 (§3.3 참조) |
| §1.3 상태 색상 "의미만" 지정 | §2.1 4-그룹 시맨틱 매핑 + `rowState` 프로퍼티 계약 |
| §1.3 빈 목록 안내 문구 (SHOULD) | `QLabel[role="empty-state-title/body"]` |
| §1.4 프록시 3-상태 | `QLabel[role="proxy-ok/off/warn"]` |
| §2.1 탭 구조 | `QTabWidget::pane`/`QTabBar::tab` |
| §2.3 magnet 인라인 오류 | `QLineEdit[state="error"]` + `QLabel[role="error"]` |
| §3 삭제 다이얼로그 라디오 + 파괴적 버튼 | `QRadioButton` 스타일 + `QPushButton[variant="danger"]` |
| §4 설정 섹션 구분 | `QGroupBox`/`QGroupBox::title` |
| §5.1 상태 우선순위별 색 (오류>일시정지>…) | `rowState` 값 목록이 우선순위와 별개로 각 상태를 커버; 실제 "어떤 상태를 표시할지" 결정은 developer 로직 |
| §6 프록시 끊김/복원 실패 배너 | `QFrame[role="banner-warning"]` |
| §6 클립보드 toast | `QFrame[role="toast"]` |

## 5. Developer 통합 노트

1. QSS 로드: 앱 시작 시 `styles.qss`를 읽어 `QApplication.setStyleSheet()`에
   전달하면 전체 위젯 트리에 적용된다. 파일 하나만 로드하면 되고, 추가 설정
   불필요.
2. **동적 프로퍼티 갱신 패턴** — Qt는 `setProperty()` 호출만으로 화면을
   다시 그리지 않는다. 값이 바뀔 때마다 다음을 호출할 것:
   ```python
   widget.setProperty("rowState", "seeding")
   widget.style().unpolish(widget)
   widget.style().polish(widget)
   ```
   (테이블의 매 1초 폴링마다 `rowState`/`state`/`role`이 바뀔 수 있는 모든
   위젯에 적용 — 진행바, 상태 텍스트, 프록시 라벨 등.)
3. 테이블 행 호버를 켜려면 `table_view.setMouseTracking(True)`.
4. 진행바 퍼센트 오버레이는 `QProgressBar.setFormat("%p%")` +
   `setAlignment(Qt.AlignmentFlag.AlignCenter)` 를 위젯 생성 시 코드로 설정.
5. 상태 텍스트 컬럼(§1.3 "상태")은 색상 배지가 필요하면 셀 위젯으로
   `QLabel`을 올리고 `role`(또는 별도 프로퍼티, 예: `statusKind`)을 세팅해
   §2.1 시맨틱 4색 중 하나를 적용 — 필요 시 QSS에 `QLabel[statusKind="..."]`
   규칙을 developer가 이 파일 하단에 추가해도 무방(색은 §2.1 토큰 재사용
   권장).
6. 새 위젯을 추가할 때 이 문서의 §2 토큰(hex 값)을 그대로 재사용할 것 — 새
   색을 즉흥적으로 추가하지 말 것. 브랜드 팔레트가 정해지면 `accent*` 4개
   토큰만 교체하면 전체 앱 톤이 바뀌도록 설계했다.

## 6. 산출물

- [`src/pytorrent_desktop/ui/styles.qss`](../src/pytorrent_desktop/ui/styles.qss) — 전체 스타일시트 (이 문서 §2의 토큰을 직접 하드코딩; QSS는 변수 문법을 지원하지 않아 값 반복, 토큰명은 주석으로 병기)
- 이 문서 (`docs/DESIGN.md`, `docs/DESIGN.en.md`)
