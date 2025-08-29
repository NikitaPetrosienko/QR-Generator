
# QR Generator Service

Микросервис для генерации **QR-кодов** (текст, ссылка, телефон, email, vCard).  
Написан на **Python 3.11 + FastAPI**, упакован в **Docker**.  
Возвращает изображение QR-кода в формате **PNG** или **SVG** по HTTP-запросу.

## 🚀 Запуск

Собрать и запустить контейнер:

```bash
docker build -t qr-service:1.0.0 .
docker run --rm -p 8000:8000 qr-service:1.0.0
```

После запуска сервис доступен по адресу:  
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)  
- Health-check: [http://localhost:8000/healthz](http://localhost:8000/healthz)  

## 🔧 API

### `GET /qr`

Генерация QR-кода.

**Параметры запроса:**

| Параметр   | Тип    | Обяз. | По умолчанию | Описание |
|------------|--------|-------|--------------|----------|
| `data`     | string | ✅     | —            | Данные для кодирования |
| `format`   | string | ❌     | `png`        | Формат: `png` или `svg` |
| `size`     | int    | ❌     | `512`        | Размер PNG (64–2048 px) |
| `level`    | string | ❌     | `M`          | Уровень коррекции ошибок: `L`=7%, `M`=15%, `Q`=25%, `H`=30% |
| `margin`   | int    | ❌     | `2`          | Отступ (0–8 модулей) |
| `download` | int    | ❌     | `0`          | `1` — скачать файлом, `0` — показать inline |
| `filename` | string | ❌     | `qr`         | Имя файла при скачивании |

**Примеры:**

```bash
# PNG 256x256
curl -o out.png "http://localhost:8000/qr?data=hello&format=png&size=256"

# SVG с телефоном
curl -o out.svg "http://localhost:8000/qr?data=TEL%3A%2B79991234567&format=svg"

# Email в PNG
curl -o mail.png "http://localhost:8000/qr?data=mailto%3Auser%40example.com&format=png&size=512"

# vCard (пример, данные должны быть URL-кодированы)
curl -o card.png "http://localhost:8000/qr?data=BEGIN%3AVCARD%0AVERSION%3A3.0%0AFN%3AIvan%20Ivanov%0AEND%3AVCARD&format=png"
```

### `GET /healthz`

Возвращает:
```json
{"status": "ok"}
```
Используется для мониторинга и проверки контейнера.

## 👀 Использование

QR можно встроить прямо на страницу портала:

```html
<img src="https://qr.company.local/qr?data=mailto%3Auser%40example.com&format=png&size=512" alt="QR">
```

Пользователь вводит данные → фронт кодирует их в URL → подставляет в `src` картинки.

## 📦 Технологии

- Python 3.11  
- FastAPI  
- Uvicorn  
- qrcode (PIL)  
- Docker  

## 🛠️ Разработка без Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

После запуска: [http://localhost:8000/docs](http://localhost:8000/docs)

## 📌 Дополнительно

- В ответах есть `ETag` и `Cache-Control` → браузеры и прокси будут кэшировать QR.  
- CORS включён (`*` по умолчанию) → можно дергать API из JS на других доменах.   


