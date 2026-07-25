/* 界面二 · 生成结果页 */
(() => {
  const metaStrip = document.querySelector("#rs-meta");
  const tabsBar = document.querySelector("#rs-tabs");
  const outputsHost = document.querySelector("#rs-outputs");
  const loading = document.querySelector("#rs-loading");
  const errorBox = document.querySelector("#rs-error");
  const reviewLink = document.querySelector("#rs-review-link");
  const copyAllButton = document.querySelector("#rs-copy-all");

  let activeSession = null;

  /* ---------- 复制文本拼装 ---------- */
  function buildXhsText(content) {
    const title = content.titles?.[0] ?? "";
    const tags = (content.tags ?? []).join(" ");
    return [
      `【小红书 · 种草文】\n${title}`,
      content.body ?? "",
      tags,
      `封面建议：${content.cover_suggestion ?? ""}`,
    ].filter(Boolean).join("\n\n");
  }

  function buildVideoText(content) {
    const lines = [
      `【短视频 · 口播脚本】时长 ${content.duration_seconds ?? "--"} 秒 · BGM：${content.bgm_style ?? "待定"}`,
    ];
    (content.shots ?? []).forEach((shot, i) => {
      lines.push(
        ``,
        `分镜 ${String(i + 1).padStart(2, "0")} 〔${shot.time_range} · ${shot.pace}〕`,
        `画面：${shot.visual}`,
        `口播：${shot.narration}`,
        `字幕：${(shot.subtitle_keywords ?? []).join(" / ")}`,
      );
    });
    return lines.join("\n");
  }

  function buildMomentsText(content) {
    const quotes = (content.poster_quotes ?? []).map((q, i) => `金句 ${i + 1}：${q}`).join("\n");
    const grid = (content.grid ?? [])
      .map((g) => `${g.position}. ${g.content}（${g.shot_size} · ${g.composition}）`)
      .join("\n");
    const tips = Object.entries(content.pinned_tips ?? {})
      .map(([k, v]) => `${k}：${v}`)
      .join("\n");
    return [
      `【朋友圈 · 海报配文】\n${quotes}`,
      content.body ?? "",
      `九宫格拍摄方案：\n${grid}`,
      `置顶实用信息：\n${tips}`,
    ].filter(Boolean).join("\n\n");
  }

  const textBuilders = { xiaohongshu: buildXhsText, video: buildVideoText, moments: buildMomentsText };

  function buildAllText(session) {
    return Wenan.platformOrder
      .filter((p) => session.outputs[p])
      .map((p) => textBuilders[p](session.outputs[p].content))
      .join("\n\n————————————————\n\n");
  }

  /* ---------- 校验徽章 ---------- */
  function validationBadge(status) {
    const cls = status === "passed" ? "badge badge-cinnabar" : status === "failed" ? "badge badge-dai" : "badge badge-gold";
    return Wenan.el("span", cls, Wenan.validationNames[status] ?? status);
  }

  /* ---------- 平台内容区 ---------- */
  function buildXhsBody(content) {
    const frag = document.createDocumentFragment();
    const now = Wenan.el("div", "xhs-title-now", content.titles?.[0] ?? "");
    frag.append(now);

    frag.append(Wenan.el("div", "xhs-titles-label", `备选标题 · 共 ${content.titles?.length ?? 0} 个，点击切换`));
    const titles = Wenan.el("div", "xhs-titles");
    (content.titles ?? []).forEach((title, i) => {
      const chip = Wenan.el("button", `chip xhs-title-chip${i === 0 ? " active" : ""}`);
      chip.type = "button";
      chip.append(Wenan.el("span", "", title));
      chip.addEventListener("click", () => {
        now.textContent = title;
        titles.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
      });
      titles.append(chip);
    });
    frag.append(titles);

    frag.append(Wenan.el("div", "block-label", "正文"));
    const body = Wenan.el("div", "xhs-body-text");
    Wenan.appendHighlighted(body, content.body ?? "");
    frag.append(body);

    const tagRow = Wenan.el("div", "tag-row");
    (content.tags ?? []).forEach((tag) => tagRow.append(Wenan.el("span", "tag-chip", tag)));
    frag.append(tagRow);

    const cover = Wenan.el("div", "notice cover-suggest");
    cover.append(Wenan.el("b", "", "封面建议 · "), document.createTextNode(content.cover_suggestion ?? ""));
    frag.append(cover);
    return frag;
  }

  function buildVideoBody(content) {
    const frag = document.createDocumentFragment();

    const hook = Wenan.el("div", "hook-block");
    hook.append(Wenan.el("div", "hk-label", "黄金 3 秒开场"));
    const hookText = Wenan.el("p");
    Wenan.appendHighlighted(hookText, content.shots?.[0]?.narration ?? "");
    hook.append(hookText);
    frag.append(hook);

    const badges = Wenan.el("div", "video-badges");
    badges.append(
      Wenan.el("span", "badge badge-dai", `${content.duration_seconds ?? "--"} 秒成片`),
      Wenan.el("span", "badge badge-gold", `♫ BGM · ${content.bgm_style ?? "待定"}`),
      Wenan.el("span", "badge", `${content.shots?.length ?? 0} 组分镜`),
    );
    frag.append(badges);

    frag.append(Wenan.el("div", "block-label", "分镜脚本"));
    const table = Wenan.el("table", "shot-table");
    const thead = Wenan.el("thead");
    const headRow = Wenan.el("tr");
    ["时间", "画面", "口播", "节奏"].forEach((h) => headRow.append(Wenan.el("th", "", h)));
    thead.append(headRow);
    table.append(thead);

    const tbody = Wenan.el("tbody");
    (content.shots ?? []).forEach((shot) => {
      const tr = Wenan.el("tr");
      tr.append(Wenan.el("td", "st-time", shot.time_range ?? ""));
      tr.append(Wenan.el("td", "", shot.visual ?? ""));
      const narration = Wenan.el("td");
      const narrationText = Wenan.el("div");
      Wenan.appendHighlighted(narrationText, shot.narration ?? "");
      narration.append(narrationText);
      const kw = Wenan.el("div", "shot-kw");
      (shot.subtitle_keywords ?? []).forEach((k) => kw.append(Wenan.el("i", "", k)));
      if (kw.childNodes.length) narration.append(kw);
      tr.append(narration);
      tr.append(Wenan.el("td", "st-pace", shot.pace ?? ""));
      tbody.append(tr);
    });
    table.append(tbody);
    frag.append(table);
    return frag;
  }

  function buildMomentsBody(content) {
    const frag = document.createDocumentFragment();

    const quotes = Wenan.el("div", "quote-grid");
    (content.poster_quotes ?? []).forEach((quote, i) => {
      const card = Wenan.el("div", "quote-card");
      card.append(Wenan.el("i", "q-tag", `金句 ${String(i + 1).padStart(2, "0")}`));
      const p = Wenan.el("p");
      Wenan.appendHighlighted(p, quote);
      card.append(p);
      quotes.append(card);
    });
    frag.append(quotes);

    frag.append(Wenan.el("div", "block-label", "正文"));
    const body = Wenan.el("div", "moments-body-text");
    Wenan.appendHighlighted(body, content.body ?? "");
    frag.append(body);

    frag.append(Wenan.el("div", "block-label", "九宫格拍摄方案"));
    const grid = Wenan.el("div", "nine-grid");
    (content.grid ?? []).forEach((cell) => {
      const item = Wenan.el("div", "nine-cell");
      item.append(
        Wenan.el("span", "n-num", String(cell.position).padStart(2, "0")),
        Wenan.el("div", "n-content", cell.content ?? ""),
        Wenan.el("div", "n-meta", `${cell.shot_size ?? ""} · ${cell.composition ?? ""}`),
      );
      grid.append(item);
    });
    frag.append(grid);

    const tipsEntries = Object.entries(content.pinned_tips ?? {});
    if (tipsEntries.length) {
      frag.append(Wenan.el("div", "block-label", "置顶实用信息"));
      const tips = Wenan.el("div", "tips-table");
      tipsEntries.forEach(([label, value]) => {
        const row = Wenan.el("div", "tt-row");
        row.append(Wenan.el("span", "", label), Wenan.el("b", "", value));
        tips.append(row);
      });
      frag.append(tips);
    }
    return frag;
  }

  const bodyBuilders = { xiaohongshu: buildXhsBody, video: buildVideoBody, moments: buildMomentsBody };

  /* ---------- 平台卡片 ---------- */
  function buildCard(platform, output, refreshed) {
    const logo = Wenan.platformLogos[platform];
    const card = Wenan.el("article", "card output-card");
    card.dataset.platform = platform;
    card.id = `output-${platform}`;

    const head = Wenan.el("div", "output-head");
    const logoBox = Wenan.el("span", `plat-logo ${logo.cls}`, logo.mark);
    const titleBox = Wenan.el("div");
    titleBox.append(
      Wenan.el("h3", "", `${Wenan.platformNames[platform]} · ${logo.sub}`),
      Wenan.el("div", "en", Wenan.platformEns[platform]),
    );
    const spacer = Wenan.el("span", "spacer");
    head.append(
      logoBox, titleBox, spacer,
      validationBadge(output.validation_status),
      Wenan.el("span", "badge", `v${output.version}`),
    );

    const body = Wenan.el("div", "output-body");
    body.append(bodyBuilders[platform](output.content ?? {}));

    const foot = Wenan.el("div", "output-foot");
    const actions = Wenan.el("div", "output-foot-actions");
    const copyBtn = Wenan.el("button", "btn btn-cinnabar btn-sm", "复制全文");
    copyBtn.type = "button";
    copyBtn.addEventListener("click", async () => {
      const ok = await Wenan.copyText(textBuilders[platform](activeSession.outputs[platform].content));
      Wenan.toast(ok ? `${Wenan.platformNames[platform]}内容已复制` : "复制失败，请手动选择文本");
    });
    const regenToggle = Wenan.el("button", "linklike", "重新生成此平台");
    regenToggle.type = "button";
    actions.append(copyBtn, regenToggle);

    const panel = Wenan.el("div", `regen-panel${refreshed ? " open" : ""}`);
    panel.append(Wenan.el("h5", "", `继续调整${Wenan.platformNames[platform]}`));
    panel.append(Wenan.el("p", "rp-sub", "告诉模型哪里不满意，只会重新生成当前平台。"));
    const input = Wenan.el("textarea");
    input.maxLength = 1000;
    input.placeholder = "例如：标题更克制一些，正文减少 emoji，保留全部事实信息";
    const regenActions = Wenan.el("div", "regen-actions");
    const status = Wenan.el("span", `regen-status${refreshed ? " ok" : ""}`,
      refreshed ? `已生成新版本 v${output.version}，上一版仍保留在后台。` : "将基于当前版本继续修改");
    const sendBtn = Wenan.el("button", "btn btn-primary btn-sm", "发送并重新生成");
    sendBtn.type = "button";
    regenActions.append(status, sendBtn);
    panel.append(input, regenActions);

    regenToggle.addEventListener("click", () => panel.classList.toggle("open"));
    sendBtn.addEventListener("click", async () => {
      const instruction = input.value.trim();
      if (!instruction) {
        status.className = "regen-status bad";
        status.textContent = "请先填写修改要求。";
        return;
      }
      input.disabled = true;
      sendBtn.disabled = true;
      sendBtn.textContent = "重新生成中…";
      status.className = "regen-status";
      status.textContent = "正在读取当前版本与会话事实…";
      try {
        const session = await Wenan.api.regenerate(activeSession.session_id, platform, instruction);
        render(session, platform);
        Wenan.toast(`${Wenan.platformNames[platform]}已生成新版本`);
      } catch (error) {
        input.disabled = false;
        sendBtn.disabled = false;
        sendBtn.textContent = "发送并重新生成";
        status.className = "regen-status bad";
        status.textContent = error.message;
      }
    });

    foot.append(actions, panel);
    card.append(head, body, foot);
    return card;
  }

  /* ---------- 元信息 ---------- */
  function renderMeta(session) {
    const items = [
      ["会话 SESSION", session.session_id.slice(0, 8)],
      ["引擎 MODEL", session.model_name || "—"],
      ["提示词版本", session.prompt_version || "—"],
      ["创建时间", Wenan.fmtTime(session.created_at)],
    ];
    if (session.validation) {
      const usable = Object.values(session.validation.platforms ?? {}).filter((p) => p.direct_usable).length;
      items.push(["总体校验", `${Wenan.validationNames[session.validation.status] ?? session.validation.status} · ${usable}/3 端即拿即用`]);
    } else {
      items.push(["状态", Wenan.statusNames[session.status] ?? session.status]);
    }
    metaStrip.replaceChildren(...items.map(([k, v]) => {
      const cell = Wenan.el("div");
      cell.append(Wenan.el("div", "t", k), Wenan.el("div", "v", v));
      return cell;
    }));
    metaStrip.hidden = false;
  }

  /* ---------- 平台 tabs ---------- */
  function renderTabs(session) {
    const platforms = Wenan.platformOrder.filter((p) => session.outputs[p]);
    tabsBar.replaceChildren();
    platforms.forEach((p) => {
      const chip = Wenan.el("button", "chip", `${Wenan.platformNames[p]} · ${Wenan.platformLogos[p].sub}`);
      chip.type = "button";
      chip.addEventListener("click", () => {
        tabsBar.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        const card = document.querySelector(`#output-${p}`);
        if (card) {
          card.scrollIntoView({ behavior: "smooth", block: "start" });
          card.classList.remove("flash");
          requestAnimationFrame(() => card.classList.add("flash"));
        }
      });
      tabsBar.append(chip);
    });
    tabsBar.hidden = platforms.length === 0;
  }

  /* ---------- 整体渲染 ---------- */
  function render(session, refreshedPlatform = null) {
    activeSession = session;
    reviewLink.href = `review.html?session=${encodeURIComponent(session.session_id)}`;
    renderMeta(session);
    renderTabs(session);
    outputsHost.replaceChildren();
    Wenan.platformOrder
      .filter((p) => session.outputs[p])
      .forEach((p) => outputsHost.append(buildCard(p, session.outputs[p], refreshedPlatform === p)));
    if (refreshedPlatform) {
      requestAnimationFrame(() => {
        const card = document.querySelector(`#output-${refreshedPlatform}`);
        card?.scrollIntoView({ behavior: "smooth", block: "start" });
        card?.classList.add("flash");
      });
    }
  }

  copyAllButton.addEventListener("click", async () => {
    if (!activeSession) return;
    const ok = await Wenan.copyText(buildAllText(activeSession));
    Wenan.toast(ok ? "三端内容已全部复制" : "复制失败，请手动选择文本");
  });

  /* ---------- 初始化 ---------- */
  async function init() {
    Wenan.mountNav("");
    Wenan.applyFactHighlightPref();
    const sessionId = Wenan.getParam("session");
    if (!sessionId) {
      loading.hidden = true;
      errorBox.textContent = "缺少会话参数 —— 请从工作台发起生成，或从历史记录打开一条会话。";
      errorBox.hidden = false;
      return;
    }
    try {
      const session = await Wenan.api.getSession(sessionId);
      loading.hidden = true;
      render(session);
    } catch (error) {
      loading.hidden = true;
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    }
  }

  init();
})();
