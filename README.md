# QR Generator Service (UI + API)

Микросервис для генерации **QR-кодов**: `vCard 3.0`, ссылки (URL/текст), телефон, e-mail и SMS.  
Отдаёт **PNG** с точной перекраской finder-паттернов, кэшированием по **ETag** и понятным именем файла.  
Имеет два режима работы:

- **UI** — универсальный конструктор (`/ui`) + API `/api/v1/qr` с кастомизацией цветов и загрузкой логотипа (POST).
- **LK** — режим интеграции с корпоративным ЛК: фиксированный бренд-стиль из JSON-конфига, данные сотрудника из заголовков.

---

## 📌 Ключевые особенности

- **Единая точка входа:** `GET/POST /api/v1/qr`
- **Типы QR:** `url | phone | mail | sms | vcard` (автоопределение из полей, либо явный `type`)
- **LK-режим:** только `GET`, только `type=vcard`, стиль и логотип — из `config/qr_config.json`
- **POST multipart (UI):** загрузка пользовательского логотипа PNG ≤ **500 KB**, авто-нормализация и белая подложка в **модулях** QR
- **Точное перекрашивание** finder-углов, аккуратные бордеры, ограничение покрытия логотипом центра
- **Кэширование:** `ETag` + `Cache-Control: public, max-age=31536000, immutable` + корректный `Content-Disposition` с UTF-8
- **Логи и метрики:** JSON-логи в stdout и `logs/qr_service.log` (RotatingFileHandler), тайминги/статусы middleware
- **Статика UI:** `/ui` (SPA на `frontend/`), CORS включён для `GET, HEAD`

---

## 🚀 Быстрый старт

### В Docker
    docker build -t qr-generator:latest .
    docker compose up --build
    # API:     http://localhost:8000/api/v1/qr
    # UI:      http://localhost:8000/ui
    # Health:  http://localhost:8000/healthz


> Конфиг читается **на каждый запрос** — менять `config/qr_config.json` можно без пересборки.

### Локально (без Docker)
    python -m venv venv
    ./venv/bin/pip install -r requirements.txt           # Windows: .\venv\Scripts\pip.exe ...
    ./venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload


---

## 🧩 API

### Базовый эндпоинт
    GET/POST /api/v1/qr

### Общие параметры (Query / FormData)
| Параметр     | Тип       | По умолч. | Описание |
|--------------|-----------|-----------|----------|
| `context`    | `ui\|lk`  | `ui`      | Режим работы. В `lk` — только `GET`, только `vcard`. |
| `type`       | см. выше  | —         | Может быть опущен — определяется из полей. |
| `fill`       | `#RRGGBB` | `#000000` | Цвет модулей. |
| `finder`     | `#RRGGBB` | `#000000` | Цвет finder-углов. |
| `bg`         | `#RRGGBB` | `#FFFFFF` | Цвет фона. |
| `filename`   | `str`     | —         | Имя файла без `.png` (в `Content-Disposition`). |

### Поля по типам
| Тип    | Обязательные / поддерживаемые поля |
|--------|------------------------------------|
| `url`  | `data` — URL или произвольный текст |
| `phone`| `number` **или** `phonenumber` |
| `mail` | `to` (**обязательно**), `subject`, `body` |
| `sms`  | `phone` (**обязательно**), `text` |
| `vcard`| `fn` (**обязательно**), `org`, `title`, `dept`, `email`, `mobile`, `work_short` |

### Ответ
- `200 image/png` — сам QR.
- `304` — по `If-None-Match` совпал `ETag`.
- Ошибки валидации: `400`, в `lk` при `POST`: `405`.

---

## 🧪 Примеры запросов

### 1) URL/текст (GET)
    curl "http://localhost:8000/api/v1/qr?context=ui&type=url&data=https%3A%2F%2Fwww.example.com&fill=%23009639&finder=%23EAAA00&bg=%23FFFFFF&filename=example"

### 2) Телефон (GET)
    curl "http://localhost:8000/api/v1/qr?type=phone&number=%2B7%20999%20123%2045%2067"

### 3) E-mail (GET)
    curl "http://localhost:8000/api/v1/qr?type=mail&to=user%40nestro.ru&subject=%D0%92%D0%BE%D0%BF%D1%80%D0%BE%D1%81&body=%D0%A2%D0%B5%D1%81%D1%82"

### 4) SMS (GET)
    curl "http://localhost:8000/api/v1/qr?type=sms&phone=%2B7%20999%20123%2045%2067&text=%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82"

