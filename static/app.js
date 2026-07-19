document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }

  bindFeedbackButtons();
  bindAdminQuery();
  bindApiStatus();
  bindAlertCheck();
  bindAlertCancel();
  bindHotCarousel();
  bindLoadingButtons();
  renderPriceChart();
  bindCompareCheckboxValidation();
  bindAlertTargetPriceWarning();
  bindSkinRecommendForm();
});

function bindLoadingButtons() {
  document.querySelectorAll("[data-loading-label]").forEach((button) => {
    const form = button.closest("form");
    if (!form) return;
    if (form.matches("[data-skin-recommend-form]")) return;
    form.addEventListener("submit", () => {
      if (button.disabled) return;
      button.dataset.originalLabel = button.innerHTML;
      button.innerHTML = `<span class="spinner"></span><span>${button.dataset.loadingLabel}</span>`;
      button.disabled = true;
    });
  });
}

function bindFeedbackButtons() {
  document.querySelectorAll("[data-feedback]").forEach((button) => {
    button.addEventListener("click", async () => {
      const payload = {
        target_type: button.dataset.targetType,
        target_id: Number(button.dataset.targetId),
        is_helpful: button.dataset.helpful === "true",
      };
      let ok = false;
      try {
        const response = await fetch("/api/feedback", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        ok = response.ok;
      } catch (error) {
        ok = false;
      }
      button.textContent = ok ? "기록됨" : "실패";
      button.classList.add(ok ? "recorded" : "record-failed");
      button.disabled = true;
    });
  });
}

function bindAdminQuery() {
  const form = document.querySelector("[data-admin-query]");
  if (!form) return;
  const result = document.querySelector("[data-query-result]");
  const button = form.querySelector("button[type=submit]");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = new FormData(form).get("question");
    result.textContent = "질의 실행 중...";
    if (button) button.disabled = true;
    try {
      const response = await fetch("/api/admin/query", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({question}),
      });
      const data = await response.json();
      result.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      result.textContent = "질의 실행에 실패했습니다. 잠시 후 다시 시도하세요.";
    } finally {
      if (button) button.disabled = false;
    }
  });
}

function bindApiStatus() {
  const button = document.querySelector("[data-api-status]");
  if (!button) return;
  const result = document.querySelector("[data-api-status-result]");
  button.addEventListener("click", async () => {
    result.textContent = "확인 중...";
    button.disabled = true;
    try {
      const response = await fetch("/api/admin/api-status");
      const data = await response.json();
      result.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      result.textContent = "연결 확인에 실패했습니다.";
    } finally {
      button.disabled = false;
    }
  });
}

function bindAlertCheck() {
  const form = document.querySelector("[data-alert-check]");
  if (!form) return;
  const button = form.querySelector("button[type=submit]");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (button) button.disabled = true;
    try {
      const response = await fetch("/api/alerts/check", {method: "POST"});
      const data = await response.json();
      window.alert(`${data.count}개 알림이 발동됐습니다.`);
      window.location.reload();
    } catch (error) {
      window.alert("알림 점검에 실패했습니다. 잠시 후 다시 시도하세요.");
      if (button) button.disabled = false;
    }
  });
}

function bindAlertCancel() {
  document.querySelectorAll("[data-alert-cancel]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (button.disabled) return;
      const alertId = button.dataset.alertId;
      const row = button.closest("[data-alert-row]");
      button.disabled = true;
      const originalLabel = button.textContent;
      button.textContent = "취소 중...";
      try {
        const response = await fetch(`/api/alerts/${alertId}/cancel`, {method: "POST"});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "취소에 실패했습니다.");
        const status = row && row.querySelector("[data-alert-status]");
        if (status) status.textContent = "취소됨";
        button.textContent = "취소됨";
      } catch (error) {
        button.textContent = originalLabel;
        button.disabled = false;
        window.alert(error.message || "알림 취소에 실패했습니다. 잠시 후 다시 시도하세요.");
      }
    });
  });
}

