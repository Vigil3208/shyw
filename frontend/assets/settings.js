/* 界面五 · 设置页 */
(() => {
  /* ---------- 面板切换 ---------- */
  const menu = document.querySelector("#st-menu");
  const panels = {
    tone: document.querySelector("#panel-tone"),
    lock: document.querySelector("#panel-lock"),
    engine: document.querySelector("#panel-engine"),
    about: document.querySelector("#panel-about"),
  };

  menu.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-panel]");
    if (!button) return;
    menu.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    Object.entries(panels).forEach(([key, panel]) => {
      panel.hidden = key !== button.dataset.panel;
    });
  });

  /* ---------- 平台调性 ---------- */
  const TONE_PREVIEWS = {
    xiaohongshu: {
      克制: "这座宋代古镇保留着完整的街巷格局，适合安排半日慢游。",
      适中: "900 岁的古镇太适合周末放空了，老街随便拍都很出片。",
      放飞: "姐妹们这个宝藏古镇我求求你们去！900 岁的老街，转角就是神仙机位📍",
    },
    video: {
      克制: "青溪古镇始建于宋代，现存老街约八百米，保存较为完整。",
      适中: "别再去人挤人的网红古镇了，这座宋代老街更有味道。",
      放飞: "别再去人挤人的网红古镇了！这条宋代老街，本地人都未必知道！",
    },
    moments: {
      克制: "一桥一塔一老街，宋代遗风，至今犹存。",
      适中: "一桥一塔一老街，宋代的风吹到了今天。",
      放飞: "宋代的风吹到了今天🍃 一桥一塔一老街，周末就出发！",
    },
  };

  const tone = Wenan.getTone();

  document.querySelectorAll(".st-group[data-platform]").forEach((group) => {
    const platform = group.dataset.platform;
    const slider = group.querySelector(".tone-range");
    const value = group.querySelector(".tone-value");
    const preview = group.querySelector(".tone-preview");

    function sync(v) {
      const label = Wenan.toneLabel(v);
      value.textContent = `${label} · ${v}`;
      preview.textContent = TONE_PREVIEWS[platform][label];
    }

    slider.value = tone[platform];
    sync(tone[platform]);

    slider.addEventListener("input", () => {
      const v = Number(slider.value);
      tone[platform] = v;
      sync(v);
      Wenan.setTone(tone);
    });
  });

  /* ---------- 事实锁定 · 高亮开关 ---------- */
  const highlightSwitch = document.querySelector("#sw-highlight");
  highlightSwitch.checked = localStorage.getItem(Wenan.LS.factHighlight) !== "off";
  highlightSwitch.addEventListener("change", () => {
    localStorage.setItem(Wenan.LS.factHighlight, highlightSwitch.checked ? "on" : "off");
    Wenan.toast(highlightSwitch.checked ? "已开启〖〗事实高亮" : "已关闭〖〗事实高亮");
  });

  /* ---------- 模型引擎与连接 ---------- */
  const apiBaseInput = document.querySelector("#api-base");
  const connStatus = document.querySelector("#conn-status");
  const connDot = connStatus.querySelector(".health-dot");
  const connText = connStatus.querySelector("span:last-child");
  const engineOpenai = document.querySelector("#engine-openai");
  const engineLocal = document.querySelector("#engine-local");
  const docsLink = document.querySelector("#about-docs");

  apiBaseInput.value = localStorage.getItem(Wenan.LS.apiBase) || "";

  function setConn(color, text) {
    connDot.style.background = color;
    connText.textContent = text;
  }

  async function refreshConnection(notify = false) {
    setConn("#c9a227", "正在测试连接…");
    try {
      const health = await Wenan.api.health();
      const isOpenai = health.model_mode === "openai";
      setConn("#3d8a5a", `连接正常 · ${isOpenai ? "在线大模型" : "本地确定性引擎"} · 数据库 ${health.database}`);
      engineOpenai.classList.toggle("live", isOpenai);
      engineLocal.classList.toggle("live", !isOpenai);
      engineOpenai.querySelector(".engine-live-tag").hidden = !isOpenai;
      engineLocal.querySelector(".engine-live-tag").hidden = isOpenai;
      if (notify) Wenan.toast("连接正常");
    } catch (error) {
      setConn("#b3402a", "连接失败 —— 请确认后端已启动、地址与跨域配置正确");
      engineOpenai.classList.remove("live");
      engineLocal.classList.remove("live");
      engineOpenai.querySelector(".engine-live-tag").hidden = true;
      engineLocal.querySelector(".engine-live-tag").hidden = true;
      if (notify) Wenan.toast("连接失败");
    }
    const base = (localStorage.getItem(Wenan.LS.apiBase) || "").replace(/\/+$/, "");
    docsLink.href = `${base}/docs`;
  }

  document.querySelector("#api-save").addEventListener("click", () => {
    localStorage.setItem(Wenan.LS.apiBase, apiBaseInput.value.trim());
    Wenan.toast("API 地址已保存");
    refreshConnection();
  });

  document.querySelector("#conn-test").addEventListener("click", () => refreshConnection(true));

  Wenan.mountNav("settings");
  refreshConnection();
})();
