/* 界面三 · 事实校验报告页（黛蓝深色） */
(() => {
  const statusRow = document.querySelector("#rv-status");
  const factRows = document.querySelector("#rv-fact-rows");
  const platformsHost = document.querySelector("#rv-platforms");
  const checksGrid = document.querySelector("#rv-checks");
  const approveBtn = document.querySelector("#rv-approve");
  const progressText = document.querySelector("#rv-progress");
  const approvedBox = document.querySelector("#rv-approved");
  const loading = document.querySelector("#rv-loading");
  const errorBox = document.querySelector("#rv-error");
  const backlink = document.querySelector("#rv-backlink");
  const backResult = document.querySelector("#rv-back-result");

  /* 明细状态 → 图标与语义（consistent 一致 / unmarked 未标注 / not_used 未采用） */
  const DETAIL_META = {
    consistent: { icon: "✓", cls: "ok-ico yes", label: "一致" },
    unmarked: { icon: "!", cls: "ok-ico no", label: "未标注" },
    not_used: { icon: "✗", cls: "ok-ico no", label: "未采用" },
  };

  function detailMeta(status) {
    return DETAIL_META[status] ?? { icon: "?", cls: "ok-ico no", label: status || "未知" };
  }

  function renderStatus(session) {
    statusRow.replaceChildren();
    const facts = session.facts ?? [];
    if (session.validation) {
      const passed = session.validation.status === "passed";
      statusRow.append(Wenan.el("span", "rv-badge",
        passed ? "校验通过 · 零硬错误" : "存在待复核项 · 请逐条核对"));
      const platforms = Object.values(session.validation.platforms ?? {});
      if (platforms.length) {
        const avg = platforms.reduce((sum, p) => sum + (p.fact_coverage ?? 0), 0) / platforms.length;
        statusRow.append(Wenan.el("span", "rv-badge", `平均事实覆盖率 ${(avg * 100).toFixed(0)}%`));
        const usable = platforms.filter((p) => p.direct_usable).length;
        statusRow.append(Wenan.el("span", "rv-badge", `${usable}/3 端即拿即用`));
      }
    } else {
      statusRow.append(Wenan.el("span", "rv-badge", Wenan.statusNames[session.status] ?? session.status));
    }
    statusRow.append(Wenan.el("span", "rv-badge", `共 ${facts.length} 个事实点`));
  }

  function renderFacts(session) {
    factRows.replaceChildren();
    const facts = session.facts ?? [];
    if (!facts.length) {
      const tr = Wenan.el("tr");
      const td = Wenan.el("td", "", "本会话未抽取到事实点。");
      td.colSpan = 4;
      td.style.textAlign = "center";
      td.style.color = "rgba(238,242,243,.5)";
      tr.append(td);
      factRows.append(tr);
      return;
    }
    facts.forEach((fact) => {
      const tr = Wenan.el("tr");
      const type = Wenan.el("td");
      type.append(Wenan.el("span", "fact-type", Wenan.factTypeNames[fact.type] ?? fact.type));
      tr.append(type);
      tr.append(Wenan.el("td", "fact-src", fact.source_text));
      tr.append(Wenan.el("td", "fact-norm num", fact.normalized_value));
      const crit = Wenan.el("td");
      crit.append(Wenan.el("span", "fact-crit", fact.criticality === "critical" ? "关键" : "一般"));
      tr.append(crit);
      factRows.append(tr);
    });
  }

  function renderPlatforms(session) {
    platformsHost.replaceChildren();
    const platforms = session.validation?.platforms ?? {};
    const entries = Wenan.platformOrder
      .filter((p) => platforms[p])
      .map((p) => [p, platforms[p]]);

    if (!entries.length) {
      platformsHost.append(Wenan.el("p", "rv-sec-sub", "暂无平台比对数据。"));
      return;
    }

    entries.forEach(([platform, pv]) => {
      const block = Wenan.el("div", "rv-plat");
      const logo = Wenan.platformLogos[platform];

      const head = Wenan.el("div", "rv-plat-head");
      head.append(Wenan.el("span", `plat-logo ${logo.cls}`, logo.mark));
      const titleBox = Wenan.el("div");
      titleBox.append(
        Wenan.el("h3", "", `${Wenan.platformNames[platform]} · ${logo.sub}`),
        Wenan.el("div", "en", Wenan.platformEns[platform]),
      );
      const coverage = Wenan.el("div", "rv-coverage");
      coverage.append(
        Wenan.el("div", "cv-num", `${Math.round((pv.fact_coverage ?? 0) * 100)}%`),
        Wenan.el("div", "cv-label", "事实覆盖率"),
      );
      head.append(titleBox, coverage);

      const body = Wenan.el("div", "rv-plat-body");
      (pv.details ?? []).forEach((item) => {
        const meta = detailMeta(item.status);
        const row = Wenan.el("div", "rv-detail-row");
        row.append(Wenan.el("span", meta.cls, meta.icon));
        const detail = Wenan.el("div");
        const srcLine = Wenan.el("div");
        srcLine.append(
          Wenan.el("span", "d-src", item.source_text),
          Wenan.el("span", "d-tag", ` ${meta.label}`),
        );
        detail.append(srcLine);
        if (item.occurrence) {
          detail.append(Wenan.el("div", "d-occ", `产出表述：${item.occurrence}`));
        }
        if (item.message) {
          detail.append(Wenan.el("div", "d-occ", item.message));
        }
        row.append(detail);
        body.append(row);
      });
      (pv.issues ?? []).forEach((issue) => {
        const row = Wenan.el("div", "rv-detail-row");
        row.append(Wenan.el("span", "ok-ico no", "⚠"));
        const detail = Wenan.el("div");
        detail.append(Wenan.el("div", "d-occ", issue));
        row.append(detail);
        body.append(row);
      });
      if (!(pv.details ?? []).length && !(pv.issues ?? []).length) {
        body.append(Wenan.el("p", "rv-sec-sub", "无逐条明细。"));
      }

      block.append(head, body);
      platformsHost.append(block);
    });
  }

  /* ---------- 人工复核 ---------- */
  function renderChecks(session) {
    checksGrid.replaceChildren();
    const facts = session.facts ?? [];
    let confirmed = 0;

    function updateProgress() {
      progressText.textContent = `${confirmed} / ${facts.length} 已确认`;
      approveBtn.disabled = !(facts.length > 0 && confirmed === facts.length);
    }

    facts.forEach((fact) => {
      const label = Wenan.el("label", "rv-check");
      const input = Wenan.el("input");
      input.type = "checkbox";
      const text = Wenan.el("span");
      text.append(
        Wenan.el("span", "rc-src", fact.source_text),
        Wenan.el("span", "rc-type", Wenan.factTypeNames[fact.type] ?? fact.type),
      );
      input.addEventListener("change", () => {
        confirmed += input.checked ? 1 : -1;
        updateProgress();
      });
      label.append(input, text);
      checksGrid.append(label);
    });
    updateProgress();
  }

  approveBtn.addEventListener("click", () => {
    approvedBox.classList.add("show");
    approveBtn.disabled = true;
    approveBtn.textContent = "已复核";
    approvedBox.scrollIntoView({ behavior: "smooth", block: "center" });
    Wenan.toast("复核完成，内容可发布");
  });

  async function init() {
    Wenan.mountNav("");
    Wenan.applyFactHighlightPref();
    const sessionId = Wenan.getParam("session");
    const resultUrl = sessionId ? `result.html?session=${encodeURIComponent(sessionId)}` : "result.html";
    backlink.href = resultUrl;
    backResult.href = resultUrl;

    if (!sessionId) {
      loading.hidden = true;
      errorBox.textContent = "缺少会话参数 —— 请从生成结果页进入校验报告。";
      errorBox.hidden = false;
      return;
    }
    try {
      const session = await Wenan.api.getSession(sessionId);
      loading.hidden = true;
      renderStatus(session);
      renderFacts(session);
      renderPlatforms(session);
      renderChecks(session);
    } catch (error) {
      loading.hidden = true;
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    }
  }

  init();
})();
