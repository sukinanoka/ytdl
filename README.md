# Video Tools

YouTube動画の情報確認と、手元にある動画・音声ファイルのMP3/MP4変換を行うWebアプリです。

## できること

- YouTube URLからタイトル、投稿者、サムネイルを表示
- YouTube Studioへのリンクを表示
- 手元の動画・音声ファイルをMP3へ変換
- 手元の動画ファイルをMP4へ変換
- スマートフォンとPCに対応
- RenderへのDockerデプロイに対応

## YouTube動画のダウンロードについて

このアプリはYouTubeの動画ストリームを自動取得しません。
YouTubeの利用規約では、サービスが明示的に許可する場合などを除き、
コンテンツのダウンロードや自動アクセスが制限されています。
自分が投稿した動画は、YouTube Studioの「コンテンツ」から
動画のメニューを開き、「ダウンロード」を選んで保存できます。
保存したファイルをこのアプリに入れると、MP3/MP4に変換できます。

公式案内： https://support.google.com/youtube/answer/56100?hl=ja
利用規約： https://www.youtube.com/t/terms?gl=JP

## ローカルで起動（Windows）

1. Python 3.12以降をインストールします。
2. FFmpegをインストールし、`ffmpeg` と `ffprobe` にPATHを通します。
3. このフォルダでPowerShellを開きます。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

ブラウザで `http://127.0.0.1:5000` を開きます。

## Renderに公開する手順

1. このフォルダをGitHubの新しいリポジトリにアップロードします。
2. Renderで「New」→「Blueprint」を選びます。
3. GitHubリポジトリを接続します。
4. `render.yaml` の設定を確認してデプロイします。

`Dockerfile` からFFmpegを含む環境を作ります。
RenderのWeb Serviceは `PORT` 環境変数のポートで待ち受けます。

## 制限と注意

- アップロード上限は250MBです。
- 変換時間は最大300秒です。
- 変換ファイルは一時フォルダに置き、送信後に削除します。
- Renderの標準ファイルシステムは一時的です。
- 無料サービスはアクセスがないと停止し、再開に時間がかかる場合があります。
- このサンプルにはログイン機能や利用者ごとの利用制限がありません。
  不特定多数に公開する前に、認証とアクセス制限を追加してください。
- 許可のあるファイルだけを変換してください。

## 主なファイル

- `app.py`：Python/Flaskの処理
- `templates/index.html`：ページ構造
- `static/style.css`：デザイン
- `static/app.js`：画面操作
- `Dockerfile`：FFmpegを含む実行環境
- `render.yaml`：Render設定
