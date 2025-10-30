const API_URL = "/api/v1/qr";   // единый эндпойнт
const SEND_TYPE = true;         // отправлять явный type

// --- DOM (основные элементы) ---
const tabs = document.querySelectorAll(".tab");
const formFields = document.getElementById("formFields");
const qrResult = document.getElementById("qrResult");
const generateBtn = document.getElementById("generateBtn");
const downloadBtn = document.getElementById("downloadBtn");

// Цвета (пикеры/превью)
const fillColor   = document.getElementById("fillColor");
const finderColor = document.getElementById("finderColor");
const bgColor     = document.getElementById("bgColor");

const fillPreview   = document.getElementById("fillPreview");
const finderPreview = document.getElementById("finderPreview");
const bgPreview     = document.getElementById("bgPreview");

// Селекты пресетов (могут отсутствовать в твоей вёрстке — это ок)
const fillPreset   = document.getElementById("fillPreset");
const finderPreset = document.getElementById("finderPreset");
const bgPreset     = document.getElementById("bgPreset");

// Блок «Фирменные цвета» (старый вариант с радиокнопками и свайчами)
const brandTargetRadios = document.querySelectorAll('input[type="radio"][data-target], input[name="brandTarget"]');
const swatches          = document.querySelectorAll('.swatches .swatch[data-hex]');

// Логотип
const logoInput   = document.getElementById("logoInput");
const logoPreview = document.getElementById("logoPreview");
const logoClearBtn = document.getElementById("logoClearBtn");

// --- Тип формы (вкладки) ---
let currentType = "url";

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

// ================== УТИЛИТЫ ==================
const getVal = (id) => document.getElementById(id)?.value?.trim() || "";
const setError = (el) => (el.style.borderColor = "#e74c3c");
const clearError = (el) => (el.style.borderColor = "");

function hexNorm(v) {
  const s = String(v || "").trim();
  const h = s.startsWith("#") ? s.toUpperCase() : ("#" + s).toUpperCase();
  // валидация #RRGGBB
  return /^#[0-9A-F]{6}$/i.test(h) ? h : "#000000";
}
function isLogoSelected() {
  return !!(logoInput && logoInput.files && logoInput.files.length > 0);
}
function buildQuery(params) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v != null) sp.set(k, v);
  });
  return sp.toString();
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
  phone: ["data"],      // поле id="data", на бэк уйдёт как number
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

// ================== ПРЕСЕТЫ БРЕНДБУКА (для селектов) ==================
const BRAND_PRESETS = [
  { hex: "#009639", label: "Основной зелёный" },
  { hex: "#EAAA00", label: "Основной жёлтый" },
  { hex: "#9BBD1E", label: "Светло-зелёный" },
  { hex: "#ED6E1C", label: "Оранжевый" },
  { hex: "#0067B2", label: "Синий" },
  { hex: "#FFFFFF", label: "Белый" },
  { hex: "#0B6C31", label: "Тёмно-зелёный" },
  { hex: "#00375F", label: "Глубокий синий" },
  { hex: "#53565A", label: "Серый 1" },
  { hex: "#E30613", label: "Красный" },
];

function matchPreset(hex) {
  const H = hexNorm(hex);
  const found = BRAND_PRESETS.find(p => p.hex === H);
  return found ? found.hex : "__custom__";
}

// синхронизация: селект -> пикер/превью (если селекты присутствуют)
function syncPresetToPicker(target) {
  const select  = target === "fill" ? fillPreset : target === "finder" ? finderPreset : bgPreset;
  const picker  = target === "fill" ? fillColor  : target === "finder" ? finderColor  : bgColor;
  const preview = target === "fill" ? fillPreview : target === "finder" ? finderPreview : bgPreview;
  if (!select || !picker || !preview) return;

  const val = select.value;
  if (val && val !== "__custom__") {
    picker.value = hexNorm(val);
    preview.style.background = picker.value;
  }
}

// синхронизация: пикер -> селект/превью
function syncPickerToPreset(target) {
  const select  = target === "fill" ? fillPreset : target === "finder" ? finderPreset : bgPreset;
  const picker  = target === "fill" ? fillColor  : target === "finder" ? finderColor  : bgColor;
  const preview = target === "fill" ? fillPreview : target === "finder" ? finderPreview : bgPreview;
  if (!picker || !preview) return;

  const H = hexNorm(picker.value);
  preview.style.background = H;
  if (select) {
    const matched = matchPreset(H);
    const opt = Array.from(select.options).find(o => o.value === matched);
    select.value = opt ? matched : "__custom__";
  }
}

