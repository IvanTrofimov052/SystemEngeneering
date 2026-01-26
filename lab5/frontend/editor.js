const toastEl = document.getElementById("toast");
const editorTitle = document.getElementById("editorTitle");
const editorSubtitle = document.getElementById("editorSubtitle");
const sessionStatus = document.getElementById("sessionStatus");
const logoutBtn = document.getElementById("logoutBtn");
const editorForm = document.getElementById("editorForm");
const saveBtn = document.getElementById("saveBtn");
const deleteBtn = document.getElementById("deleteBtn");
const postPreview = document.getElementById("postPreview");
const postPreviewImg = document.getElementById("postPreviewImg");
const postPreviewName = document.getElementById("postPreviewName");
const postPreviewSize = document.getElementById("postPreviewSize");
const clearPostImage = document.getElementById("clearPostImage");
const removeImageInput = document.getElementById("removeImage");
const postImageName = document.getElementById("postImageName");

const state = {
  token: localStorage.getItem("token") || "",
  me: null,
  mode: "new",
  postId: null,
  post: null,
};

function authHeaders() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

function showToast(message, isError = false) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  toastEl.style.background = isError ? "#d1463b" : "#1f1b18";
  setTimeout(() => {
    toastEl.hidden = true;
  }, 2400);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...options.headers,
      ...authHeaders(),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Ошибка сервера");
  }
  return response.json();
}

function detectMode() {
  const path = window.location.pathname;
  if (path === "/posts/new") {
    state.mode = "new";
    return;
  }
  const match = path.match(/\/posts\/(\d+)\/edit$/);
  if (match) {
    state.mode = "edit";
    state.postId = Number(match[1]);
    return;
  }
  state.mode = "new";
}

async function loadMe() {
  if (!state.token) {
    window.location.href = "/login";
    return;
  }
  try {
    state.me = await api("/users/me");
    sessionStatus.textContent = `Сессия: активна (${state.me.email})`;
    sessionStatus.classList.add("active");
    logoutBtn.hidden = false;
  } catch (err) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
}

async function loadPost() {
  if (state.mode !== "edit" || !state.postId) return;
  try {
    const data = await api(`/posts/${state.postId}`);
    state.post = data.post;
    if (state.post.author_id !== state.me.id) {
      showToast("Нет доступа к редактированию", true);
      window.location.href = "/";
      return;
    }
    editorTitle.textContent = "Редактирование";
    editorSubtitle.textContent = "Обновите текст или замените изображение";
    editorForm.querySelector("textarea[name='text']").value = state.post.text;
    deleteBtn.hidden = false;
    setupImagePreview(
      editorForm.querySelector("input[name='image']"),
      postPreview,
      postPreviewImg,
      clearPostImage,
      state.post.image_url,
      removeImageInput,
      postPreviewName,
      postPreviewSize,
      "Текущее изображение"
    );
    if (postImageName) {
      postImageName.textContent = "Файл не выбран";
    }
  } catch (err) {
    showToast(err.message, true);
  }
}

function setupImagePreview(
  inputEl,
  previewWrap,
  imgEl,
  clearBtn,
  existingUrl = "",
  removeInput = null,
  nameEl,
  sizeEl,
  fallbackName = "Новое изображение"
) {
  if (!inputEl) return;
  let removed = false;
  const setPreview = (src, nameText, sizeText) => {
    imgEl.classList.remove("is-ready");
    previewWrap.hidden = true;
    imgEl.onload = () => {
      imgEl.classList.add("is-ready");
      previewWrap.hidden = false;
    };
    imgEl.onerror = () => {
      imgEl.classList.remove("is-ready");
      previewWrap.hidden = true;
    };
    imgEl.src = src || "";
    if (nameEl) nameEl.textContent = nameText || fallbackName;
    if (sizeEl) sizeEl.textContent = sizeText || "—";
  };

  if (existingUrl) {
    setPreview(existingUrl, fallbackName, "—");
    if (removeInput) removeInput.value = "0";
  }
  inputEl.addEventListener("change", () => {
    const file = inputEl.files && inputEl.files[0];
    if (!file) {
      if (postImageName) postImageName.textContent = "Файл не выбран";
      if (existingUrl && !removed) {
        setPreview(existingUrl, fallbackName, "—");
      } else {
        previewWrap.hidden = true;
        imgEl.src = "";
        imgEl.classList.remove("is-ready");
      }
      return;
    }
    removed = false;
    if (removeInput) removeInput.value = "0";
    if (postImageName) postImageName.textContent = file.name;
    const reader = new FileReader();
    reader.onload = () => {
      setPreview(reader.result, file.name, formatBytes(file.size));
    };
    reader.readAsDataURL(file);
  });
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      inputEl.value = "";
      if (postImageName) postImageName.textContent = "Файл не выбран";
      if (existingUrl) {
        removed = true;
        if (removeInput) removeInput.value = "1";
        imgEl.src = "";
        previewWrap.hidden = true;
        imgEl.classList.remove("is-ready");
        if (nameEl) nameEl.textContent = fallbackName;
        if (sizeEl) sizeEl.textContent = "—";
        return;
      }
      imgEl.src = "";
      previewWrap.hidden = true;
      imgEl.classList.remove("is-ready");
    });
  }
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let idx = 0;
  let size = bytes;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(size >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
}

editorForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  saveBtn.disabled = true;
  const formData = new FormData(editorForm);
  try {
    let postId = state.postId;
    let method = "POST";
    let url = "/posts";
    if (state.mode === "edit" && postId) {
      method = "PUT";
      url = `/posts/${postId}`;
    }
    const res = await fetch(url, {
      method,
      headers: authHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      throw new Error(payload.detail || "Ошибка сохранения");
    }
    const payload = await res.json().catch(() => null);
    postId = postId || (payload && payload.id);
    if (postId) {
      window.location.href = `/post/${postId}`;
    } else {
      window.location.href = "/";
    }
  } catch (err) {
    showToast(err.message, true);
  } finally {
    saveBtn.disabled = false;
  }
});

deleteBtn.addEventListener("click", async () => {
  if (!state.postId) return;
  if (!confirm("Удалить пост?")) return;
  try {
    await api(`/posts/${state.postId}`, { method: "DELETE" });
    window.location.href = "/";
  } catch (err) {
    showToast(err.message, true);
  }
});

logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("token");
  window.location.href = "/login";
});

setupImagePreview(
  editorForm.querySelector("input[name='image']"),
  postPreview,
  postPreviewImg,
  clearPostImage,
  "",
  postPreviewName,
  postPreviewSize
);

detectMode();
loadMe().then(loadPost);
