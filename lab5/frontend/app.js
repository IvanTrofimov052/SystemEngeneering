const feedEl = document.getElementById("feed");
const feedMetaEl = document.getElementById("feedMeta");
const detailEl = document.getElementById("detail");
const closeDetailBtn = document.getElementById("closeDetail");
const toastEl = document.getElementById("toast");
const profileBox = document.getElementById("profileBox");
const sessionStatus = document.getElementById("sessionStatus");
const authHint = document.getElementById("authHint");
const avatarForm = document.getElementById("avatarForm");
const newPostLink = document.getElementById("newPostLink");
const feedPanel = document.getElementById("feedPanel");
const logoutBtn = document.getElementById("logoutBtn");
const refreshBtn = document.getElementById("refreshBtn");
const loginLink = document.getElementById("loginLink");
const registerLink = document.getElementById("registerLink");

const state = {
  token: localStorage.getItem("token") || "",
  me: null,
  feed: [],
  detail: null,
};

const placeholderAvatar =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96'>" +
      "<rect width='96' height='96' fill='#f1e7de'/>" +
      "<circle cx='48' cy='38' r='18' fill='#d8c7b8'/>" +
      "<rect x='20' y='60' width='56' height='24' rx='12' fill='#d8c7b8'/>" +
    "</svg>"
  );

const iconHeart = `
  <span class="tag-icon" aria-hidden="true">
    <svg viewBox="0 0 24 24">
      <path d="M12 20.5s-7-4.6-9.4-8.6A5.5 5.5 0 0 1 12 4.3a5.5 5.5 0 0 1 9.4 7.6C19 15.9 12 20.5 12 20.5z"></path>
    </svg>
  </span>
`;

const iconComment = `
  <span class="tag-icon" aria-hidden="true">
    <svg viewBox="0 0 24 24">
      <path d="M20 14.5a4.5 4.5 0 0 1-4.5 4.5H9l-5 3v-13A4.5 4.5 0 0 1 8.5 4h7A4.5 4.5 0 0 1 20 8.5z"></path>
    </svg>
  </span>
`;

function goToPostPage(postId) {
  window.location.href = `/post/${postId}`;
}

function setToken(token) {
  state.token = token;
  if (token) {
    localStorage.setItem("token", token);
  } else {
    localStorage.removeItem("token");
  }
}

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

