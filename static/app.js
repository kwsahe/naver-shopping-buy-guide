document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }

  bindFeedbackButtons();
  bindAdminQuery();
  bindApiStatus();
  bindAlertCheck();
  bindHotCarousel();
  renderPriceChart();
});

function bindFeedbackButtons() {
  document.querySelectorAll("[data-feedback]").forEach((button) => {
    button.addEventListener("click", async () => {
      const payload = {
        target_type: button.dataset.targetType,
        target_id: Number(button.dataset.targetId),
        is_helpful: button.dataset.helpful === "true",
      };
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      button.textContent = response.ok ? "기록됨" : "실패";
      button.disabled = true;
    });
  });
}

function bindAdminQuery() {
  const form = document.querySelector("[data-admin-query]");
  if (!form) return;
  const result = document.querySelector("[data-query-result]");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = new FormData(form).get("question");
    const response = await fetch("/api/admin/query", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question}),
    });
    const data = await response.json();
    result.textContent = JSON.stringify(data, null, 2);
  });
}

function bindApiStatus() {
  const button = document.querySelector("[data-api-status]");
  if (!button) return;
  const result = document.querySelector("[data-api-status-result]");
  button.addEventListener("click", async () => {
    const response = await fetch("/api/admin/api-status");
    const data = await response.json();
    result.textContent = JSON.stringify(data, null, 2);
  });
}

function bindAlertCheck() {
  const form = document.querySelector("[data-alert-check]");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const response = await fetch("/api/alerts/check", {method: "POST"});
    const data = await response.json();
    window.alert(`${data.count}개 알림이 발동됐습니다.`);
    window.location.reload();
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
