/* 界面一 · 主工作台 */
(() => {
  const text = document.querySelector("#wb-text");
  const countBox = document.querySelector("#wb-count");
  const countNum = countBox.querySelector("b");
  const instructionInput = document.querySelector("#wb-instruction-input");
  const submitButton = document.querySelector("#wb-submit");
  const errorBox = document.querySelector("#wb-error");
  const overlay = document.querySelector("#gen-overlay");
  const stepLabel = document.querySelector("#gen-step");

  const SAMPLE = "青云山始建于明代，主峰海拔 860 米。景区每天 8:00 至 18:00 开放，成人票价 60 元。山顶观景台可以俯瞰古城全貌。相传明代旅行家徐霞客曾登临此山，留下「青云直上」四字摩崖石刻。山间现存清代古刹一座，占地约三千平方米，为省级重点文物保护单位。";

  const GEN_STEPS = [
    "正在抽取事实点…",
    "正在生成小红书种草文…",
    "正在生成短视频口播脚本…",
    "正在生成朋友圈海报配文…",
    "正在逐条校验事实…",
  ];

  function updateCount() {
    countNum.textContent = text.value.length.toLocaleString("en-US");
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function hideError() {
    errorBox.hidden = true;
  }

  text.addEventListener("input", updateCount);

  document.querySelector("#wb-clear").addEventListener("click", () => {
    text.value = "";
    updateCount();
    text.focus();
  });

  document.querySelector("#wb-sample").addEventListener("click", () => {
    text.value = SAMPLE;
    updateCount();
    hideError();
  });

  let stepTimer = null;

  function startSteps() {
    let index = 0;
    stepLabel.textContent = GEN_STEPS[0];
    stepTimer = setInterval(() => {
      index = (index + 1) % GEN_STEPS.length;
      stepLabel.textContent = GEN_STEPS[index];
    }, 2600);
  }

  function stopSteps() {
    clearInterval(stepTimer);
    stepTimer = null;
  }

  submitButton.addEventListener("click", async () => {
    hideError();
    const original = text.value.trim();
    if (!original) {
      showError("请先粘贴一段景区官方讲解词。");
      text.focus();
      return;
    }

    /* 设置页的语气偏好自动附加，用户补充要求紧随其后 */
    const extra = instructionInput.value.trim();
    let userInstruction = [Wenan.toneInstruction(), extra].filter(Boolean).join(" ");
    if (userInstruction.length > 1000) {
      userInstruction = userInstruction.slice(0, 1000);
    }

    submitButton.disabled = true;
    submitButton.textContent = "生成中…";
    overlay.classList.add("show");
    startSteps();

    try {
      const session = await Wenan.api.generate({
        original_text: original,
        user_instruction: userInstruction || null,
      });
      window.location.href = `result.html?session=${encodeURIComponent(session.session_id)}`;
    } catch (error) {
      overlay.classList.remove("show");
      showError(error.message);
    } finally {
      stopSteps();
      submitButton.disabled = false;
      submitButton.textContent = "一键生成 · 三端齐发 →";
    }
  });

  Wenan.mountNav("workbench");
  updateCount();
})();
