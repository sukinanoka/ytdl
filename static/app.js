const inspectForm = document.querySelector("#inspect-form");
const inspectButton = document.querySelector("#inspect-button");
const inspectMessage = document.querySelector("#inspect-message");
const videoResult = document.querySelector("#video-result");
const creatorNote = document.querySelector("#creator-note");

const convertForm = document.querySelector("#convert-form");
const convertButton = document.querySelector("#convert-button");
const convertMessage = document.querySelector("#convert-message");
const progressTrack = document.querySelector("#progress-track");
const fileInput = document.querySelector("#media-file");
const fileLabel = document.querySelector("#file-label");

function showMessage(element, message, type = "") {
  element.textContent = message;
  element.className = `message ${type}`.trim();
}

inspectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  videoResult.classList.add("hidden");
  creatorNote.classList.add("hidden");
  showMessage(inspectMessage, "動画情報を確認しています…");
  inspectButton.disabled = true;

  try {
    const response = await fetch("/api/inspect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: document.querySelector("#youtube-url").value.trim() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "動画情報を取得できませんでした。");

    document.querySelector("#video-title").textContent = data.title;
    document.querySelector("#video-author").textContent = `投稿者：${data.author}`;
    document.querySelector("#video-thumbnail").src = data.thumbnail || "";
    document.querySelector("#watch-link").href = data.watch_url;
    videoResult.classList.remove("hidden");
    creatorNote.classList.remove("hidden");
    showMessage(inspectMessage, "動画情報を確認しました。", "success");
  } catch (error) {
    showMessage(inspectMessage, error.message, "error");
  } finally {
    inspectButton.disabled = false;
  }
});

fileInput.addEventListener("change", () => {
  fileLabel.textContent = fileInput.files[0]?.name || "クリックしてファイルを選択";
});

convertForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    showMessage(convertMessage, "変換するファイルを選択してください。", "error");
    return;
  }
  if (file.size > 250 * 1024 * 1024) {
    showMessage(convertMessage, "ファイルが250MBを超えています。", "error");
    return;
  }

  const formData = new FormData(convertForm);
  convertButton.disabled = true;
  progressTrack.classList.remove("hidden");
  showMessage(convertMessage, "変換しています。完了まで画面を閉じないでください。");

  try {
    const response = await fetch("/api/convert", { method: "POST", body: formData });
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
      const errorData = contentType.includes("application/json")
        ? await response.json()
        : { error: "変換に失敗しました。" };
      throw new Error(errorData.error || "変換に失敗しました。");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    const filename = match ? decodeURIComponent(match[1] || match[2]) : `converted.${document.querySelector("#output-format").value}`;
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
    showMessage(convertMessage, "変換が完了しました。ダウンロードを開始しました。", "success");
  } catch (error) {
    showMessage(convertMessage, error.message, "error");
  } finally {
    convertButton.disabled = false;
    progressTrack.classList.add("hidden");
  }
});