// helper: установить цвет в нужную цель (fill/finder/bg) и синхронизировать всё
function setColorForTarget(target, hex) {
  const picker  = target === "fill" ? fillColor  : target === "finder" ? finderColor  : bgColor;
  if (!picker) return;
  picker.value = hexNorm(hex);
  syncPickerToPreset(target);
}

// Инициализация превью
["fill", "finder", "bg"].forEach((t) => syncPickerToPreset(t));

// Слушатели селектов (если они есть)
fillPreset?.addEventListener("change", () => syncPresetToPicker("fill"));
finderPreset?.addEventListener("change", () => syncPresetToPicker("finder"));
bgPreset?.addEventListener("change", () => syncPresetToPicker("bg"));

// Слушатели пикеров
fillColor?.addEventListener("input", () => syncPickerToPreset("fill"));
finderColor?.addEventListener("input", () => syncPickerToPreset("finder"));
bgColor?.addEventListener("input", () => syncPickerToPreset("bg"));

// Определяем выбранную цель (QR/Ключи/Фон) из радиокнопок старого блока
function getSelectedBrandTarget() {
  // поддержка обоих вариантов: data-target="fill|finder|bg" или value="fill|finder|bg"
  const checked = Array.from(brandTargetRadios).find(r => r.checked);
  if (!checked) return "fill";
  return checked.dataset.target || checked.value || "fill";
}
// Клик по свайчу — применяем к выбранной цели
swatches.forEach(btn => {
  btn.addEventListener("click", () => {
    const hex = btn.dataset.hex;
    if (!hex) return;
    const target = getSelectedBrandTarget(); // fill/finder/bg
    setColorForTarget(target, hex);
  });
});

// ================== ЛОГОТИП: ПРЕДПРОСМОТР / ОЧИСТКА ==================
if (logoInput) {
  logoInput.addEventListener("change", () => {
    if (!logoInput.files || logoInput.files.length === 0) {
      logoPreview && (logoPreview.innerHTML = `<span class="placeholder">Превью</span>`);
      return;
    }
    const file = logoInput.files[0];
    if (file.type !== "image/png") {
      qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Логотип должен быть PNG (image/png)</p>`;
      logoInput.value = "";
      logoPreview && (logoPreview.innerHTML = `<span class="placeholder">Превью</span>`);
      return;
    }
    if (file.size > 500 * 1024) {
      qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Размер логотипа должен быть ≤ 500 KB</p>`;
      logoInput.value = "";
      logoPreview && (logoPreview.innerHTML = `<span class="placeholder">Превью</span>`);
      return;
    }

    // мини-превью
    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = new Image();
      img.onload = () => {
        if (!logoPreview) return;
        logoPreview.innerHTML = "";
        img.style.maxWidth = "96px";
        img.style.maxHeight = "96px";
        img.style.borderRadius = "12px";
        img.style.boxShadow = "0 1px 6px rgba(0,0,0,0.12)";
        logoPreview.appendChild(img);
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
  });
}

logoClearBtn?.addEventListener("click", () => {
  if (logoInput) logoInput.value = "";
  if (logoPreview) logoPreview.innerHTML = `<span class="placeholder">Превью</span>`;
  // Следующая генерация пойдёт по GET
});

// ================== СБОР ПАРАМЕТРОВ ==================
function collectParams(type) {
  const params = {
    fill:   hexNorm(fillColor?.value   || "#000000"),
    finder: hexNorm(finderColor?.value || "#000000"),
    bg:     hexNorm(bgColor?.value     || "#FFFFFF"),
    t: Date.now().toString(), // бьём кеш браузера для превью
  };

  if (SEND_TYPE) params.type = type;

  switch (type) {
    case "url":
      params.data = getVal("data");
      break;
    case "phone":
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

// ================== ГЕНЕРАЦИЯ ==================
generateBtn.addEventListener("click", async () => {
  qrResult.innerHTML = `<p class="placeholder">⏳ Генерация QR-кода...</p>`;

  if (!validate(currentType)) {
    qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Заполните обязательные поля!</p>`;
    return;
  }

  const params = collectParams(currentType);
  const defaultName = `qr_${currentType}.png`;

  // Если выбран логотип — POST multipart
  if (isLogoSelected()) {
    const fd = new FormData();
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
      const resp = await fetch(API_URL, { method: "POST", body: fd });
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
    } catch {
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
