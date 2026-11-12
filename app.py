from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from flask import Flask, after_this_request, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
}
MAX_UPLOAD_BYTES = 250 * 1024 * 1024  # 250 MB
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be", "www.youtu.be",
}

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["JSON_AS_ASCII"] = False


def extract_video_id(raw_url: str) -> str | None:
    """Accept ordinary YouTube watch, short, embed, live, and youtu.be URLs."""
    try:
        parsed = urlparse(raw_url.strip())
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.username or parsed.password:
        return None

    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        return None

    video_id = ""
    if host.endswith("youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live", "v"}:
            video_id = path_parts[1]

    return video_id if VIDEO_ID_RE.fullmatch(video_id) else None


def safe_output_stem(filename: str) -> str:
    original_stem = Path(filename).stem
    cleaned = secure_filename(original_stem)
    if not cleaned:
        cleaned = "converted-video"
    return cleaned[:80]


def run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def get_stream_types(input_path: Path) -> set[str]:
    result = run_command(
        [
            "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
            "-of", "json", str(input_path),
        ],
        timeout=30,
    )
    if result.returncode != 0:
        raise ValueError("ファイルを読み取れません。動画・音声ファイルか確認してください。")

    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError as exc:
        raise ValueError("ファイル情報を読み取れませんでした。") from exc

    return {stream.get("codec_type", "") for stream in streams}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.post("/api/inspect")
def inspect_youtube_url():
    payload = request.get_json(silent=True) or {}
    raw_url = str(payload.get("url", "")).strip()
    video_id = extract_video_id(raw_url)

    if not video_id:
        return jsonify({"error": "有効なYouTube動画URLを入力してください。"}), 400

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        response = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": canonical_url, "format": "json"},
            headers={"User-Agent": "Mozilla/5.0 VideoConverterSite/1.0"},
            timeout=(4, 10),
        )
        if response.status_code == 404:
            return jsonify({"error": "動画情報を取得できません。非公開・削除済みの可能性があります。"}), 404
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return jsonify({"error": "YouTubeの動画情報を取得できませんでした。時間をおいて再試行してください。"}), 502
    except ValueError:
        return jsonify({"error": "YouTubeから不正な応答が返されました。"}), 502

    return jsonify(
        {
            "video_id": video_id,
            "title": data.get("title", "タイトル不明"),
            "author": data.get("author_name", "投稿者不明"),
            "thumbnail": data.get("thumbnail_url"),
            "watch_url": canonical_url,
            "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
        }
    )


@app.post("/api/convert")
def convert_uploaded_file():
    upload = request.files.get("file")
    output_format = str(request.form.get("format", "")).lower()

    if upload is None or not upload.filename:
        return jsonify({"error": "変換するファイルを選択してください。"}), 400
    if output_format not in {"mp3", "mp4"}:
        return jsonify({"error": "出力形式はMP3またはMP4を選択してください。"}), 400

    original_name = upload.filename
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "対応していないファイル形式です。"}), 400

    output_stem = safe_output_stem(original_name)
    temporary_directory = tempfile.TemporaryDirectory(prefix="video-converter-")
    work_dir = Path(temporary_directory.name)
    input_path = work_dir / f"input{suffix}"
    output_path = work_dir / f"{output_stem}.{output_format}"

    try:
        upload.save(input_path)
        if input_path.stat().st_size == 0:
            raise ValueError("空のファイルは変換できません。")

        stream_types = get_stream_types(input_path)
        if output_format == "mp3":
            if "audio" not in stream_types:
                raise ValueError("このファイルには音声トラックがありません。")
            command = [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(input_path), "-map", "0:a:0", "-vn",
                "-codec:a", "libmp3lame", "-q:a", "2", str(output_path),
            ]
        else:
            if "video" not in stream_types:
                raise ValueError("MP4にするには映像を含むファイルが必要です。")
            command = [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(input_path), "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                str(output_path),
            ]

        result = run_command(command, timeout=300)
        if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
            raise ValueError("変換に失敗しました。別のファイルで試してください。")

        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f"{output_stem}.{output_format}",
            mimetype="audio/mpeg" if output_format == "mp3" else "video/mp4",
            max_age=0,
        )
        response.call_on_close(temporary_directory.cleanup)
        return response

    except ValueError as exc:
        temporary_directory.cleanup()
        return jsonify({"error": str(exc)}), 400
    except subprocess.TimeoutExpired:
        temporary_directory.cleanup()
        return jsonify({"error": "変換時間が上限を超えました。短い動画で試してください。"}), 408
    except FileNotFoundError:
        temporary_directory.cleanup()
        app.logger.exception("FFmpeg or FFprobe was not found")
        return jsonify({"error": "サーバーにFFmpegがありません。管理者に連絡してください。"}), 500
    except Exception:
        temporary_directory.cleanup()
        app.logger.exception("Unexpected conversion error")
        return jsonify({"error": "変換中に予期しないエラーが発生しました。"}), 500


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "ファイルが大きすぎます。上限は250MBです。"}), 413


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
