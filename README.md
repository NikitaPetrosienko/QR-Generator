
# QR Generator Service

Микросервис для генерации **QR-кодов** (текст, ссылка, телефон, email, wi-fi vCard).  
Написан на **Python 3.11 + FastAPI**.  
Возвращает изображение QR-кода в формате **PNG** или **SVG** по HTTP-запросу.

## Возможности 

- Генерация QR-кодов в формате PNG или SVG.  
- Поддержка различных типов данных: текст, ссылка, телефон, email, SMS, Wi-Fi, vCard.  
- Цветовая настройка QR-кодов (для PNG).  
- Автоматическая отрисовка фронта на основе спецификации с бэка (`/form-spec`).  
- Кэширование результатов (ETag, Cache-Control).  
- Раздача фронта напрямую из FastAPI.

## Структура проекта  

qr-service/  
├── README.md                 # Описание проекта, использование и настройка  
├── requirements-win.txt      # Список зависимостей   
├── pkgs/                     # Локальные wheel-пакеты для оффлайн установки  
├── venv                      # Окружение
├── main.py                   # FastAPI приложение с эндпоинтами   
└── public/  
    └── index.html            # Веб-интерфейс: формы по /form-spec, вызовы /compose и /qr

## Запуск

```bash
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --no-index --find-links=pkgs -r requirements-win.txt
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

После запуска сервис доступен по адресу:
- Frontend: [http://localhost:8000/ui](http://localhost:8000/ui) 
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)  
- Health-check: [http://localhost:8000/healthz](http://localhost:8000/healthz) 

## API

### `GET /healthz`

Возвращает:
```json
{"status": "ok"}
```
Используется для мониторинга и проверки контейнера.

## Технологии

- Python 3.11  
- FastAPI  
- Uvicorn  
- qrcode (PIL)  

## Дополнительно

- В ответах есть `ETag` и `Cache-Control` → браузеры и прокси будут кэшировать QR.  
- На данном этапе разработки CORS включён (`*` по умолчанию) → можно дергать API из JS на других доменах.    