### 5) vCard (GET, UI-режим)
    curl "http://localhost:8000/api/v1/qr?type=vcard&fn=%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2%20%D0%98%D0%B2%D0%B0%D0%BD%20%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2%D0%B8%D1%87&org=%D0%97%D0%9D%20%D0%A6%D0%B8%D1%84%D1%80%D0%B0&title=%D0%A0%D0%B0%D0%B7%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D1%87%D0%B8%D0%BA&email=user%40nestro.ru&mobile=%2B79991234567&work_short=002-8042"

### 6) vCard (GET, **LK-режим** + заголовки ЛК)
> В `lk` тип всегда `vcard`, поля берутся из заголовков `X-Employee-*`, стиль — из конфига.

    curl -H "X-Employee-FullName: Петров Иван Иванович" \
         -H "X-Employee-Org: ЗН Цифра" \
         -H "X-Employee-Title: Разработчик" \
         -H "X-Employee-Dept: Отдел ИТ" \
         -H "X-Employee-Email: IPetrov@nestro.ru" \
         -H "X-Employee-Mobile: +79991234567" \
         -H "X-Employee-WorkShort: 002-8042" \
         "http://localhost:8000/api/v1/qr?context=lk&type=vcard"

### 7) Загрузка логотипа (POST multipart, **UI**)
    curl -X POST "http://localhost:8000/api/v1/qr" \
      -F "context=ui" -F "type=vcard" -F "fn=Петров Иван Иванович" \
      -F "fill=#0067B2" -F "finder=#009639" -F "bg=#FFFFFF" -F "filename=petrov_vcard" \
      -F "logo=@assets/logo.png;type=image/png"

> Лого PNG ≤ **500 KB**; если изображение слишком большое — автоматически уменьшается до 1024px по стороне.

---

## 🧱 Режим **LK** — интеграция с ЛК

- Разрешён только `GET /api/v1/qr?context=lk&type=vcard`
- Параметры визитки читаются из заголовков (UTF-8 decode safe):
  - `X-Employee-FullName`, `X-Employee-Org`, `X-Employee-Title`, `X-Employee-Dept`,
    `X-Employee-Email`, `X-Employee-Mobile`, `X-Employee-WorkShort`
- Стиль и логотип берутся из `config/qr_config.json`  
- Базовый номер для `WORK`/доб. — из `VCARD_EXT_BASE` (ENV имеет приоритет)

---

## ⚙️ Конфигурация

Файл `backend/app/config/qr_config.json` перечитывается **каждый запрос** (можно заменить без рестарта).  
Путь можно переопределить ENV-переменной `QR_CONFIG_FILE` (относительный — от `cwd`).

### Пример `qr_config.json`
    {
      "QR_SIZE": 512,
      "QR_BORDER_PX": 6,
      "QR_FILL": "#009639",
      "QR_BG": "#FFFFFF",
      "QR_FINDER": "#EAAA00",
      "QR_LOGO": "assets/logo.png",
      "QR_LOGO_RATIO": 0.5,
      "QR_LOGO_PAD": 0.5,
      "QR_LOGO_PAD_RADIUS": 0,
      "QR_EC": "H",
      "WORKERS": 2
    }

### Пояснения параметров
| Ключ                 | Описание |
|----------------------|----------|
| `QR_SIZE`            | Размер итогового изображения (px). |
| `QR_BORDER_PX`       | Внешний бордер (px). |
| `QR_FILL` / `QR_BG`  | Цвет модулей / фона. |
| `QR_FINDER`          | Цвет finder-углов. |
| `QR_EC`              | Ошибкокоррекция: `H` или `Q`. |
| `QR_LOGO`            | Путь к логотипу (используется **только** в `context=lk`). |
| `QR_LOGO_RATIO`      | Доля стороны QR, занимаемая логотипом. |
| `QR_LOGO_PAD`        | Масштаб белой подложки под логотип. |
| `QR_LOGO_PAD_RADIUS` | Радиус скругления подложки. |
| `VCARD_EXT_BASE`     | Базовый рабочий номер (для отображения `WORK; pref` + возможный доб.). |
| `WORKERS`            | Кол-во воркеров при прод-старте (используйте в своём entrypoint/compose). |

> В UI-режиме лого из конфига **не** используется — логотип можно прислать только как `POST multipart`.

---

## 📦 Заголовки и кэширование

- `ETag`: основан на полезной нагрузке и стиле (включая хеш файла логотипа).
- `If-None-Match`: при совпадении возвращается `304`.
- `Cache-Control: public, max-age=31536000, immutable`
- `Content-Disposition`: корректно формирует ASCII и `filename*` (UTF-8), чтобы имена файлов были удобочитаемы.

