<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - ダウンロード数](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![ダウンロード数](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - ライセンス](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![コードスタイル: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
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

> この翻訳は自動的に生成されたものです。内容に相違がある場合は、[英語のオリジナル README](../README.md) が優先されます。

## Tasker のバックアップまたはエクスポートした XML ファイルに基づいて、デスクトップブラウザ（Mac/Windows 11/Linux）で Tasker の Project、Profile、Task、Scene を表示・編集・分析する

コンフィギュレーションマップ（Configuration Map）...
![MapTasker のコンフィギュレーションマップ：1つの project とその profiles、tasks を色分けされたインデント付きのアウトラインで表示し、各 task の番号付き action とその設定が下に列記されている](../documentation_images/intro.png)

ダイアグラムマップ（Diagram Map）...
![MapTasker のダイアグラムマップ：project とその profiles が箱として描かれ、その下に tasks があり、どの task がどの task を呼び出すかを線で示し、1つの呼び出しパスが強調表示されている](../documentation_images/Introd.png)

[[その他のサンプル]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

これは [Tasker](https://tasker.joaoapps.com/) を補完するアプリケーションで、Web ブラウザ上で動作するように設計されています（[注1](#1) 参照）。

私は自分の Tasker の Project/Profile/Task/Scene が管理不能になりつつあり、電話の画面が小さすぎてそれらをナビゲートするのが難しいことに気づきました。そこで、ローカルのデスクトップドライブに保存した Tasker のバックアップ XML ファイルに基づき、Web ブラウザ内に設定全体の完全なマップを提供する Python プログラムを書きました。

その後、Tasker オブジェクトの編集や Tasker の設定の詳細な分析機能など、多くの追加オプションを加えてこのマップを改良してきました。

Tasker のバックアップ、または他の Tasker からエクスポートされた XML は、手動で PC/Mac/Linux/クラウドドライブにアップロードすることも、本プログラムが Android デバイスから直接取得することもできます（[注2](#2) 参照）。

## 機能

- 概要レベルから非常に詳細なレベルまで、出力の詳細度を自由に選択できます。
- 単一の Project、Profile、または Task のみを表示します。
- Profile と Task の条件（States、Events など）を含める／除外します。
- そのままストリーム出力するか、すべてのフィールドを揃えて出力を「きれいに」整えます。
- 外観を変更：'light'（ライト）または 'dark'（ダーク）モードを選択します。
- お好みの等幅フォントで出力し、Project、Profile、Task の名前をイタリック、ボールド、ハイライト、アンダーラインで強調します。
- 気分に応じて、出力の各要素に関連付けられた色を変更します。
- TaskerNet の説明や Tasker の環境設定（preferences）を含めます。
- 複雑な設定の場合、Project、Profile、Task、Scene へのハイパーリンクの目次を任意で含めることができます。
- Tasker の全体設定のダイアグラムと Task Flow を表示します。
- コマンドライン、または GUI インターフェース。
- エクスポートされた XML を使用するか、設定マッピングのために Android デバイスから直接 XML を取得します。
- Project、Profile、Task、Scene をお使いの Android デバイスの Tasker に送り返します。
- ランタイム設定を保存・復元します。
- 「action」が多すぎる Task を特定し、複数の Task に分割すべきかどうかを判断します。
- サーバーベースの ChatGPT/Claude/Gemini、またはローカルベースの Llama（Ollama 経由）をサポートするモデルを使用して、特定の Project、Profile、Task、Scene を分析する AI 分析オプション。
- 結果を GUI 内に直接表示：（設定）Map View、Tree View、Diagram View。
- 更新の自動検出と新しいバージョンの任意のインストール。
- 強化された検索と構造化された 'Find/Replace'。
- Project、Profile、Task、Scene を追加・編集します（[注6](#6) 参照）。
- 特定の日付以降の変更をリスト表示します。
- Project、Profile、Task、Scene を、それが由来する TaskerNet share にリンクし、作者が新しいバージョンを公開したときに通知を受け取り、その変更を1つずつ取り込みます。
- Tasker の XML の健全性、および設定全体にある多数の変数を分析します。
- XML ファイルを、読み込まれている XML と比較します。

## プログラムの依存関係

### - Python バージョン 3.11 以上

### - Tasker の完全または部分 XML ファイル：backup.xml、またはその他の Tasker からエクスポートされた XML ファイル

&nbsp;&nbsp;&nbsp;Tasker のバージョン 5 またはバージョン 6 で作成された、デスクトップ上の Tasker からエクスポートされた XML ファイル（例：backup.xml）を探して指定するように求められます。任意で、Android デバイスから直接取得することもできます（[注2](#2) 参照）。

### - AI 分析

&nbsp;&nbsp;&nbsp;サーバーベースの分析を使用する場合は有効な API キーが必要であり、ローカル分析には Ollama のインストールが必要です（[注3](#3) 参照）。

## インストール

このプログラムとそのすべての前提条件は、約 230MB の容量を必要とします。仮想環境へのインストールをお勧めします（オプション2）。

- ターミナル／コマンドプロンプトに次のいずれかのコマンドを入力して MapTasker をインストールします：

     ```python -m pip install maptasker -U```
                 ...または...
     ```uv add maptasker```

- 仮想環境にインストールするには、ターミナル／コマンドプロンプトに次のコマンドを入力します：

  pip を使う場合...
  - `cd xxx`（'xxx' は仮想環境を設定したいディレクトリです）。
  - `python -m venv venv`
  - 仮想環境をアクティブ化します...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `pip install maptasker`

  ...または...

  uv を使う場合...
  - `cd xxx`（'xxx' は仮想環境を設定したいディレクトリです）。
  - `uv venv`
  - 仮想環境をアクティブ化します...
    MAC/Linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `uv pip install maptasker`

- AI 分析機能には追加のライブラリ（OpenAI、Anthropic、Google、Ollama）が必要です。MapTasker はこれらを自動的にインストールしません。必要な場合は、代わりに `ai` extra 付きで MapTasker をインストールしてください：

     ```python -m pip install "maptasker[ai]" -U```
                 ...または...
     ```uv add "maptasker[ai]"```

## 使用方法

- 次のコマンドを入力します：

     ```maptasker```
     ...または、uv で仮想環境を管理している場合...
     ```uv run maptasker```

### コマンドラインからのレポート

Health Check、Compare、Changes Since、Export、およびフォルダの監視（watch）はウィンドウなしで実行されるため、毎晩の Tasker バックアップを自動的にチェックできます（`cron`、タスクスケジューラ、`launchd`、または CI ジョブから）：

```
maptasker -healthcheck -file backup.xml                 # バックアップ内の問題
maptasker -compare older.xml newer.xml                  # 2つのバックアップ間の差分
maptasker -changes_since week -file backup.xml          # 何が変更されたか：today（今日）、week（週）、month（月）、all（すべて）、特定の日付、または 3d（3日間）
maptasker -export map -format md -file backup.xml       # Map（またはダイアグラム）を md、json、または pdf として出力
maptasker -watch ~/TaskerBackups                        # 新しいバックアップを履歴に記録
```

- **`-file`** はバックアップ、またはフォルダ（その中の最新の `.xml` ファイルが使用されます）を受け取ります。`-outdir` はファイルの書き込み先を選択し、`-save` はウィンドウと同様にレポートをファイルとしても保存します。
- **レポートのみ、そしてレポートだけが標準出力（standard output）に送られます**。それ以外のすべては標準エラー出力に送られるため、`maptasker -healthcheck -file backup.xml > report.txt` はきれいなレポートになります。
- **終了コード（Exit codes）** により、スクリプトが結果に応じて動作できます：

  | コード | 意味 |
  |---|---|
  | 0 | 完了し、報告すべき内容は何もなかった |
  | 10 | レポートが何かを検出した：Health Check のエラー（警告を含めるには `-fail_on warning`、無視するには `-fail_on never`）、または差分 |
  | 11 | `-changes_since` に比較対象の以前の設定がなかった（最初の実行で履歴が始まる） |
  | 1 | プログラムエラー |
  | 2 | ファイルを書き込めなかった（使用できない `-outdir` フォルダを含む）、または出力を作成できなかった |
  | 3 | ファイルが有効な Tasker バックアップではない |
  | 5 | 要求された単一の Project、Profile、または Task（`-project`、`-profile`、または `-task`）が見つからなかった |
  | 6 | ファイルが指定されなかった、またはファイル／フォルダが存在しない |
  | 7 | 無効なオプション、例えば不正な色、未知の `-fail_on` 値、またはファイルを自分自身と比較した場合 |
  | 8 | Tasker サーバーを実行している Android デバイスへのリクエストが失敗した |

- **履歴（History）。** 読み込まれたすべてのバックアップは設定の履歴に記録され、これは `-changes_since` が読み取るものです。`-watch FOLDER` は `FOLDER` に現れる新しい完全なバックアップをファイルの日付に基づいて記録するため、MapTasker を一度も開かない日でも履歴は蓄積されます。`-watch FOLDER -once` はスケジュールされたジョブのために一度だけチェックします。履歴は MapTasker が実行されるディレクトリ内の `MapTasker_Timeline` フォルダに保存されるため、スケジュールされたジョブはウィンドウが使用するのと同じフォルダを指すように `-history_dir` を使用する必要があります。
- **他には何も変わりません。** これらの実行はブラウザを開くことはなく、ウィンドウが保持している設定を書き換えることもありません。

## プログラムの出力

MapTasker はデスクトップと Android デバイスの両方に複数の出力ファイルを生成します。

MapTasker が生成する出力の完全なリストについては、[wiki](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output) を参照してください。

## 詳細：[[ランタイムオプション]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[ランタイムオプションの例]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[サンプル出力]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## プロジェクト構成

主なファイルとその目的の概要です：

- `maptasker/`: 実際のアプリケーションコードが含まれています。
  - `maptasker/src/`: MapTaskerのロジックに関する主要なPythonソースファイル。レイヤーごとにサブパッケージで整理されています。
    （あるレイヤーは、その下にあるレイヤーから必要なものだけをインポートできます。`lint-imports`はそのルールを強制します。）
    - `gui/`: NiceGUI のウィンドウ、ダイアログ、およびそれらのイベントハンドラ。
    - `device/`: Tasker の HTTP サーバーを通じて、Android デバイス上で TaskTasker が行う処理。
    - `mapops/`: 大量置換、リファクタリング、修理、復元、およびドラフト作成; TaskerNet および関連ツール。
    - `analysis/`: 設定に対して、読み取り専用で質問された項目。
    - `mapgen/` と `edit/`: バックアップの読み込みと、それに基づいてマップの作成、およびタスク、プロファイル、プロジェクト、シーンエディターの使用。
    - `core/`: 実行状態、Taskerのアクションテーブル、および共有ユーティリティ。
    - `mapit.py`、`progargs.py`、`runcli.py`、`rungui.py`、`clireports.py`：開始地点
  - `maptasker/assets/`: アプリケーションで使用されるアイコン、画像、JSONデータなどの静的アセット。
  - `maptasker/locale`: 翻訳用の言語ファイル。
- `documentation_images/`: このREADMEおよびその他のドキュメントで使用されている画像。
- `tools/`: 開発時に使用されたツール。
- `tests/`: コードの品質を保証するためのテストスクリプトおよび関連ファイルが含まれています。
- `maptasker/main.py`: `maptasker`コマンドの背後にあるエントリポイント。クローンされたリポジトリから、`python -m maptasker.main`を実行します。
- `LICENSE`: プロジェクトのライセンスファイル。
- `README.md`: このファイル。
- `Changelog.md`：各バージョンで実施された変更の記録。
- `pyproject.toml`: プロジェクトのメタデータおよびビルドシステムの構成。

## ライセンス

このプロジェクトは [MIT ライセンス](../LICENSE) の下でライセンスされています。

MIT ライセンスは、マサチューセッツ工科大学（MIT）で生まれた許容的（permissive）なフリーソフトウェアライセンスです。許容的ライセンスであるため、再利用に対する制限が非常に限られており、したがって高いライセンス互換性を持っています。

簡単に言えば、これは以下を自由に行えることを意味します：

- **使用**：ソフトウェアを商用・私的を問わずあらゆる目的で使用すること。
- **変更**：ソフトウェアを変更すること。
- **配布**：オリジナルまたは変更したソフトウェアを配布すること。
- **サブライセンス**：ソフトウェアをサブライセンスすること。

以下を行う必要があります：

- **著作権の記載**：ソフトウェアの実質的な部分に、オリジナルの著作権表示とライセンス自体を含めること。

ソフトウェアは、いかなる種類の保証もなく「現状のまま（AS IS）」提供されます。ライセンスの全文については、[LICENSE](../LICENSE) ファイルを参照してください。

## トラブルシューティングと FAQ

**Q：Windows のメモ帳（Notepad）で `MapTasker_Map.txt` のダイアグラムが崩れて表示されます。**

A：メモ帳はこのファイルの間隔を正しく処理できない場合があります。

Notepad++、VS Code、Typepad などの別のテキストエディタを使用することをお勧めします（そして `.txt` ファイルの既定のエディタに設定してください）。「テキストの折り返し」が無効になっており、等幅フォントが使用されていることを確認してください。

**Q：Android デバイスから直接 Tasker XML ファイルを取得するにはどうすればよいですか？**

A：前提条件：

1－ ブラウザと Android デバイスが同じローカルネットワーク上にある必要があります。

2－ Android デバイスに ['Http Server Example' Tasker プロジェクト](https://shorturl.at/bwCD4) がインストールされ、有効になっていて、サーバーが起動している必要があります。

詳細はこの README の「注記」セクションをご覧ください。

**Q：中国語、韓国語、または日本語の名前で、ダイアグラムのコネクタの位置がずれます。**

A：これはダイアグラム描画ライブラリにおける、これらの言語のフォントメトリクスに関連する既知の問題です。

**Q：一部の Task の action や Profile の state/event が編集／追加できないのはなぜですか？

A：場合によっては、これらの action、event、または state には、Android および／または Tasker 自体でのみ利用可能な情報が必要です。これらの編集を許可すると、不完全な Task または Profile になり、Tasker の障害を引き起こす可能性があります。

## 注記

「トラブルシューティングと FAQ」セクションで触れられたいくつかのポイントの詳細を、追加の文脈のためにここに残しています。

### 1
**Windows 11 固有の情報：**

- Windows 11 のみがサポートされています。それ以前の Windows バージョンはサポートされていません。
- メモ帳で `MapTasker_Map.txt` の表示に問題がある場合は、Typepad などの別のテキストエディタを使用し、`.txt` ファイルの既定に設定してください。

### 2
**Android からの XML の直接取得：**

Tasker の XML ファイルを直接取得するには：

- デスクトップと Android デバイスが同じローカルネットワーク上にあり、Tasker が実行されていることを確認してください。
- Android デバイスに ['Http Server Example' Tasker プロジェクト](https://shorturl.at/bwCD4) がインストールされ、有効になっていて、サーバーが起動している必要があります。「Update GD HTTP Info」Task を実行し、（初回のみ）求められたら Google ドライブの ID を入力することを忘れないでください。
- 取得後、XML はデスクトップに保存され、変更がない限り頻繁に再取得する必要はありません。

### 3
**AI サポート**

AI 分析は GUI を通じてのみ利用可能です。分析を実行できるのは単一の Project、Profile、Task、または Scene のみです。サーバーベースの OpenAi（ChatGPT）、Gemini、Anthropic、およびローカルベースの Llama モデルがサポートされています。

Llama ベースのモデルは [Ollama](https://ollama.com/) を介してサポートされており、デスクトップにサーバーを設定するために手動でダウンロード、インストールし、一度実行する必要があります。Llama モデルがまだロードされていない場合、MapTasker はそれを動的にロードします。

AI サポートモジュールは、MapTasker のインストール時には既定でインストールされません。代わりに、特定の AI リクエストが最初に使用されるときに動的にインストールされます。このため、AI を使用する予定がない場合は、そのオーバーヘッドを負うことはありません。

## アプリケーションの編集と分析に関する注意事項
**MapTasker の編集と分析に関する注意事項**

詳細については [Caveats（注意事項）](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt) 文書を参照してください。

## To-Do リスト（特定の順序はありません）

- [x] Readiness Check（準備状況チェック）

- [x] 追加プラグインのサポート

- [x] 依存関係付きインポート（Import with Dependencies）

- [x] タスクのテスト - タスクの変更前と後の、タスクステップのセッションを保存し、比較する

- [ ] 残りの Tasker 環境設定のマッピング

- [x] Task Stepper：Task を action ごとに「ドライラン」し、どの If、For、Goto の分岐が実行されるか、各変数が何を保持しているかを表示

- [x] TaskerNet のアップデート追跡機能: 自分が利用している共有ファイルの作者が、新しいバージョンをリリースした際に、変更点との差分を通知します。

- [x] 参照しているファイル、フォルダ、画像、音声、シーン、およびアプリケーションがまだ存在するかどうかを確認する機能：

- [x] Live Run Monitor：電話上でどの Profile と Task がトリガーされるかをライブストリーム表示し、Diagram View でハイライト

- [ ] 共通の祖先に対する 2 つのバックアップの 3 ウェイマージ（Three-way merge）を、競合ごとに解決し、1 ステップで取り消せるようにする

- [x] TaskerNet 更新トラッカー：使用している share の作者が新しいバージョンを公開したときに、変更の diff とともに通知

- [ ] 個人用スニペットライブラリ：再利用可能な action シーケンス、Task、Profile テンプレートを保存し、パラメータ付きで挿入

- [ ] Map 内の簡単な説明：AI が作成し、キャッシュされ、編集可能な、各 Profile と Task の 1 行要約

- [x] 欠落リソースチェッカー：action が参照するファイル、フォルダ、画像、サウンド、Scene、アプリが依然として存在するかを確認

- [x] 複雑さとトレンドのダッシュボード：Task の長さ、ネスト、呼び出しチェーンの深さ、所見を時間を追って追跡

- [ ] ドキュメントサイトのエクスポート：Project、Profile、Task、Scene ごとに 1 ページずつ、呼び出しダイアグラムを含む相互リンクされた Markdown または HTML ページ一式

## プライバシーに関する声明

以下に記載（ネットワークトラフィック）されているもの以外、情報は一切、ネットワークを介して収集され、私や他の第三者に送信されることはありません。

エラーを報告する際には、エラーの出力ログファイルと XML ファイルの提供を求められる可能性が高く、これらはプログラムのデバッグにのみ使用され、その後直ちに削除されます。

ネットワークトラフィックは以下のとおりです：

- Android デバイスから直接 XML を取得する際のローカル LAN トラフィック。
- 起動時に 1 日 1 回、新しいリリースが利用可能かどうかを pypi.com で確認します。
- GUI で 'Upgrade' を選択すると、pypi.com から（'pip' を介して）プログラムを更新します。
- GUI で「What's New」を選択すると、'<https://github.com/mctinker/Map-Tasker>' から 'Changelog.md' ファイルを読み込みます。
- OpenAi のいずれかのモデルで AI 分析を使用する場合、chatgpt.com が使用されます。MapTasker の出力は、分析のために標準的な API 呼び出しを通じてサーバーに送信されます。Claude（Anthropic）および Gemini（Google）についても同様です。
- AI Analysis 機能を実行すると、新しいおよび更新されたローカル AI モデルが '<https://ollama.com/library>' からロードされます。
- Task の action ラベルおよび TaskerNet の説明内で '<img src=https://...>' HTML タグによって定義された画像および動画のソースへのハイパーリンクは、クリックされた際にアクセスされます。例：imggur.com、Youtube、Dropbox、Google Drive など。

## コントリビューション

コントリビューションを歓迎します！MapTasker への貢献方法には以下のようなものがあります：

**バグの報告：**

- バグを見つけた場合は、[GitHub Issuesページ](https://github.com/mctinker/Map-Tasker/issues)で問題を開くようお願いいたします。
- 可能な限り詳細な情報を記載してください:
  - バグを再現するための手順
  - 期待される動作と実際の動作。
  - お使いのオペレーティングシステムとPythonのバージョン。
  - MapTasker のバージョン。
  - 関連するTaskerのXMLファイルの一部（該当する場合、および機密情報が含まれていないことを確認してください）。
  - `maptasker.log`ファイルが`-debug`オプションで生成された場合。

**改善の提案：**

- GitHub で issue を開き、提案内容を説明してください。
- 使用例と、この改善がなぜ有益であるかを説明してください。

**Pull Request：**

- コードで貢献したい場合：
    1. リポジトリを fork してください。
    2. 機能やバグ修正のための新しい branch を作成してください（例：`feature/new-output-format` や `fix/xml-parsing-error`）。
    3. 変更を加えてください。
    4. コードが Black のコードスタイルに準拠していることを確認してください（バッジに示されているとおり）。
    5. 該当する場合は `tests/` ディレクトリに変更に対するテストを追加してください。
    6. すべてのテストが通ることを確認してください。
    7. `Master` branch に pull request を送信してください。

**コードスタイル：**

- このプロジェクトはコードフォーマットに [Ruff](https://docs.astral.sh/ruff/formatter/) を使用しています。あなたの貢献が Ruff でフォーマットされていることを確認してください。

MapTasker の改善にご協力いただき、ありがとうございます！

## 既知の問題

- 名前が中国語、韓国語、または日本語の場合、ダイアグラムのコネクタの位置がずれます。
- すべての Task の action と Profile の state/event の編集がサポートされているわけではありません。一部は Android デバイス上でのみ利用可能な情報を必要とするためです。

## 貢献

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021、Clippy のために](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/)、[OpenAi](https://openai.com/)、[Claude AI](https://claude.ai)、[Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