function bindHotCarousel() {
  const root = document.querySelector("[data-hot-carousel]");
  if (!root) return;
  const cards = Array.from(root.querySelectorAll("[data-hot-card]"));
  const dots = Array.from(root.querySelectorAll("[data-hot-dot]"));
  if (cards.length <= 1) return;

  let index = 0;
  let timer = null;
  const show = (nextIndex) => {
    index = (nextIndex + cards.length) % cards.length;
    cards.forEach((card, cardIndex) => card.classList.toggle("active", cardIndex === index));
    dots.forEach((dot, dotIndex) => dot.classList.toggle("active", dotIndex === index));
  };
  const schedule = () => {
    if (timer) window.clearInterval(timer);
    timer = window.setInterval(() => show(index + 1), 4500);
  };

  const prev = root.querySelector("[data-hot-prev]");
  const next = root.querySelector("[data-hot-next]");
  if (prev) prev.addEventListener("click", () => { show(index - 1); schedule(); });
  if (next) next.addEventListener("click", () => { show(index + 1); schedule(); });
  dots.forEach((dot) => {
    dot.addEventListener("click", () => {
      show(Number(dot.dataset.hotDot));
      schedule();
    });
  });
  schedule();
}

function renderPriceChart() {
  const canvas = document.getElementById("priceChart");
  if (!canvas || !window.Chart) return;
  const history = JSON.parse(canvas.dataset.history || "[]");
  const labels = history.map((row) => row.collected_at.slice(5, 10));
  const prices = history.map((row) => row.price);
  new window.Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "가격",
          data: prices,
          borderColor: "#00a36c",
          backgroundColor: "rgba(0, 163, 108, 0.12)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {display: false},
      },
      scales: {
        y: {
          ticks: {
            callback: (value) => `${Number(value).toLocaleString()}원`,
          },
        },
      },
    },
  });
}

function bindCompareCheckboxValidation() {
  const forms = document.querySelectorAll("form[action*='compare']");
  forms.forEach((form) => {
    const checkboxes = form.querySelectorAll("input[type='checkbox'][name='product_ids']");
    const submitBtn = form.querySelector("button[type='submit']");
    if (!checkboxes.length || !submitBtn) return;

    const floatBar = form.id
      ? document.querySelector(`[data-compare-float][data-compare-float-for="${form.id}"]`)
      : null;
    const floatCount = floatBar && floatBar.querySelector("[data-compare-float-count]");
    const floatSubmit = floatBar && floatBar.querySelector("[data-compare-float-submit]");

    const updateSubmitButton = () => {
      const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
      const enough = checkedCount >= 2;
      submitBtn.disabled = !enough;
      const btnText = submitBtn.querySelector("span");
      if (btnText) btnText.textContent = enough ? "AI 비교 리포트 생성" : "비교할 상품을 2개 이상 선택하세요";

      if (floatBar) {
        floatBar.classList.toggle("is-visible", checkedCount > 0);
        if (floatCount) floatCount.textContent = `${checkedCount}개 선택됨`;
        if (floatSubmit) floatSubmit.disabled = !enough;
      }
    };

    checkboxes.forEach(cb => {
      cb.addEventListener("change", updateSubmitButton);
    });

    if (floatSubmit) {
      floatSubmit.addEventListener("click", () => {
        if (floatSubmit.disabled) return;
        if (form.requestSubmit) form.requestSubmit(submitBtn);
        else submitBtn.click();
      });
    }

    updateSubmitButton(); // Initial check
  });
}

