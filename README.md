# Rutube Video Downloader

Скрипт для скачивания видео с сайта Rutube.ru

## Установка

1. Установите зависимости:
```bash
uv sync
```

2. Установите браузеры для Playwright:
```bash
uv run playwright install chromium
```

## Использование

```bash
uv run python rutube_downloader.py <URL> [output_path]
```

### Примеры

```bash
# Скачать видео с автоматическим именем файла
uv run python rutube_downloader.py https://rutube.ru/video/55f0ce41c0a5adc5b5b263fdf9baa187/

# Скачать видео с указанным именем файла
uv run python rutube_downloader.py https://rutube.ru/video/55f0ce41c0a5adc5b5b263fdf9baa187/ video.mp4
```

## Как это работает

1. Скрипт использует Playwright для анализа страницы и получения информации о видео через API Rutube
2. Извлекает URL M3U8 плейлиста (HLS формат)
3. Парсит M3U8 плейлист и получает список всех сегментов видео
4. Скачивает все сегменты последовательно
5. Объединяет сегменты в один видеофайл

## Зависимости

- `playwright` - для анализа сайта и получения информации о видео
- `requests` - для скачивания сегментов видео
- `m3u8` - для парсинга HLS плейлистов
- `tqdm` - для отображения прогресса (опционально)

## Docker

### Сборка образа

```bash
docker build --platform linux/amd64 -t rutube_loader .
```

### Запуск контейнера

#### Способ 1: С использованием docker-compose (рекомендуется)

1. Создайте файл `.env` в корне проекта:
```bash
# .env
DOWNLOAD_PATH=/app/downloads
```

2. Запустите контейнер:
```bash
docker-compose up -d
```

#### Способ 2: С использованием docker run

```bash
# С переменными окружения напрямую
docker run -d -p 8000:8000 \
  -e DOWNLOAD_PATH=/app/downloads \
  --name rutube_app \
  rutube_loader

# Или с файлом .env
docker run -d -p 8000:8000 \
  --env-file .env \
  --name rutube_app \
  rutube_loader
```

### Управление переменными окружения

**Важно:** Файл `.env` **НЕ** включается в Docker образ (исключен в `.dockerignore`).

#### Доступные переменные окружения:

- `DOWNLOAD_PATH` - путь для сохранения скачанных видео (по умолчанию используется временная директория)

#### Как изменить переменные окружения:

1. **Через docker-compose.yml:**
   - Отредактируйте файл `.env` и перезапустите:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

2. **Через docker run:**
   ```bash
   # Остановите текущий контейнер
   docker stop rutube_app
   docker rm rutube_app
   
   # Запустите с новыми переменными
   docker run -d -p 8000:8000 \
     -e DOWNLOAD_PATH=/app/new_path \
     --name rutube_app \
     rutube_loader
   ```

3. **Через docker exec (для временных изменений):**
   ```bash
   docker exec -it rutube_app bash
   export DOWNLOAD_PATH=/app/new_path
   ```

#### Пример .env файла:

```bash
# Путь для сохранения скачанных видео
DOWNLOAD_PATH=/app/downloads
```

Приложение будет доступно по адресу: `http://localhost:8000`

