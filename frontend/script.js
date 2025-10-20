const tabs = document.querySelectorAll(".tab");
const formFields = document.getElementById("formFields");
const qrResult = document.getElementById("qrResult");
const generateBtn = document.getElementById("generateBtn");

let currentType = "url";

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

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentType = tab.dataset.type;
    renderForm(currentType);
  });
});

["fill", "finder", "bg"].forEach((key) => {
  const input = document.getElementById(`${key}Color`);
  const preview = document.getElementById(`${key}Preview`);
  input.addEventListener("input", () => (preview.style.background = input.value));
});

generateBtn.addEventListener("click", async () => {
  qrResult.innerHTML = `<p class="placeholder">⏳ Генерация QR-кода...</p>`;

  // параметры кастомизации
  const fill = document.getElementById("fillColor").value || "#000000";
  const finder = document.getElementById("finderColor").value || "#000000";
  const bg = document.getElementById("bgColor").value || "#FFFFFF";
  const size = document.getElementById("size").value || 512;
  const border = document.getElementById("border").value || 8;

  // собираем URL запроса
  let url = "";

  switch (currentType) {
    case "url":
      url = `/qr/url?data=${encodeURIComponent(document.getElementById("data").value)}`;
      break;
    case "phone":
      url = `/qr/phone?number=${encodeURIComponent(document.getElementById("data").value)}`;
      break;
    case "mail":
      url = `/qr/mail?to=${encodeURIComponent(document.getElementById("to").value)}&subject=${encodeURIComponent(document.getElementById("subject").value)}`;
      break;
    case "sms":
      url = `/qr/sms?phone=${encodeURIComponent(document.getElementById("phone").value)}&text=${encodeURIComponent(document.getElementById("text").value)}`;
      break;
    case "vcard":
      const params = ["fn", "org", "title", "dept", "email", "mobile", "work_short"]
        .map((id) => `${id}=${encodeURIComponent(document.getElementById(id).value)}`)
        .join("&");
      url = `/qr/vcard?${params}`;
      break;
  }

  // добавляем стили
  url += `&fill=${encodeURIComponent(fill)}&finder=${encodeURIComponent(finder)}&bg=${encodeURIComponent(bg)}&size=${size}&border=${border}`;

  // Создаём изображение и добавляем анимацию
  const img = new Image();
  img.src = url;

  img.onload = () => {
    img.classList.add("visible");
    qrResult.innerHTML = "";
    qrResult.appendChild(img);
  };

  img.onerror = () => {
    qrResult.innerHTML = `<p class="placeholder">Ошибка генерации QR</p>`;
  };
});