function bindAlertTargetPriceWarning() {
  const input = document.getElementById("target_price");
  const warning = document.getElementById("price-warning");
  if (!input || !warning) return;
  const currentPrice = Number(input.value);

  const checkPrice = () => {
    const val = Number(input.value);
    if (val >= currentPrice) {
      warning.style.display = "block";
    } else {
      warning.style.display = "none";
    }
  };

  input.addEventListener("input", checkPrice);
  checkPrice();
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function bindSkinRecommendForm() {
  const form = document.querySelector("[data-skin-recommend-form]");
  const results = document.querySelector("[data-skin-recommend-results]");
  const message = document.querySelector("[data-skin-recommend-message]");
  const disclaimer = document.querySelector("[data-skin-recommend-disclaimer]");
  const conditionInputs = Array.from(form?.querySelectorAll('input[name="skin_conditions"]') || []);
  const conditionSummary = form?.querySelector("[data-skin-condition-summary]");
  const conditionReset = form?.querySelector("[data-skin-condition-reset]");
  const submitButton = form?.querySelector('button[type="submit"]');
  if (!form || !results || !message) return;

  const updateConditionState = () => {
    const selected = conditionInputs.filter((input) => input.checked);
    const selectedLabels = selected.map((input) => input.closest("label")?.innerText.trim() || input.value);
    conditionInputs.forEach((input) => {
      input.disabled = selected.length >= 5 && !input.checked;
    });
    if (conditionSummary) {
      conditionSummary.textContent = selected.length
        ? `${selected.length}/5 선택 · ${selectedLabels.join(", ")}`
        : "선택한 피부 고민이 없습니다.";
    }
    if (conditionReset) conditionReset.disabled = selected.length === 0;
  };

  conditionInputs.forEach((input) => input.addEventListener("change", updateConditionState));
  conditionReset?.addEventListener("click", () => {
    conditionInputs.forEach((input) => {
      input.checked = false;
      input.disabled = false;
    });
    message.textContent = "";
    updateConditionState();
    conditionInputs[0]?.focus();
  });
  updateConditionState();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const skinType = form.querySelector("#skin_type").value;
    const hairType = form.querySelector("#hair_type").value;
    const skinConditions = Array.from(
      form.querySelectorAll('input[name="skin_conditions"]:checked')
    ).map((input) => input.value);

    if (!skinType && !hairType && skinConditions.length === 0) {
      message.textContent = "피부 타입, 모발 타입, 피부 고민 중 하나 이상을 선택해주세요.";
      results.innerHTML = "";
      if (disclaimer) disclaimer.hidden = true;
      return;
    }
    if (skinConditions.length > 5) {
      message.textContent = "피부 고민은 최대 5개까지 선택할 수 있습니다.";
      return;
    }

    const params = new URLSearchParams();
    if (skinType) params.set("skin_type", skinType);
    if (hairType) params.set("hair_type", hairType);
    skinConditions.forEach((condition) => params.append("skin_conditions", condition));
    params.set("limit", "12");

    message.textContent = "추천 상품을 찾는 중입니다...";
    results.innerHTML = "";
    if (disclaimer) disclaimer.hidden = true;
    const originalButtonHtml = submitButton?.innerHTML;
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.innerHTML = '<span class="spinner"></span><span>추천 찾는 중...</span>';
    }

    try {
      const response = await fetch(`/api/recommend?${params.toString()}`);
      const data = await response.json();

      if (!response.ok) {
        message.textContent = data.error || "추천을 불러오지 못했습니다.";
        return;
      }

      const items = data.recommendations || [];
      if (items.length === 0) {
        message.textContent = "조건에 맞는 추천 상품을 찾지 못했습니다.";
        if (disclaimer) disclaimer.hidden = false;
        return;
      }

      if (disclaimer) disclaimer.hidden = false;
      message.textContent = `${items.length}개의 맞춤 추천 상품을 찾았습니다.`;
      results.innerHTML = items
        .map((product) => {
          const price = product.latest_price
            ? `${Number(product.latest_price).toLocaleString()}원`
            : "가격 정보 없음";
          const reasons = (product.recommend_reasons || []).map(escapeHtml).join(" · ");
          const image = product.promo_image || product.image_url;
          const visual = image
            ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(product.name)}">`
            : `<span>${escapeHtml((product.name || "?")[0])}</span>`;
          return `
            <a class="product-card" href="/products/${product.id}">
              <span class="product-visual">${visual}</span>
              <span class="product-body">
                <strong>${escapeHtml(product.name)}</strong>
                <small>${escapeHtml(product.brand || product.maker || "브랜드 확인 불가")}</small>
                ${reasons ? `<small class="description-line">${reasons}</small>` : ""}
                <b>${price}</b>
              </span>
            </a>
          `;
        })
        .join("");

      if (window.lucide) {
        window.lucide.createIcons();
      }
    } catch (error) {
      message.textContent = "추천을 불러오는 중 오류가 발생했습니다.";
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.innerHTML = originalButtonHtml;
      }
      if (window.lucide) window.lucide.createIcons();
    }
  });
}
