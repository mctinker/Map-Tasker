<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - 다운로드](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![다운로드](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![파이썬](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - 라이선스](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![코드 스타일: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![pytest](https://img.shields.io/badge/tested%20with-pytest-blue?logo=pytest)](https://docs.pytest.org/)
[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

<p align="center">
  <b>Read this in:</b>
  <a href="../README.md">English</a> •
  <a href="README.zh-CN.md">简体中文</a> •
  <a href="README.es.md">Español</a> •
  <a href="README.hi.md">हिन्दी</a> •
  <a href="README.fr.md">Français</a> •
  <a href="README.ar.md">العربية</a> •
  <a href="README.de.md">Deutsch</a> •
  <a href="README.da.md">Dansk</a> •
  <a href="README.fi.md">Suomi</a> •
  <a href="README.ru.md">Русский</a> •
  <a href="README.ko.md">한국어</a> •
  <a href="README.ja.md">日本語</a>
</p>

---

# MapTasker

> 이 번역은 자동으로 생성되었습니다. 내용에 차이가 있는 경우 [원본 영어 README](../README.md)가 우선합니다.

## Tasker의 백업 또는 내보낸 XML 파일을 기반으로, 데스크톱 브라우저(Mac/Windows 11/Linux)에서 Tasker의 Project, Profile, Task, Scene을 표시/편집/분석하세요

구성 맵(Configuration Map)...
![MapTasker 구성 맵: 하나의 project와 그 profiles, tasks를 색상으로 구분된 들여쓰기 개요로 표시하며, 각 task의 번호가 매겨진 action과 그 설정이 아래에 나열됨](../documentation_images/intro.png)

다이어그램 맵(Diagram Map)...
![MapTasker 다이어그램 맵: project와 그 profiles가 상자로, 그 아래에 tasks가 그려져 있고, 어떤 task가 어떤 task를 호출하는지 선으로 표시되며, 하나의 호출 경로가 강조됨](../documentation_images/Introd.png)

[[더 많은 예시]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

이것은 [Tasker](https://tasker.joaoapps.com/)를 보완하는 애플리케이션으로, 웹 브라우저에서 실행되도록 설계되었습니다 (참고 [노트 1](#1)).

제 Tasker Project/Profile/Task/Scene이 점점 관리하기 어려워졌고, 휴대폰 화면이 너무 작아 탐색하기 힘들다는 것을 알게 되었습니다. 그래서 로컬 데스크톱 드라이브에 저장한 Tasker 백업 XML 파일을 기반으로, 웹 브라우저에서 전체 구성의 완전한 맵을 제공하는 Python 프로그램을 작성했습니다.

시간이 지나면서 Tasker 객체를 편집하고 Tasker 구성을 심층 분석할 수 있는 기능을 포함해 많은 추가 옵션을 제공함으로써 이 맵을 개선해 왔습니다.

Tasker 백업 또는 기타 Tasker 내보내기 XML은 수동으로 PC/Mac/Linux/클라우드 드라이브에 업로드할 수도 있고, 이 프로그램이 Android 기기에서 직접 가져올 수도 있습니다 (참고 [노트 2](#2)).

## 기능

- 전체 요약부터 매우 세부적인 수준까지, 원하는 출력 상세 수준을 선택하세요.
- 단일 Project, Profile 또는 Task만 표시하세요.
- Profile 및 Task 조건(States, Events 등)을 포함/제외하세요.
- 모든 것을 그대로 스트리밍하거나, 모든 필드를 정렬하여 출력을 "깔끔하게" 만드세요.
- 외관 변경: '라이트' 또는 '다크' 모드를 선택하세요.
- 원하는 고정폭 글꼴로 출력하고, Project, Profile, Task 이름을 기울임, 굵게, 강조 및/또는 밑줄로 강조하세요.
- 기분에 따라 출력의 다양한 측면과 관련된 색상을 수정하세요.
- TaskerNet 설명 및/또는 Tasker 환경설정(preferences)을 포함하세요.
- 복잡한 구성의 경우, 선택적으로 Project, Profile, Task, Scene에 대한 하이퍼링크 목록을 포함할 수 있습니다.
- 전체 Tasker 구성의 다이어그램과 Task Flow를 표시하세요.
- 명령줄 또는 GUI 인터페이스.
- 내보낸 XML을 사용하거나, 구성 매핑을 위해 Android 기기에서 직접 XML을 가져오세요.
- Project, Profile, Task, Scene을 Android 기기의 Tasker로 다시 전송하세요.
- 런타임 설정을 저장하고 복원하세요.
- 너무 많은 'action'을 가진 Task를 식별하여, 여러 Task로 분할해야 할지 판단하세요.
- 서버 기반 ChatGPT/Claude/Gemini 또는 로컬 기반 Llama(Ollama 경유) 지원 모델을 사용하여 특정 Project, Profile, Task 또는 Scene을 분석하는 AI 분석 옵션.
- GUI 내에서 직접 결과를 표시하세요: (구성) Map View, Tree View, Diagram View.
- 자동 업데이트 감지 및 새 버전의 선택적 설치.
- 향상된 검색 및 구조화된 'Find/Replace'.
- Project, Profile, Task, Scene을 추가 및 편집하세요 (참고 [노트 6](#6)).
- 특정 날짜 이후의 변경 사항 목록을 표시하세요.
- Project, Profile, Task 또는 Scene을 해당 TaskerNet 공유에 연결하고, 작성자가 새 버전을 게시할 때 알림을 받으며, 그 변경 사항을 하나씩 적용하세요.
- Tasker XML의 상태와 전체 구성에 있는 수많은 변수를 분석하세요.
- XML 파일을 로드된 XML과 비교하세요.

## 프로그램 종속성

### - Python 3.11 이상 버전

### - 전체 또는 부분 Tasker XML 파일: backup.xml 또는 기타 Tasker 내보내기 XML 파일

&nbsp;&nbsp;&nbsp;Tasker 버전 5 또는 버전 6에서 생성된, 데스크톱에 있는 내보낸 XML 파일(예: backup.xml)을 찾아 지정하라는 안내가 표시됩니다. 선택적으로 Android 기기에서 직접 가져올 수도 있습니다 (참고 [노트 2](#2)).

### - AI 분석

&nbsp;&nbsp;&nbsp;서버 기반 분석을 사용하는 경우 유효한 API 키가 필요하며, 로컬 분석을 위해서는 Ollama 설치가 필요합니다 (참고 [노트 3](#3)).

## 설치

이 프로그램과 모든 전제 조건은 약 230MB의 공간을 차지합니다. 가상 환경(옵션 2)에 설치하는 것이 권장됩니다.

- 터미널/명령 프롬프트에 다음 명령 중 하나를 입력하여 MapTasker를 설치하세요:

     ```python -m pip install maptasker -U```
                 ...또는...
     ```uv add maptasker```

- 가상 환경에 설치하려면 터미널/명령 프롬프트에 다음 명령을 입력하세요:

  pip를 통해...
  - `cd xxx`, 여기서 'xxx'는 가상 환경을 설정할 디렉터리입니다.
  - `python -m venv venv`
  - 가상 환경을 활성화하세요...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `pip install maptasker`

  ...또는...

  uv를 통해...
  - `cd xxx`, 여기서 'xxx'는 가상 환경을 설정할 디렉터리입니다.
  - `uv venv`
  - 가상 환경을 활성화하세요...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `uv pip install maptasker`

- AI 분석 기능에는 추가 라이브러리(OpenAI, Anthropic, Google, Ollama)가 필요합니다. MapTasker는 이를 자동으로 설치하지 않습니다. 필요하다면 `ai` extra와 함께 MapTasker를 설치하세요:

     ```python -m pip install "maptasker[ai]" -U```
                 ...또는...
     ```uv add "maptasker[ai]"```

## 사용법

- 다음 명령을 입력하세요:

     ```maptasker```
     ...또는 uv로 가상 환경을 관리하는 경우...
     ```uv run maptasker```

### 명령줄에서의 리포트

Health Check, Compare, Changes Since, Export, 폴더 감시(watch)는 창 없이 실행되므로, 매일 밤 Tasker 백업을 자동으로 확인할 수 있습니다 (`cron`, 작업 스케줄러, `launchd` 또는 CI 작업을 통해):

```
maptasker -healthcheck -file backup.xml                 # 백업의 문제점
maptasker -compare older.xml newer.xml                  # 두 백업 간의 차이점
maptasker -changes_since week -file backup.xml          # 변경된 내용: today(오늘), week(1주), month(1개월), all(전체), 특정 날짜, 또는 3d(3일)
maptasker -export map -format md -file backup.xml       # Map(또는 diagram)을 md, json 또는 pdf로 내보내기
maptasker -watch ~/TaskerBackups                        # 새 백업을 기록(history)에 저장
```

- **`-file`**은 백업 또는 폴더(그 안에서 가장 최신의 `.xml` 파일이 사용됨)를 받을 수 있습니다. `-outdir`는 파일을 저장할 위치를 지정하고, `-save`는 창(window)에서와 마찬가지로 리포트를 파일로도 저장합니다.
- **리포트만, 오직 리포트만 표준 출력(standard output)으로 전달됩니다**. 그 외의 모든 것은 표준 오류(standard error)로 전달되므로, `maptasker -healthcheck -file backup.xml > report.txt`는 깨끗한 리포트를 만듭니다.
- **종료 코드(Exit codes)**는 스크립트가 결과에 따라 동작할 수 있게 합니다:

  | 코드 | 의미 |
  |---|---|
  | 0 | 완료되었으며 보고할 내용이 없음 |
  | 10 | 리포트에서 무언가를 발견함: Health Check 오류(경고를 포함하려면 `-fail_on warning`, 무시하려면 `-fail_on never`) 또는 차이점 |
  | 11 | `-changes_since`가 비교할 이전 구성이 없음 (첫 실행이 기록(history)을 시작함) |
  | 1 | 프로그램 오류 |
  | 2 | 파일을 쓸 수 없음(사용할 수 없는 `-outdir` 폴더 포함), 또는 출력을 생성할 수 없음 |
  | 3 | 파일이 유효한 Tasker 백업이 아님 |
  | 5 | 요청한 단일 Project, Profile 또는 Task(`-project`, `-profile` 또는 `-task`)를 찾을 수 없음 |
  | 6 | 파일이 지정되지 않았거나, 파일/폴더가 존재하지 않음 |
  | 7 | 잘못된 옵션, 예를 들어 잘못된 색상, 알 수 없는 `-fail_on` 값, 또는 파일을 자기 자신과 비교하는 경우 |
  | 8 | Tasker 서버를 실행 중인 Android 기기에 대한 요청이 실패함 |

- **기록(History).** 로드된 모든 백업은 구성 기록(configuration history)에 기록되며, 이는 `-changes_since`가 읽는 데이터입니다. `-watch FOLDER`는 `FOLDER`에 나타나는 새롭고 완전한 백업을 파일의 날짜에 따라 기록하므로, MapTasker를 한 번도 열지 않은 날에도 기록이 채워집니다. `-watch FOLDER -once`는 예약된 작업을 위해 한 번만 확인합니다. 기록은 MapTasker가 실행되는 디렉터리의 `MapTasker_Timeline` 폴더에 보관되므로, 예약된 작업은 창(window)이 사용하는 것과 동일한 폴더를 가리키도록 `-history_dir`을 사용해야 합니다.
- **다른 것은 변경되지 않습니다.** 이러한 실행은 브라우저를 열지 않으며, 창(window)이 보관하는 설정을 다시 쓰지 않습니다.

## 프로그램 출력

MapTasker는 데스크톱과 Android 기기 모두에 여러 출력 파일을 생성합니다.

MapTasker가 생성하는 출력의 전체 목록은 [위키(wiki)](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output)를 참조하세요.

## 더 보기: [[런타임 옵션]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[런타임 옵션 예시]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[샘플 출력]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## 프로젝트 구조

주요 파일과 그 용도에 대한 간략한 개요입니다:

- `maptasker/`: 핵심 애플리케이션 코드 포함.
  - `maptasker/src/`: MapTasker의 로직을 위한 주요 파이썬 소스 파일, 계층별 하위 패키지로 구성됨
    (하나의 층은 그 위에 있는 층에서만 데이터를 가져올 수 있으며, `lint-imports`는 이를 강제합니다):
    - `gui/`: NiceGUI 창, 대화 상자 및 해당 이벤트 처리기.
    - `device/`: Tasker 앱이 안드로이드 장치에서 Tasker의 HTTP 서버를 통해 수행하는 작업.
    - `mapops/`: 대량 교체, 리팩토링, 수리, 복구 및 초안 작성; TaskerNet 및 준비 도구.
    - `analysis/`: 구성에 대해 묻는 읽기 전용 질문
    - `mapgen/` 및 `edit/`: 백업 로드 및 맵 생성, 그리고 맵, 프로필, 프로젝트 및 시퀀스 편집기 사용.
    - `core/`: 실행 상태, Tasker 액션 테이블 및 공유 유틸리티.
    - `mapit.py`, `progargs.py`, `runcli.py`, `rungui.py`, `clireports.py`: 진입 지점.
  - `maptasker/assets/`: 애플리케이션에서 사용되는 아이콘, 이미지, JSON 데이터와 같은 정적 자산.
  - `maptasker/locale`: 번역을 위한 언어 파일.
- `documentation_images/`: 이 README 및 기타 문서에 사용된 이미지.
- `tools/`: 개발 과정에서 사용된 도구.
- `tests/`: 코드 품질을 보장하기 위한 테스트 스크립트 및 관련 파일 포함.
- `maptasker/main.py`: `maptasker` 명령 뒤에 위치한 진입 지점입니다. 복제된 저장소에서 `python -m maptasker.main`를 실행합니다.
- `LICENSE`: 이 프로젝트에 사용되는 MIT 라이선스 파일.
- `README.md`: 이 파일.
- `Changelog.md`: 각 버전에서 이루어진 변경 사항의 기록.
- `pyproject.toml`: 프로젝트 메타데이터 및 빌드 시스템 설정.

## 라이선스

이 프로젝트는 [MIT 라이선스](../LICENSE)에 따라 라이선스가 부여됩니다.

MIT 라이선스는 매사추세츠 공과대학교(MIT)에서 시작된 허용적(permissive) 자유 소프트웨어 라이선스입니다. 허용적 라이선스로서, 재사용에 대해 매우 제한적인 제약만을 두므로 라이선스 호환성이 높습니다.

간단히 말해, 이는 다음을 자유롭게 할 수 있다는 의미입니다:

- **사용**: 어떤 목적으로든(상업적 또는 개인적) 소프트웨어를 사용할 수 있습니다.
- **수정**: 소프트웨어를 수정할 수 있습니다.
- **배포**: 원본 또는 수정된 소프트웨어를 배포할 수 있습니다.
- **재라이선스**: 소프트웨어를 재라이선스할 수 있습니다.

다음을 수행해야 합니다:

- **저작권 포함**: 소프트웨어의 상당한 부분에 원본 저작권 고지와 라이선스 자체를 포함해야 합니다.

소프트웨어는 어떠한 형태의 보증 없이 "있는 그대로(AS IS)" 제공됩니다. 전체 라이선스 텍스트는 [LICENSE](../LICENSE) 파일을 참조하세요.

## 문제 해결 및 FAQ

**Q: Windows의 메모장(Notepad)에서 `MapTasker_Map.txt` 다이어그램이 잘못 정렬되어 보입니다.**

A: 메모장이 이 파일의 간격을 올바르게 처리하지 못할 수 있습니다.

Notepad++, VS Code 또는 Typepad와 같은 다른 텍스트 편집기를 사용하는 것이 권장됩니다(그리고 `.txt` 파일의 기본값으로 설정하세요). '자동 줄 바꿈'이 꺼져 있고 고정폭 글꼴이 사용되고 있는지 확인하세요.

**Q: Android 기기에서 직접 Tasker XML 파일을 가져오려면 어떻게 하나요?**

A: 전제 조건:

1- 브라우저와 Android 기기가 동일한 로컬 네트워크에 있어야 합니다.

2- ['Http Server Example' Tasker 프로젝트](https://shorturl.at/bwCD4)가 Android 기기에 설치되어 활성화되어 있고, 서버가 실행 중이어야 합니다.

자세한 내용은 이 README의 "노트" 섹션에서 확인할 수 있습니다.

**Q: 중국어, 한국어 또는 일본어 이름에 대해 다이어그램 연결선이 잘못 정렬됩니다.**

A: 이것은 다이어그램 작성 라이브러리에서 이러한 언어의 글꼴 메트릭과 관련된 알려진 문제입니다.

**Q: 일부 Task action과 Profile state/event는 왜 편집/추가할 수 없나요?

A: 경우에 따라 이러한 action, event 또는 state는 Android 및/또는 Tasker 내부에서만 사용할 수 있는 정보를 필요로 합니다. 이러한 항목의 편집을 허용하면 Task 또는 Profile이 불완전해져 Tasker 오류가 발생할 수 있습니다.

## 노트

"문제 해결 및 FAQ" 섹션에서 언급된 일부 사항에 대한 세부 정보는 추가적인 맥락을 위해 여기에 보존되어 있습니다.

### 1
**Windows 11 관련 사항:**

- Windows 11만 지원됩니다. 이전 버전의 Windows는 지원되지 않습니다.
- 메모장에서 `MapTasker_Map.txt` 표시 문제가 있는 경우, Typepad와 같은 다른 텍스트 편집기를 사용하고 `.txt` 파일의 기본값으로 설정하세요.

### 2
**Android에서 XML을 직접 가져오기:**

Tasker XML 파일을 직접 가져오려면:

- 데스크톱과 Android 기기가 동일한 로컬 네트워크에 있고 Tasker가 실행 중인지 확인하세요.
- ['Http Server Example' Tasker 프로젝트](https://shorturl.at/bwCD4)가 Android 기기에 설치되어 활성화되어 있고, 서버가 실행 중이어야 합니다. "Update GD HTTP Info" Task를 실행하고 (처음 한 번만) 안내가 표시되면 Google Drive ID를 입력하는 것을 잊지 마세요.
- 가져온 후에는 XML이 데스크톱에 저장되며, 변경되지 않는 한 계속해서 다시 가져올 필요가 없습니다.

### 3
**AI 지원**

AI 분석은 GUI를 통해서만 사용할 수 있습니다. 단일 Project, Profile, Task 또는 Scene만 사용하여 분석을 실행할 수 있습니다. 서버 기반 OpenAi(ChatGPT), Gemini, Anthropic 및 로컬 기반 Llama 모델이 지원됩니다.

Llama 기반 모델은 [Ollama](https://ollama.com/)를 통해 지원되며, 데스크톱에 서버를 설정하기 위해 직접 다운로드, 설치 및 한 번 실행해야 합니다. Llama 모델이 아직 로드되지 않은 경우 MapTasker가 이를 동적으로 로드해 줍니다.

AI 지원 모듈은 MapTasker를 설치할 때 기본적으로 설치되지 않습니다. 대신 특정 AI 요청을 처음 사용할 때 동적으로 설치됩니다. 이러한 방식으로 AI를 사용할 계획이 없다면 그에 따른 오버헤드가 발생하지 않습니다.

## 애플리케이션 편집 및 분석 주의 사항
**MapTasker 편집 및 분석 주의 사항**

자세한 내용은 [주의 사항(Caveats)](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt) 문서를 참조하세요.

## 할 일 목록 (특정 순서 없음)

- [x] 준비 상태 확인 (Readiness Check)

- [x] 추가 플러그인 지원

- [x] 종속성 포함 가져오기 (Import with Dependencies)

- [x] 작업 테스트 - 작업 단계별 세션을 변경 전후로 저장하고 비교

- [ ] 남은 Tasker 환경설정 매핑

- [x] Task Stepper: Task를 action 단위로 "드라이런"하여 어떤 If, For, Goto 분기가 실행되는지와 각 변수가 가진 값을 표시

- [x] TaskerNet 업데이트 추적 기능: 사용하시는 앱의 개발자가 새로운 버전을 출시했을 때 알림을 제공하며, 변경된 내용의 차이점을 보여줍니다.

- [x] 리소스 누락 확인: 사용자가 참조하는 파일, 폴더, 이미지, 사운드, 장면 및 앱이 여전히 존재하는지 확인합니다.

- [x] Live Run Monitor: 휴대폰에서 어떤 Profile과 Task가 트리거되는지 실시간 스트리밍하고 Diagram View에서 강조 표시

- [ ] 공통 조상에 대한 두 백업의 3방향 병합(Three-way merge), 충돌별로 해결하고 한 단계로 실행 취소

- [x] TaskerNet 업데이트 추적기: 사용 중인 공유의 작성자가 새 버전을 게시하면 변경 사항의 diff와 함께 알려줌

- [ ] 개인 스니펫 라이브러리: 재사용 가능한 action 시퀀스, Task, Profile 템플릿을 저장하고 매개변수와 함께 삽입

- [ ] Map 내 쉬운 설명: AI가 작성하고 캐시되며 편집 가능한, 각 Profile과 Task에 대한 한 줄 요약

- [x] 누락된 리소스 확인기: action이 참조하는 파일, 폴더, 이미지, 소리, Scene, 앱이 여전히 존재하는지 확인

- [x] 복잡성 및 추세 대시보드: 시간에 따른 Task 길이, 중첩, 호출 체인 깊이, 발견 사항을 추적

- [ ] 문서 사이트 내보내기: Project, Profile, Task, Scene마다 하나씩, 호출 다이어그램이 포함된 상호 연결된 Markdown 또는 HTML 페이지 모음

## 개인정보 보호 정책

아래(네트워크 트래픽)에 나열된 것을 제외하고는, 어떠한 정보도 네트워크를 통해 수집되어 저 또는 다른 제3자에게 전송되지 않습니다.

오류를 신고할 경우, 오류의 출력 로그 파일과 XML 파일을 제공하라는 요청을 받을 가능성이 높으며, 둘 다 프로그램 디버깅에만 사용된 후 즉시 삭제됩니다.

네트워크 트래픽은 다음과 같습니다:

- Android 기기에서 직접 XML을 가져올 때의 로컬 LAN 트래픽.
- 시작 시 하루에 한 번, pypi.com에서 새 릴리스가 있는지 확인합니다.
- GUI에서 'Upgrade'를 선택하면 pypi.com에서('pip'를 통해) 프로그램을 업데이트합니다.
- GUI에서 "What's New"를 선택하면 '<https://github.com/mctinker/Map-Tasker>'에서 'Changelog.md' 파일을 읽습니다.
- OpenAi 모델 중 하나로 AI 분석을 사용할 때 chatgpt.com을 사용합니다. MapTasker의 출력은 분석을 위해 표준 API 호출을 통해 서버로 전송됩니다. Claude(Anthropic) 및 Gemini(Google)에도 동일하게 적용됩니다.
- AI 분석 기능을 실행할 때 '<https://ollama.com/library>'에서 새롭고 업데이트된 로컬 AI 모델이 로드됩니다.
- Task action 레이블 및 TaskerNet 설명에서 '<img src=https://...>' HTML 태그로 정의된 이미지 및 비디오 소스 하이퍼링크는 클릭 시 액세스됩니다. 예: imggur.com, Youtube, Dropbox, Google Drive 등.

## 기여하기

기여를 환영합니다! MapTasker에 기여할 수 있는 몇 가지 방법은 다음과 같습니다:

**버그 신고:**

- 버그를 발견하신 경우, [GitHub Issues 페이지](https://github.com/mctinker/Map-Tasker/issues)에 문제를 제기해 주시기 바랍니다.
- 가능한 한 자세한 정보를 포함해 주세요:
  - 버그를 재현하는 방법
  - 예상되는 동작 및 실제 동작
  - 사용 중인 운영체제 및 파이썬 버전.
  - MapTasker 버전.
  - 귀하의 Tasker XML 파일의 관련 부분 (해당하는 경우, 그리고 민감한 정보가 포함되지 않도록 주의).
  - `maptasker.log` 파일이 `-debug` 옵션으로 생성된 경우.

**개선 사항 제안:**

- GitHub에서 issue를 열고 제안 내용을 설명하세요.
- 사용 사례와 이 개선이 왜 유익한지 설명하세요.

**Pull Request:**

- 코드로 기여하고 싶다면:
    1. 리포지토리를 fork하세요.
    2. 기능 또는 버그 수정을 위한 새 branch를 만드세요(예: `feature/new-output-format` 또는 `fix/xml-parsing-error`).
    3. 변경 사항을 적용하세요.
    4. 코드가 Black 코드 스타일을 따르는지 확인하세요(배지에 표시된 대로).
    5. 해당하는 경우 `tests/` 디렉터리에 변경 사항에 대한 테스트를 추가하세요.
    6. 모든 테스트가 통과하는지 확인하세요.
    7. `Master` branch에 pull request를 제출하세요.

**코드 스타일:**

- 이 프로젝트는 코드 포맷팅을 위해 [Ruff](https://docs.astral.sh/ruff/formatter/)를 사용합니다. 기여 내용이 Ruff로 포맷되었는지 확인하세요.

MapTasker를 개선하는 데 도와주셔서 감사합니다!

## 알려진 문제

- 이름이 중국어, 한국어 또는 일본어인 경우 다이어그램 연결선이 잘못 정렬됩니다.
- 일부 Task action 및 Profile state/event 편집은 Android 기기에서만 사용할 수 있는 정보가 필요하기 때문에 지원되지 않습니다.

## 참여자

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021, Clippy](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