---

## 🔐 CORS и безопасность

- Включён `CORS` для `GET, HEAD` и любых заголовков.
- В `LK` режим **запрещён `POST`** (`405`).
- Валидации размеров/типа логотипа и обязательных полей с явными `400`.

---

## 🧭 Структура проекта

    .
    ├── assets/
    ├── backend/
    │   └── app/
    │       ├── api/
    │       │   ├── __init__.py
    │       │   └── qr.py                         # единый endpoint /api/v1/qr
    │       ├── config/
    │       │   ├── config.py                     # чтение JSON-конфига (каждый запрос)
    │       │   └── qr_config.json                # бренд-стиль, логотип, VCARD_EXT_BASE и т.д.
    │       ├── core/
    │       │   ├── __init__.py
    │       │   ├── etag.py                       # подпись стиля (учитывает хеш лого)
    │       │   ├── http.py                       # ETag, Content-Disposition, ответы PNG
    │       │   ├── renderer.py                   # генерация, перекраска finder, логотипы
    │       │   ├── style.py                      # QRStyle (Pydantic v2), merge, ENV helpers
    │       │   └── vcard.py                      # построение vCard 3.0
    │       ├── loging/
    │       │   ├── __init__.py
    │       │   ├── logging_conf.py               # JSON-логгер stdout + файл
    │       │   └── metrics_basic.py              # middleware с таймингами/статусом
    │       └── main.py                           # FastAPI app, /ui, /healthz, CORS, middleware
    ├── frontend/
    │   ├── index.html
    │   ├── script.js
    │   └── style.css
    ├── .dockerignore
    ├── .gitignore
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    └── README.md

---

## 🧾 Логи и метрики

- JSON-формат: `{"ts": "...", "level": "INFO", "logger": "qr", "msg": "...", "event": "qr_request", "type": "...", "from": "...", "path": "...", "status": 200, "ms": 173.6}`
- Пишутся в stdout и файл `logs/qr_service.log` c ротацией (5×5MB).
- Middleware (`metrics_basic.py`) логирует каждый запрос с длительностью.

---

## ❤️ UI (конструктор)

- Доступен на `/ui`, работает поверх того же API.
- Поддерживает пресеты бренд-цветов, ручной выбор `fill/finder/bg`.
- Кнопка «Добавить логотип» переводит генерацию в `POST multipart` c авто-нормализацией логотипа (обрезка прозрачных/белых полей, ограничение покрытия центра, масштабирование по модульной сетке).

---

## 🧯 Диагностика ошибок

| Код | Причина |
|-----|--------|
| `400` | Некорректные/отсутствующие параметры (например, пустой `to` для `mail`, `phone` для `sms`, `fn` для `vcard`); неверный тип логотипа; логотип > 500 KB; повреждённый PNG. |
| `405` | Попытка `POST` в `context=lk`. |
| `415` | (Потенциально) неверный `Content-Type` при `POST` (нужно `multipart/form-data`). |
| `500` | Непредвиденная ошибка рендеринга. Смотрите логи. |

---

## 🔧 Переменные окружения

- `QR_CONFIG_FILE` — путь к JSON-конфигу (абс./относительный от `cwd`).
- `VCARD_EXT_BASE` — переопределяет одноимённый ключ из конфига (для `WORK` телефона).
- (Оркестратор) `UVICORN_WORKERS` / `WORKERS` из конфига — используйте в своём entrypoint.

---

## 🗺️ Совместимость и версия API

- Стабильный префикс: **`/api/v1`**.  
  Любые будущие изменения будут выпускаться как `/api/v2`, без поломки текущих интеграций.

---

## 🩺 Healthcheck
    GET /healthz  →  {"status": "ok"}

---

## 📚 Зависимости

- `fastapi`, `uvicorn`
- `pillow`
- `qrcode`

> Смотрите `requirements.txt` для закреплённых версий.

---

## ✍️ Примечания по логотипам (UI/POST)

- Только **PNG**, ≤ **500 KB**.
- Слишком большие файлы уменьшаются до **1024 px** по максимальной стороне.
- Белая подложка и скругление рассчитываются **в модулях QR**, чтобы не портить считываемость.
- Центровая площадь логотипа ограничена (по умолчанию ≤ 20% внутреннего квадрата данных).

---

## 🔒 Лицензирование / права

Встраиваемые логотипы/бренд-цвета принадлежат правообладателям.  
Используйте сервис в соответствии с внутренними политиками ИБ и бренда.
