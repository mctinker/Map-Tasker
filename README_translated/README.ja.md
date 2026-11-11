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

- 出力の詳細レベルは、概要から非常に詳細な設定まで、ご希望に応じて選択いただけます。
- 単一のプロジェクト、プロフィール、またはタスクのみを表示する。
- プロファイルとタスクの条件（状態、イベントなど）の包含/除外
- すべてのデータをストリーミングする、またはすべてのフィールドを揃えて、表示を整える。
- 外観を変更: 'ライト'または'ダーク'モードを選択してください。
- お好みの固定ピッチフォントを使用して出力し、"Project"、"Profile"、および "Task" の名前を、斜体、太字、ハイライト、または下線で強調表示してください。
- 出力のさまざまな要素に関連する色を、自分の気分に合わせて変更してください。
- TaskerNetの説明や/またはTaskerの好みを含める。
- 複雑な設定の場合、プロジェクト、プロフィール、タスク、シーンへのショートカットリンクをまとめた辞書を、必要に応じて含めることができます。
- タスカーの設定全体と、タスクフローを図で表示する。
- コマンドラインまたはGUIインターフェース。
- 構成のマッピングには、エクスポートされたXMLを使用するか、Androidデバイスから直接XMLを取得してください。
- プロジェクト、プロフィール、タスク、シーンを、お使いのAndroidデバイスからTaskerに送信してください。
- 実行時の設定を保存および復元する。
- 「実行ステップが多すぎる」と判断されたタスクを特定し、複数のタスクに分割することを検討する。
- AI 分析オプションにより、サーバー上で動作する ChatGPT/Claude/Gemini、またはローカルで動作する Llama (Ollama を介して) でサポートされているモデルを使用して、特定のプロジェクト、プロファイル、タスク、またはシーンを分析できます。
- 結果をGUI内で直接表示する： (設定) マップ表示、ツリー表示、および図表表示。
- 自動アップデートの検出機能と、オプションでの新しいバージョンのインストール機能。
- 高度な検索機能と、構造化された「検索/置換」機能。
- プロジェクト、プロフィール、タスク、およびシーンの追加と編集 (詳細は [注記 6](#6) を参照)
- 特定の日から変更されたリストの内容を一覧表示する。
- タスカーのXMLファイルの健全性を、また設定における様々な変数を分析してください。
- ロードされたXMLファイルと比較する。
- TaskerNetで、プロジェクト、プロフィール、タスクの最新情報を確認し、利用可能な場合は適用してください。
- 別のXMLファイルからTaskerオブジェクトと、それに関連するすべての依存関係をインポートします。
- コードが改善されているかどうかを確認するために、トレンド分析を行ってください。
- タスクがAndroidデバイス以外の場所で使用するすべてのものをリストアップしてください。
- 特定の条件（状態またはイベント）に基づいて、「何がトリガーとなるか」を特定する。
- タスクの論理を理解し、異なる実行結果を比較してください。
- Androidデバイスでライブモニタリングを実行し、どのプロファイルとタスクが実行されているかを確認してください。
- バッテリーの消耗に繋がる要因を特定してください。
- 読み込むすべてのテキスト（フラッシュ、通知、Say、ダイアログ、シーンラベルなど）をテーブル形式で抽出し、翻訳または編集し、編集後のテキストを再度挿入する。
- グローバル変数の管理: 各変数がどこで設定され、読み込まれるかを確認し、すべての場所で名前を変更し、その値を変更し、携帯電話に送信します。

## プログラムの依存関係

### - Python バージョン 3.11 以上

### - Tasker の完全または部分 XML ファイル：backup.xml、またはその他の Tasker からエクスポートされた XML ファイル

&nbsp;&nbsp;&nbsp;Tasker のバージョン 5 またはバージョン 6 で作成された、デスクトップ上の Tasker からエクスポートされた XML ファイル（例：backup.xml）を探して指定するように求められます。任意で、Android デバイスから直接取得することもできます（[注2](#2) 参照）。

### - AI 分析

&nbsp;&nbsp;&nbsp;サーバーベースの分析を使用する場合は有効な API キーが必要であり、ローカル分析には Ollama のインストールが必要です（[注3](#3) 参照）。

## インストール

このプログラムとそのすべての前提条件は、約 230MB の容量を必要とします。仮想環境へのインストールをお勧めします（オプション2）。

1- MapTaskerをインストールするには、ターミナル/コマンドプロンプトに次のコマンドのいずれかを入力してください:

     ```python -m pip install maptasker -U```
                 ...または...
     ```uv add maptasker```

2- 仮想環境にインストールするには、ターミナル/コマンドプロンプトで次のコマンドを入力してください:

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
maptasker -healthcheck -file backup.xml                 # problems in a backup
maptasker -compare older.xml newer.xml                  # what differs between two backups
maptasker -changes_since week -file backup.xml          # what changed: today, week, month, all, a date, or 3d
maptasker -trend -file backup.xml                       # is the configuration getting healthier or messier
maptasker -export map -format md -file backup.xml       # the Map (or diagram) as md, json or pdf
maptasker -text export -file backup.xml                 # every piece of text a person reads, as a table to translate or edit
maptasker -text apply -table edited.csv -file backup.xml  # put the edited table back
maptasker -watch ~/TaskerBackups                        # record each new backup in the history
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

2- 以下の2つのTaskerプロジェクト（どちらも、すべてのプロファイルを有効にした状態でターゲットのAndroidデバイスにインストールする必要があります）：
  ['Http Server Example' Taskerプロジェクト](https://shorturl.at/bwCD4)
  ['Tasker HTTP API' Taskerプロジェクト](https://shorturl.at/hlTj0)

詳細については、このREADMEの[注記2](#2)をご参照ください。

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

- デスクトップおよびAndroidデバイスが同じローカルネットワークに接続され、Taskerが実行されていることを確認してください。
- Taskerプロジェクト ['Http Server Example'](https://shorturl.at/bwCD4) と ['Tasker HTTP API'](https://shorturl.at/hlTj0) の両方が、Androidデバイスにインストールされて有効になっており、サーバーが起動している必要があります。「Update GD HTTP Info」タスクを実行し、初回のみ、求められたときにGoogle Drive IDを入力してください。
  - 注: MapTasker は、'Http Server Example' をインストールするオプションを提供しています。このオプションは、'ANDROID デバイスから XML を取得' のパネルの下にあります。ただし、この機能を使用するには、事前に 'Tasker HTTP API' をインストールしておく必要があります。
- 取得後、XMLはデスクトップに保存され、変更がない限り、再度取得する必要はありません。
- MapTasker の他の機能も、それぞれ個別に Android デバイス上で、その機能を実行するための権限を求めるプロンプトを表示します。

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

- [x] 依存関係付きインポート（Import with Dependencies）

- [x] タスクのテスト - タスクの変更前と後の、タスクステップのセッションを保存し、比較する

- [ ] 残りの Tasker 環境設定のマッピング

- [x] 参照しているファイル、フォルダ、画像、音声、シーン、およびアプリケーションがまだ存在するかどうかを確認する機能：

- [x] Live Run Monitor：電話上でどの Profile と Task がトリガーされるかをライブストリーム表示し、Diagram View でハイライト

- [ ] Map 内の簡単な説明：AI が作成し、キャッシュされ、編集可能な、各 Profile と Task の 1 行要約

- [ ] ドキュメントサイトのエクスポート：Project、Profile、Task、Scene ごとに 1 ページずつ、呼び出しダイアグラムを含む相互リンクされた Markdown または HTML ページ一式

- [ ] ヒートマップを使用して、特定の期間における実際の状況を可視化し、どのような状況で火が発生するかを把握する。

- [ ] 類似度の高いタスク検出機能：コピー＆ペーストされたタスクの中から、わずかな違いがあるものを検出し、統合を提案する機能

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
