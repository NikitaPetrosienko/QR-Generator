// frontend/script.js

const API_URL = "/api/v1/qr";   // единый эндпойнт
const SEND_TYPE = true;         // отправлять явный type

// --- DOM ---
const tabs = document.querySelectorAll(".tab");
const formFields = document.getElementById("formFields");
const qrResult = document.getElementById("qrResult");
const generateBtn = document.getElementById("generateBtn");
const downloadBtn = document.getElementById("downloadBtn");

// Brand presets & logo upload
const swatchesWrap = document.getElementById("brandSwatches");
const brandTargetRadios = document.querySelectorAll('input[name="brandTarget"]');
const logoInput = document.getElementById("logoInput");
const logoPreview = document.getElementById("logoPreview");

let currentType = "url";
let currentBrandTarget = "fill"; // 'fill' | 'finder' | 'bg'

// ================== РЕНДЕР ФОРМЫ ПО ТИПУ ==================
function renderForm(type) {
  const templates = {
    url: `
      <label>Введите текст или ссылку</label>
      <textarea id="data" rows="3" placeholder="https:// или произвольный текст"></textarea>
    `,
    phone: `
      <label>Введите номер телефона</label>
      <input id="data" type="text" placeholder="+7 999 123 45 67" />
    `,
    mail: `
      <label>E-mail получателя</label>
      <input id="to" type="email" placeholder="user@nestro.ru" />
      <label>Тема письма</label>
      <input id="subject" type="text" placeholder="Тема письма" />
      <label>Текст письма</label>
      <textarea id="body" rows="3" placeholder="Введите текст письма"></textarea>
    `,
    sms: `
      <label>Номер телефона</label>
      <input id="phone" type="text" placeholder="+7 999 123 45 67" />
      <label>Текст сообщения</label>
      <textarea id="text" rows="3" placeholder="Введите сообщение"></textarea>
    `,
    vcard: `
      <label>ФИО</label>
      <input id="fn" type="text" placeholder="Иванов Иван Иванович" />
      <label>Организация</label>
      <input id="org" type="text" placeholder="Организация" />
      <label>Подразделение</label>
      <input id="dept" type="text" placeholder="Подразделение" />
      <label>Должность</label>
      <input id="title" type="text" placeholder="Должность" />
      <label>Email</label>
      <input id="email" type="email" placeholder="user@nestro.ru" />
      <label>Мобильный</label>
      <input id="mobile" type="text" placeholder="+7 999 123 45 67" />
      <label>Рабочий номер</label>
      <input id="work_short" type="text" placeholder="002-8042" />
    `,
  };
  formFields.innerHTML = templates[type];
}
renderForm(currentType);

// ================== ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК ==================
tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentType = tab.dataset.type;
    renderForm(currentType);
  });
});

// ================== ПРЕВЬЮ ЦВЕТОВ ==================
["fill", "finder", "bg"].forEach((key) => {
  const input = document.getElementById(`${key}Color`);
  const preview = document.getElementById(`${key}Preview`);
  input?.addEventListener("input", () => (preview.style.background = input.value));
});

// ================== УТИЛИТЫ ==================
const getVal = (id) => document.getElementById(id)?.value?.trim() || "";
const setError = (el) => (el.style.borderColor = "#e74c3c");
const clearError = (el) => (el.style.borderColor = "");

function getColorInputEl(target) {
  if (target === "fill")   return document.getElementById("fillColor");
  if (target === "finder") return document.getElementById("finderColor");
  return document.getElementById("bgColor");
}
function getColorPreviewEl(target) {
  if (target === "fill")   return document.getElementById("fillPreview");
  if (target === "finder") return document.getElementById("finderPreview");
  return document.getElementById("bgPreview");
}

function applyBrandColor(hex, target) {
  const input = getColorInputEl(target);
  const preview = getColorPreviewEl(target);
  if (!input || !preview) return;
  input.value = hex;
  preview.style.background = hex;
}

function buildQuery(params) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v != null) sp.set(k, v);
  });
  return sp.toString();
}

function isLogoSelected() {
  return !!(logoInput && logoInput.files && logoInput.files.length > 0);
}

