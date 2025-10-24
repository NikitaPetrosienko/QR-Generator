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
  input.addEventListener("input", () => (preview.style.background = input.value));
});

// генерация QR
generateBtn.addEventListener("click", async () => {
  qrResult.innerHTML = `<p class="placeholder">⏳ Генерация QR-кода...</p>`;

  const getVal = (id) => document.getElementById(id)?.value?.trim() || "";

  // подсветка ошибок
  document.querySelectorAll("input, textarea").forEach((el) => {
    el.addEventListener("input", () => (el.style.borderColor = ""));
  });

  let requiredFields = [];
  switch (currentType) {
    case "url":
      requiredFields = ["data"];
      break;
    case "phone":
      requiredFields = ["data"];
      break;
    case "mail":
      requiredFields = ["to"];
      break;
    case "sms":
      requiredFields = ["phone", "text"];
      break;
    case "vcard":
      requiredFields = ["fn"];
      break;
  }

  let hasError = false;
  requiredFields.forEach((id) => {
    const el = document.getElementById(id);
    if (el && !getVal(id)) {
      el.style.borderColor = "#e74c3c";
      hasError = true;
    }
  });

  if (hasError) {
    qrResult.innerHTML = `<p class="placeholder" style="color:#e74c3c;">Заполните обязательные поля!</p>`;
    return;
  }

  const fill = document.getElementById("fillColor").value || "#000000";
  const finder = document.getElementById("finderColor").value || "#000000";
  const bg = document.getElementById("bgColor").value || "#FFFFFF";

  // сборка URL
  let url = "";
  switch (currentType) {
    case "url":
      url = `/qr/url?data=${encodeURIComponent(getVal("data"))}`;
      break;
    case "phone":
      url = `/qr/phone?number=${encodeURIComponent(getVal("data"))}`;
      break;
    case "mail":
      url = `/qr/mail?to=${encodeURIComponent(getVal("to"))}&subject=${encodeURIComponent(getVal("subject"))}&body=${encodeURIComponent(getVal("body"))}`;
      break;
    case "sms":
      url = `/qr/sms?phone=${encodeURIComponent(getVal("phone"))}&text=${encodeURIComponent(getVal("text"))}`;
      break;
    case "vcard":
      const params = ["fn", "org", "title", "dept", "email", "mobile", "work_short"]
        .map((id) => `${id}=${encodeURIComponent(getVal(id))}`)
        .join("&");
      url = `/qr/vcard?${params}`;
      break;
  }

  // цвета и антикеш
  url += `&fill=${encodeURIComponent(fill)}&finder=${encodeURIComponent(finder)}&bg=${encodeURIComponent(bg)}&t=${Date.now()}`;

  // создаём и вставляем изображение
  const img = new Image();
  img.src = url;
  img.classList.remove("visible");

  img.onload = () => {
    img.classList.add("visible");
    qrResult.innerHTML = "";
    qrResult.appendChild(img);

    // кнопка скачивания
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
});
