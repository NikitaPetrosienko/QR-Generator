const API_URL = "/api/v1/qr";   // единый эндпойнт
const SEND_TYPE = true;         

// --- DOM ---
const tabs = document.querySelectorAll(".tab");
const formFields = document.getElementById("formFields");
const qrResult = document.getElementById("qrResult");
const generateBtn = document.getElementById("generateBtn");
const downloadBtn = document.getElementById("downloadBtn");

let currentType = "url";

// шаблоны форм 
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

// переключение вкладок
tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentType = tab.dataset.type;
    renderForm(currentType);
  });
});

// превью цветов
["fill", "finder", "bg"].forEach((key) => {
  const input = document.getElementById(`${key}Color`);
  const preview = document.getElementById(`${key}Preview`);
  input?.addEventListener("input", () => (preview.style.background = input.value));
});

// --- utils
const getVal = (id) => document.getElementById(id)?.value?.trim() || "";
const setError = (el) => (el.style.borderColor = "#e74c3c");
const clearError = (el) => (el.style.borderColor = "");

// обязательные поля 
const requiredByType = {
  url: ["data"],
  phone: ["data"],      // вводим в поле id="data", на бэк уйдёт как number
  mail: ["to"],
  sms: ["phone", "text"],
  vcard: ["fn"],
};

// собираем параметры под конкретный тип
function collectParams(type) {
  // базовые цвета
  const params = {
    fill: getVal("fillColor") || "#000000",
    finder: getVal("finderColor") || "#000000",
    bg: getVal("bgColor") || "#FFFFFF",
    t: Date.now().toString(), // бьём кеш браузера в превью
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

function buildQuery(params) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v != null) sp.set(k, v);
  });
  return sp.toString();
}

// валидация полей 
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

// генерация
generateBtn.addEventListener("click", async () => {
  qrResult.innerHTML = `<p class="placeholder">⏳ Генерация QR-кода...</p>`;

  if (!validate(currentType)) {
    qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Заполните обязательные поля!</p>`;
    return;
  }

  const params = collectParams(currentType);
  const url = `${API_URL}?${buildQuery(params)}`;

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
      link.download = `qr_${currentType}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };
  };
  img.onerror = () => {
    qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Ошибка генерации QR</p>`;
  };
  img.src = url;
});
