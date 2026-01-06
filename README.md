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