function formatTime(value) {
  try {
    const date = new Date(value);
    return new Intl.DateTimeFormat("ru-RU", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  } catch {
    return value;
  }
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

async function loadMe() {
  if (!state.token) {
    state.me = null;
    renderProfile();
    return;
  }
  try {
    state.me = await api("/users/me");
  } catch (err) {
    setToken("");
    state.me = null;
    showToast(err.message, true);
  }
  renderProfile();
}

async function loadFeed() {
  try {
    state.feed = await api("/feed");
    renderFeed();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function openPost(postId) {
  try {
    state.detail = await api(`/posts/${postId}`);
    renderDetail();
  } catch (err) {
    showToast(err.message, true);
  }
}

function renderProfile() {
  if (!state.me) {
    profileBox.textContent = "Вы не авторизованы";
    avatarForm.hidden = true;
    logoutBtn.hidden = true;
    authHint.hidden = false;
    newPostLink.hidden = true;
    loginLink.hidden = false;
    registerLink.hidden = false;
    sessionStatus.textContent = "Сессия: нет";
    sessionStatus.classList.remove("active");
    return;
  }
  profileBox.innerHTML = `
    <div class="profile-line">
      <img class="avatar" src="${state.me.avatar_url || placeholderAvatar}" alt="Аватар" />
      <div>
        <div><strong>${state.me.name}</strong></div>
        <div class="muted">${state.me.email}</div>
      </div>
    </div>
    <div class="muted">Дата регистрации: ${formatTime(state.me.created_at)}</div>
  `;
  avatarForm.hidden = false;
  logoutBtn.hidden = false;
  authHint.hidden = true;
  newPostLink.hidden = false;
  loginLink.hidden = true;
  registerLink.hidden = true;
  sessionStatus.textContent = `Сессия: активна (${state.me.email})`;
  sessionStatus.classList.add("active");
}

function renderFeed() {
  feedEl.innerHTML = "";
  feedMetaEl.textContent = `${state.feed.length} поста`;
  if (!state.feed.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "Пока нет постов. Создайте первый!";
    feedEl.appendChild(empty);
    return;
  }

  state.feed.forEach((post, index) => {
    const item = document.createElement("article");
    item.className = "feed-item";
    item.style.animationDelay = `${index * 0.04}s`;
    item.innerHTML = `
      <div class="profile-line">
        <img class="avatar" src="${post.author_avatar_url || placeholderAvatar}" alt="${post.author_name}" />
        <div>
          <div><strong>${post.author_name}</strong></div>
          <div class="muted">${formatTime(post.created_at)}</div>
        </div>
      </div>
      <div>${post.text}</div>
      ${post.image_url ? `<img class="post-image" src="${post.image_url}" alt="Изображение поста" />` : ""}
      <div class="feed-meta">
        <span class="tag action like ${post.liked_by_me ? "is-liked" : ""}" data-like-toggle="${post.id}">${iconHeart}<span>${post.likes_count}</span></span>
        <span class="tag action" data-open-page="${post.id}">${iconComment}<span>${post.comments_count}</span></span>
      </div>
      <div class="feed-actions">
        <button class="btn ghost" data-open="${post.id}">Открыть</button>
      </div>
    `;
    feedEl.appendChild(item);
  });
}

function renderDetail() {
  if (!state.detail) {
    detailEl.textContent = "Выберите пост из ленты";
    closeDetailBtn.hidden = true;
    return;
  }
  closeDetailBtn.hidden = false;
  const post = state.detail.post;
  const comments = state.detail.comments || [];
  const canEdit = state.me && state.me.id === post.author_id;

  detailEl.innerHTML = `
    <div class="profile-line">
      <img class="avatar" src="${post.author_avatar_url || placeholderAvatar}" alt="${post.author_name}" />
      <div>
        <div><strong>${post.author_name}</strong></div>
        <div class="muted">${formatTime(post.created_at)}</div>
      </div>
    </div>
    <div class="post-text">${post.text}</div>
    ${post.image_url ? `<img class="post-image" src="${post.image_url}" alt="" />` : ""}
    <div class="feed-meta">
      <span class="tag action like ${state.detail.liked_by_me ? "is-liked" : ""}" data-like-toggle="${post.id}">${iconHeart}<span>${post.likes_count}</span></span>
      <span class="tag">${iconComment}<span>${post.comments_count}</span></span>
    </div>
    <div class="feed-actions">
      ${canEdit ? `<a class="btn ghost" href="/posts/${post.id}/edit">Редактировать</a><button class="btn danger" id="deletePost">Удалить</button>` : ""}
    </div>
    <div>
      <h3>Комментарии</h3>
      ${comments.length ? comments.map(renderComment).join("") : "<div class=\"muted\">Комментариев пока нет</div>"}
    </div>
    ${state.me ? `
      <form id="commentForm" class="form">
        <textarea name="text" rows="3" placeholder="Ваш комментарий" required></textarea>
        <button class="btn">Отправить</button>
      </form>
    ` : `<div class="muted">Войдите, чтобы комментировать.</div>`}
  `;

  const deleteBtn = document.getElementById("deletePost");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("Удалить пост?")) return;
      try {
        await api(`/posts/${post.id}`, { method: "DELETE" });
        state.detail = null;
        renderDetail();
        await loadFeed();
      } catch (err) {
        showToast(err.message, true);
      }
    });
  }


  const commentForm = document.getElementById("commentForm");
  if (commentForm) {
    commentForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = new FormData(commentForm).get("text");
      try {
        await api(`/posts/${post.id}/comments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        await openPost(post.id);
        await loadFeed();
      } catch (err) {
        showToast(err.message, true);
      }
    });
  }
}

function renderComment(comment) {
  return `
    <div class="comment">
      <div class="profile-line">
        <img class="avatar" src="${comment.author_avatar_url || placeholderAvatar}" alt="" />
        <div>
          <div><strong>${comment.author_name}</strong></div>
          <div class="muted">${formatTime(comment.created_at)}</div>
        </div>
      </div>
      <div>${comment.text}</div>
    </div>
  `;
}



avatarForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(avatarForm);
  try {
    await fetch("/users/me/avatar", {
      method: "PUT",
      headers: authHeaders(),
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail || "Ошибка обновления аватара");
      }
    });
    await loadMe();
    await loadFeed();
    showToast("Аватар обновлен");
  } catch (err) {
    showToast(err.message, true);
  }
});

logoutBtn.addEventListener("click", () => {
  setToken("");
  state.me = null;
  renderProfile();
  showToast("Вы вышли");
});

refreshBtn.addEventListener("click", loadFeed);
closeDetailBtn.addEventListener("click", () => {
  state.detail = null;
  renderDetail();
});

feedEl.addEventListener("click", async (event) => {
  const toggleTarget = event.target.closest("[data-like-toggle]");
  if (toggleTarget) {
    try {
      const isLiked = toggleTarget.classList.contains("is-liked");
      if (isLiked) {
        await api(`/posts/${toggleTarget.dataset.likeToggle}/like`, { method: "DELETE" });
      } else {
        await api(`/posts/${toggleTarget.dataset.likeToggle}/like`, { method: "POST" });
      }
      showToast(isLiked ? "Лайк снят" : "Лайк поставлен");
      await openPost(toggleTarget.dataset.likeToggle);
      await loadFeed();
    } catch (err) {
      showToast(err.message, true);
    }
    return;
  }
  const pageTarget = event.target.closest("[data-open-page]");
  if (pageTarget) {
    goToPostPage(pageTarget.dataset.openPage);
    return;
  }
  const openTarget = event.target.closest("[data-open]");
  if (openTarget) {
    await openPost(openTarget.dataset.open);
  }
});

async function bootstrap() {
  await loadMe();
  await loadFeed();
  renderDetail();
  const match = window.location.pathname.match(/^\/post\/(\d+)$/);
  if (match) {
    if (feedPanel) feedPanel.classList.add("hidden");
    await openPost(match[1]);
  }
}

bootstrap();
