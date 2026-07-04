<!--
이 PR이 0.x 마일스톤(예: v0.1.0) 브랜치(release/vX.Y.0)에서 main으로 병합하는
PR이라면 아래 체크리스트를 사용하세요. 마일스톤 PR이 아닌 작은 수정(typo, CI
설정 등)이라면 관련 없는 항목은 지우거나 "해당 없음"으로 표시해도 됩니다.
자세한 절차는 docs/PROCESS.md를 참고하세요.
-->

## 마일스톤

- 대상 버전: `vX.Y.0` (docs/ROADMAP.md의 마일스톤 표 참고)
- 브랜치: `release/vX.Y.0`

## 요약

<!-- 이 PR이 무엇을 구현/변경하는지 2~3문장으로 -->

## 수용 기준

<!--
docs/ROADMAP.md와 docs/SCOPE.md의 해당 마일스톤 항목을 링크하고, 각 기준이
이번 PR로 충족되었는지 체크하세요. 예:
- [ ] docs/SCOPE.md MVP 완료 기준 #1 (.torrent 열기 → 저장 경로 다이얼로그 → 다운로드 시작)
-->
- [ ] docs/ROADMAP.md 마일스톤 표의 해당 항목을 링크했다
- [ ] docs/SCOPE.md 관련 수용 기준을 링크했다
- [ ] 위 기준을 실제로(가능하면 데모/스크린샷으로) 검증했다

## 체크리스트

- [ ] `CHANGELOG.md`에 이번 버전 섹션(`## [X.Y.Z] - YYYY-MM-DD`)을 추가/갱신했다
- [ ] `CHANGELOG.en.md`도 동일한 내용으로 갱신했다 (docs/DECISIONS.md D7: 한글 기본 + 영어 병행)
- [ ] 이 PR에서 바뀐 문서가 있다면 한글본과 `.en.md` 영어본을 함께 갱신했다
- [ ] 로컬에서 `ruff check .` 통과
- [ ] 로컬에서 `pytest` 통과
- [ ] CI(`.github/workflows/ci.yml`, ubuntu + windows)가 그린이다 — **머지 게이트**
- [ ] 브랜치를 `vX.Y.0`으로 태그하고 릴리스를 만들 준비가 되었다 (병합 후, docs/PROCESS.md 절차대로)

## 참고 사항

<!-- 알려진 이슈, 다음 PR로 미룬 항목, 리뷰어가 특히 봐줬으면 하는 부분 등 -->
