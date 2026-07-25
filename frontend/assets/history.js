/* 界面四 · 历史记录 */
(() => {
  const listHost = document.querySelector("#hs-list");
  const emptyBox = document.querySelector("#hs-empty");
  const loading = document.querySelector("#hs-loading");
  const errorBox = document.querySelector("#hs-error");
  const searchInput = document.querySelector("#hs-q");
  const filtersBar = document.querySelector("#hs-filters");

  const FILTERS = [
    ["all", "全部"],
    ["success", "生成成功"],
    ["partial_failure", "部分失败"],
    ["failed", "生成失败"],
    ["processing", "处理中"],
  ];

  const STATUS_BADGE = {
    success: "badge badge-cinnabar",
    partial_failure: "badge badge-gold",
    failed: "badge badge-dai",
    processing: "badge badge-gold",
  };

  let sessions = [];
  let activeFilter = "all";
  let query = "";

  function renderFilters() {
    filtersBar.replaceChildren();
    FILTERS.forEach(([key, label]) => {
      const chip = Wenan.el("button", `chip${key === activeFilter ? " active" : ""}`, label);
      chip.type = "button";
      chip.addEventListener("click", () => {
        activeFilter = key;
        renderFilters();
        renderList();
      });
      filtersBar.append(chip);
    });
  }

  function visibleSessions() {
    return sessions.filter((s) => {
      if (activeFilter !== "all" && s.status !== activeFilter) return false;
      if (query && !s.original_text_preview?.toLowerCase().includes(query)) return false;
      return true;
    });
  }

  function renderList() {
    listHost.replaceChildren();
    const items = visibleSessions();
    emptyBox.hidden = items.length > 0;

    items.forEach((s) => {
      const card = Wenan.el("article", "card card-hover hs-item");

      const main = Wenan.el("div", "hs-item-main");
      main.append(
        Wenan.el("div", "hs-item-title", Wenan.truncate(s.original_text_preview, 30) || "未命名讲解词"),
        Wenan.el("div", "hs-item-preview", Wenan.truncate(s.original_text_preview, 72)),
      );

      const meta = Wenan.el("div", "hs-item-meta");
      meta.append(
        Wenan.el("span", STATUS_BADGE[s.status] ?? "badge", Wenan.statusNames[s.status] ?? s.status),
        Wenan.el("span", "hs-time", Wenan.fmtTime(s.created_at)),
      );

      const actions = Wenan.el("div", "hs-item-actions");
      const openLink = Wenan.el("a", "linklike", "打开 →");
      openLink.href = `result.html?session=${encodeURIComponent(s.session_id)}`;
      const reviewLink = Wenan.el("a", "linklike", "校验报告");
      reviewLink.href = `review.html?session=${encodeURIComponent(s.session_id)}`;
      actions.append(openLink, reviewLink);

      card.append(main, meta, actions);
      listHost.append(card);
    });
  }

  searchInput.addEventListener("input", () => {
    query = searchInput.value.trim().toLowerCase();
    renderList();
  });

  async function init() {
    Wenan.mountNav("history");
    renderFilters();
    try {
      sessions = await Wenan.api.listSessions(50);
      loading.hidden = true;
      renderList();
    } catch (error) {
      loading.hidden = true;
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    }
  }

  init();
})();