function showResultImageFromUrl(url, downloadName) {
  const img = new Image();
  img.classList.remove("visible");
  img.onload = () => {
    img.classList.add("visible");
    qrResult.innerHTML = "";
    qrResult.appendChild(img);

    downloadBtn.disabled = false;
    downloadBtn.onclick = () => {
      const link = document.createElement("a");
      link.href = img.src;
      link.download = downloadName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };
  };
  img.onerror = () => {
    qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Ошибка генерации QR</p>`;
  };
  img.src = url;
}

function showResultImageFromBlob(blob, downloadName) {
  const url = URL.createObjectURL(blob);
  showResultImageFromUrl(url, downloadName);
}

// ================== ОБЯЗАТЕЛЬНЫЕ ПОЛЯ ==================
const requiredByType = {
  url: ["data"],
  phone: ["data"],      // в форме поле id="data", на бэк уйдёт как number
  mail: ["to"],
  sms: ["phone", "text"],
  vcard: ["fn"],
};

function validate(type) {
  let ok = true;
  (requiredByType[type] || []).forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      if (!getVal(id)) {
        setError(el);
        ok = false;
      } else {
        clearError(el);
      }
      el.addEventListener("input", () => clearError(el), { once: true });
    }
  });
  return ok;
}

// ================== СБОР ПАРАМЕТРОВ ==================
function collectParams(type) {
  // базовые цвета
  const params = {
    fill: getVal("fillColor") || "#000000",
    finder: getVal("finderColor") || "#000000",
    bg: getVal("bgColor") || "#FFFFFF",
    t: Date.now().toString(), // бьём кеш браузера в превью (для GET)
  };

  if (SEND_TYPE) params.type = type; // явный тип (можно выключить)

  switch (type) {
    case "url":
      params.data = getVal("data");
      break;
    case "phone":
      // в форме поле id="data", а на бэк ждём number
      params.number = getVal("data");
      break;
    case "mail":
      params.to = getVal("to");
      if (getVal("subject")) params.subject = getVal("subject");
      if (getVal("body")) params.body = getVal("body");
      break;
    case "sms":
      params.phone = getVal("phone");
      if (getVal("text")) params.text = getVal("text");
      break;
    case "vcard":
      params.fn = getVal("fn");
      ["org", "title", "dept", "email", "mobile", "work_short"].forEach((k) => {
        const v = getVal(k);
        if (v) params[k] = v;
      });
      break;
  }

  return params;
}

// ================== BRAND PRESETS ==================
brandTargetRadios.forEach((r) => {
  r.addEventListener("change", () => {
    currentBrandTarget = r.value;
  });
});

if (swatchesWrap) {
  swatchesWrap.addEventListener("click", (e) => {
    const btn = e.target.closest(".swatch");
    if (!btn) return;
    const hex = btn.getAttribute("data-hex");
    if (!hex) return;
    applyBrandColor(hex, currentBrandTarget);
  });
}

// ================== ЛОГОТИП: ПРЕДПРОСМОТР И ПРЕ-ПРОВЕРКИ ==================
if (logoInput) {
  logoInput.addEventListener("change", () => {
    if (!logoInput.files || logoInput.files.length === 0) {
      logoPreview.innerHTML = `<span class="placeholder">Превью</span>`;
      return;
    }
    const file = logoInput.files[0];
    // простые клиентские проверки (совпадают с бэком)
    if (file.type !== "image/png") {
      qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Логотип должен быть PNG (image/png)</p>`;
      logoInput.value = "";
      logoPreview.innerHTML = `<span class="placeholder">Превью</span>`;
      return;
    }
    if (file.size > 500 * 1024) {
      qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Размер логотипа должен быть ≤ 500 KB</p>`;
      logoInput.value = "";
      logoPreview.innerHTML = `<span class="placeholder">Превью</span>`;
      return;
    }

    // показать мини-превью
    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = new Image();
      img.onload = () => {
        logoPreview.innerHTML = "";
        img.style.maxWidth = "56px";
        img.style.maxHeight = "56px";
        img.style.borderRadius = "10px";
        img.style.boxShadow = "0 1px 6px rgba(0,0,0,0.12)";
        logoPreview.appendChild(img);
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
  });
}

// ================== ГЕНЕРАЦИЯ ==================
generateBtn.addEventListener("click", async () => {
  qrResult.innerHTML = `<p class="placeholder">⏳ Генерация QR-кода...</p>`;

  if (!validate(currentType)) {
    qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Заполните обязательные поля!</p>`;
    return;
  }

  const params = collectParams(currentType);
  const defaultName = `qr_${currentType}.png`;

  // Если выбран логотип — отправляем POST multipart в тот же эндпойнт
  if (isLogoSelected()) {
    const fd = new FormData();
    // базовые
    fd.set("context", "ui");
    if (SEND_TYPE) fd.set("type", currentType);
    fd.set("fill", params.fill);
    fd.set("finder", params.finder);
    fd.set("bg", params.bg);
    fd.set("filename", `qr_${currentType}`);

    // типоспецифичные
    if (currentType === "url") {
      fd.set("data", params.data || "");
    } else if (currentType === "phone") {
      fd.set("number", params.number || "");
    } else if (currentType === "mail") {
      fd.set("to", params.to || "");
      if (params.subject) fd.set("subject", params.subject);
      if (params.body) fd.set("body", params.body);
    } else if (currentType === "sms") {
      fd.set("phone", params.phone || "");
      if (params.text) fd.set("text", params.text);
    } else if (currentType === "vcard") {
      fd.set("fn", params.fn || "");
      ["org", "title", "dept", "email", "mobile", "work_short"].forEach((k) => {
        if (params[k]) fd.set(k, params[k]);
      });
    }

    // файл логотипа
    const file = logoInput.files[0];
    fd.set("logo", file, file.name);

    try {
      const resp = await fetch(API_URL, {
        method: "POST",
        body: fd,
      });
      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Ошибка ${resp.status}: ${text || "генерации QR"}</p>`;
        return;
      }
      const contentType = resp.headers.get("content-type") || "";
      if (!contentType.includes("image/png")) {
        const text = await resp.text().catch(() => "");
        qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Не PNG-ответ: ${text || contentType}</p>`;
        return;
      }
      const blob = await resp.blob();
      showResultImageFromBlob(blob, defaultName);
    } catch (e) {
      qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Сетевая ошибка при генерации</p>`;
    }
    return;
  }

  // Иначе — классический GET превью
  const url = `${API_URL}?${buildQuery({
    ...params,
    context: "ui",
    type: SEND_TYPE ? currentType : undefined,
  })}`;

  showResultImageFromUrl(url, defaultName);
});
