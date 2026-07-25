/* ============================================================
   山河有文 — 前端公共脚本
   导航 / API 客户端 / 事实高亮 / 语气偏好 / 工具函数
   ============================================================ */
window.Wenan = (() => {
  const LS = {
    apiBase: "wenan.apiBase",
    tone: "wenan.tone",
    factHighlight: "wenan.factHighlight",
  };

  const platformNames = { xiaohongshu: "小红书", video: "短视频", moments: "朋友圈" };
  const platformEns = { xiaohongshu: "XIAOHONGSHU", video: "SHORT VIDEO", moments: "MOMENTS" };
  const platformLogos = {
    xiaohongshu: { mark: "红", cls: "lg-xhs", sub: "种草文" },
    video: { mark: "抖", cls: "lg-dy", sub: "口播脚本" },
    moments: { mark: "友", cls: "lg-wx", sub: "海报配文" },
  };
  const platformOrder = ["xiaohongshu", "video", "moments"];
  const factTypeNames = {
    era: "年代", date: "日期", person: "人名", place: "地名", organization: "机构",
    number: "数字", area: "面积", price: "票价", opening_hours: "开放时间", event: "事件", other: "其他",
  };
  const statusNames = { success: "生成成功", partial_failure: "部分失败", failed: "生成失败", processing: "处理中" };
  const validationNames = { passed: "校验通过", failed: "校验未过", pending: "待校验", not_completed: "校验未完成" };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function apiBase() {
    return (localStorage.getItem(LS.apiBase) || "").trim().replace(/\/+$/, "");
  }

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(apiBase() + path, options);
    } catch {
      throw new Error("无法连接后端服务，请确认服务已启动（或在设置页检查 API 地址）");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const message = data?.error?.message
        ?? data?.detail?.[0]?.msg
        ?? (typeof data?.detail === "string" ? data.detail : null)
        ?? `请求失败（HTTP ${response.status}）`;
      throw new Error(message);
    }
    return data;
  }

  const api = {
    health: () => request("/health"),
    generate: (payload) => request("/api/v1/sessions/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
    getSession: (id) => request(`/api/v1/sessions/${encodeURIComponent(id)}`),
    listSessions: (limit = 50) => request(`/api/v1/sessions?limit=${limit}`),
    regenerate: (id, platform, instruction) => request(
      `/api/v1/sessions/${encodeURIComponent(id)}/outputs/${platform}/regenerate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_instruction: instruction }),
      },
    ),
  };

  /* 顶部导航 + 健康徽章 */
  function mountNav(active) {
    const host = document.querySelector("#topnav");
    if (!host) return;
    host.className = "topnav";
    const inner = el("div", "topnav-inner");

    const brand = el("a", "brand");
    brand.href = "index.html";
    brand.append(el("span", "seal", "種"), el("span", "brand-name", "山河有文"));

    const links = el("nav", "nav-links");
    [
      ["index.html", "工作台", "workbench"],
      ["history.html", "历史记录", "history"],
      ["settings.html", "设置", "settings"],
    ].forEach(([href, label, key]) => {
      const a = el("a", key === active ? "active" : "", label);
      a.href = href;
      links.append(a);
    });

    const right = el("div", "nav-right");
    const healthBadge = el("span", "health");
    const dot = el("span", "health-dot");
    dot.style.background = "#c9a227";
    const label = el("span", "", "正在连接后端");
    healthBadge.append(dot, label);
    right.append(healthBadge);

    inner.append(brand, links, right);
    host.replaceChildren(inner);

    api.health().then((h) => {
      dot.style.background = "#3d8a5a";
      const mode = h.model_mode === "openai" ? "在线模型" : "本地引擎";
      label.textContent = `后端已连接 · ${mode}`;
    }).catch(() => {
      dot.style.background = "#b3402a";
      label.textContent = "后端未连接";
    });
  }

  /* 时间与文本工具 */
  function fmtTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  function truncate(text, n = 42) {
    const s = String(text || "").replace(/\s+/g, " ").trim();
    return s.length > n ? `${s.slice(0, n)}…` : s;
  }

  /* 〖〗事实高亮（设置页可全局关闭） */
  function appendHighlighted(parent, text = "") {
    String(text).split(/(〖[^〗]+〗)/g).forEach((part) => {
      if (!part) return;
      if (part.startsWith("〖") && part.endsWith("〗")) {
        parent.append(el("mark", "fact-mark", part));
      } else {
        parent.append(document.createTextNode(part));
      }
    });
  }

  function applyFactHighlightPref() {
    if (localStorage.getItem(LS.factHighlight) === "off") {
      document.body.classList.add("fact-hidden");
    }
  }

  /* 复制与轻提示 */
  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const ta = el("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0;pointer-events:none";
      document.body.append(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      ta.remove();
      return ok;
    }
  }

  function toast(message) {
    document.querySelectorAll(".toast").forEach((t) => t.remove());
    const t = el("div", "toast", message);
    document.body.append(t);
    requestAnimationFrame(() => t.classList.add("show"));
    setTimeout(() => {
      t.classList.remove("show");
      setTimeout(() => t.remove(), 400);
    }, 2200);
  }

  /* 平台语气偏好（设置页调节，生成时自动附加给引擎） */
  const TONE_DEFAULT = { xiaohongshu: 85, video: 70, moments: 40 };

  function getTone() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(LS.tone) || "{}"); } catch { saved = {}; }
    return { ...TONE_DEFAULT, ...saved };
  }

  function setTone(tone) {
    localStorage.setItem(LS.tone, JSON.stringify(tone));
  }

  function toneLabel(v) {
    return v >= 67 ? "放飞" : v >= 34 ? "适中" : "克制";
  }

  function toneInstruction() {
    const t = getTone();
    return `语气偏好：小红书${toneLabel(t.xiaohongshu)}、短视频${toneLabel(t.video)}、朋友圈${toneLabel(t.moments)}。`;
  }

  function getParam(name) {
    return new URLSearchParams(location.search).get(name);
  }

  return {
    LS, api, el, mountNav, fmtTime, truncate,
    appendHighlighted, applyFactHighlightPref,
    copyText, toast, getTone, setTone, toneLabel, toneInstruction, getParam,
    platformNames, platformEns, platformLogos, platformOrder,
    factTypeNames, statusNames, validationNames,
  };
})();
