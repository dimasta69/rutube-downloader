from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any, Callable, Awaitable
from urllib.parse import urljoin, urlparse

import m3u8
import requests
from playwright.async_api import async_playwright, Page
from tqdm import tqdm


def extract_video_id(url: str) -> str | None:
    """Извлекает ID видео из URL Rutube."""
    match = re.search(r'/video/([a-f0-9]+)', url)
    return match.group(1) if match else None


async def get_video_info(page: Page, video_id: str) -> dict[str, Any] | None:
    """Получает информацию о видео через API Rutube."""
    api_url = (
        f"https://rutube.ru/api/play/options/{video_id}/"
        "?no_404=true&referer=https%3A%2F%2Frutube.ru&pver=v2&client=wdp&mq=all&av1=1"
    )
    
    try:
        # Используем page.request для API запросов с cookies из текущего контекста
        response = await page.request.get(
            api_url,
            headers={
                "Referer": "https://rutube.ru/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30000
        )
        
        status = response.status
        print(f"Статус ответа API: {status} для video_id: {video_id}")
        
        if not response.ok:
            # Пытаемся получить текст ответа для диагностики
            try:
                text = await response.text()
                print(f"Ошибка API (статус {status}): {text[:500]}")
                if status == 500:
                    print(f"API вернул ошибку 500. Возможно, видео недоступно или заблокировано.")
            except Exception:
                pass
            return None
        
        # Парсим JSON ответ
        try:
            data = await response.json()
            print(f"Успешно получена информация о видео: {data.get('title', 'без названия')}")
            return data
        except Exception as json_error:
            print(f"Ошибка при парсинге JSON ответа: {json_error}")
            # Пытаемся получить текст ответа
            try:
                text = await response.text()
                print(f"Текст ответа (первые 500 символов): {text[:500]}")
            except Exception:
                pass
            return None
            
    except Exception as e:
        print(f"Ошибка при получении информации о видео: {e}")
        import traceback
        traceback.print_exc()
    
    return None


async def extract_video_info_from_page(page: Page) -> dict[str, Any] | None:
    """Пытается извлечь информацию о видео из HTML страницы."""
    try:
        # Сначала пытаемся найти данные в window объекте (самый надежный способ)
        try:
            page_data = await page.evaluate("""
                () => {
                    // Проверяем различные возможные места для данных о видео
                    if (window.__INITIAL_STATE__) {
                        return window.__INITIAL_STATE__;
                    }
                    if (window.__NEXT_DATA__) {
                        return window.__NEXT_DATA__;
                    }
                    if (window.__INITIAL_DATA__) {
                        return window.__INITIAL_DATA__;
                    }
                    // Пытаемся найти данные в глобальных переменных
                    if (typeof window.pageData !== 'undefined') {
                        return window.pageData;
                    }
                    return null;
                }
            """)
            if page_data:
                print("Найдены данные в window объекте")
                return page_data
        except Exception as e:
            print(f"Не удалось извлечь данные из window: {e}")
        
        # Альтернативный метод: ищем в script тегах с типом application/json
        try:
            script_content = await page.evaluate("""
                () => {
                    const scripts = Array.from(document.querySelectorAll('script[type="application/json"]'));
                    for (const script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent || '{}');
                            // Проверяем, что это данные о видео
                            if (data.video || data.video_balancer || (data.props && data.props.pageProps && data.props.pageProps.video)) {
                                return data;
                            }
                        } catch (e) {
                            continue;
                        }
                    }
                    return null;
                }
            """)
            if script_content:
                print("Найдены данные в script тегах")
                return script_content
        except Exception as e:
            print(f"Не удалось извлечь данные из script тегов: {e}")
            
    except Exception as e:
        print(f"Ошибка при извлечении данных со страницы: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def get_m3u8_url(video_info: dict[str, Any]) -> str | None:
    """Извлекает URL M3U8 плейлиста из информации о видео."""
    # Стандартный формат API Rutube
    if "video_balancer" in video_info:
        balancer = video_info["video_balancer"]
        if isinstance(balancer, dict):
            if "m3u8" in balancer:
                return balancer["m3u8"]
            if "default" in balancer:
                return balancer["default"]
    
    # Альтернативные пути для данных, извлеченных со страницы
    if "video" in video_info:
        video = video_info["video"]
        if isinstance(video, dict):
            if "video_balancer" in video:
                balancer = video["video_balancer"]
                if isinstance(balancer, dict):
                    if "m3u8" in balancer:
                        return balancer["m3u8"]
                    if "default" in balancer:
                        return balancer["default"]
    
    # Проверка в props.pageProps (Next.js структура)
    if "props" in video_info:
        props = video_info["props"]
        if isinstance(props, dict) and "pageProps" in props:
            page_props = props["pageProps"]
            if isinstance(page_props, dict) and "video" in page_props:
                video = page_props["video"]
                if isinstance(video, dict) and "video_balancer" in video:
                    balancer = video["video_balancer"]
                    if isinstance(balancer, dict):
                        if "m3u8" in balancer:
                            return balancer["m3u8"]
                        if "default" in balancer:
                            return balancer["default"]
    
    return None


def parse_m3u8_playlist(m3u8_url: str) -> list[str]:
    """Парсит M3U8 плейлист и возвращает список URL сегментов."""
    playlist = m3u8.load(m3u8_url)
    segments: list[str] = []
    
    # Если это master playlist, выбираем самый высокий битрейт
    if playlist.is_variant:
        best_playlist = max(
            playlist.playlists,
            key=lambda p: p.stream_info.bandwidth if p.stream_info else 0
        )
        variant_url = urljoin(m3u8_url, best_playlist.uri)
        playlist = m3u8.load(variant_url)
        # Обновляем базовый URL для сегментов после загрузки варианта
        m3u8_url = variant_url
    
    # Получаем базовый URL правильно используя urlparse
    parsed = urlparse(m3u8_url)
    # Строим базовый URL: scheme + netloc + путь до файла (без имени файла)
    path_parts = parsed.path.rstrip('/').split('/')
    base_path = '/'.join(path_parts[:-1]) if len(path_parts) > 1 else ''
    base_url = f"{parsed.scheme}://{parsed.netloc}{base_path}/"
    
    for segment in playlist.segments:
        # urljoin правильно обрабатывает относительные и абсолютные URL
        segment_url = urljoin(base_url, segment.uri)
        segments.append(segment_url)
    
    return segments


def download_segment(url: str, output_path: Path, session: requests.Session) -> bool:
    """Скачивает один сегмент видео."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://rutube.ru/",
        }
        response = session.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"Ошибка при скачивании сегмента {url}: {e}")
        return False


async def download_video(
    m3u8_url: str, 
    output_path: Path, 
    status_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None
) -> bool:
    """
    Скачивает видео из M3U8 плейлиста.
    
    Args:
        m3u8_url: URL M3U8 плейлиста
        output_path: Путь для сохранения видео
        status_callback: Асинхронный callback для отправки статуса
    """
    async def send_status(status: str, progress: float | None = None, message: str | None = None) -> None:
        """Вспомогательная функция для отправки статуса."""
        if status_callback:
            await status_callback({
                "status": status,
                "progress": progress,
                "message": message
            })
    
    print(f"Парсинг M3U8 плейлиста: {m3u8_url}")
    await send_status("parsing", 0, "Парсинг M3U8 плейлиста...")
    
    try:
        segments = parse_m3u8_playlist(m3u8_url)
        print(f"Найдено сегментов: {len(segments)}")
        await send_status("parsing", 10, f"Найдено сегментов: {len(segments)}")
    except Exception as e:
        print(f"Ошибка при парсинге M3U8: {e}")
        await send_status("error", None, f"Ошибка при парсинге M3U8: {e}")
        return False
    
    if not segments:
        print("Сегменты не найдены")
        await send_status("error", None, "Сегменты не найдены")
        return False
    
    # Создаем временную директорию для сегментов
    temp_dir = output_path.parent / f"{output_path.stem}_segments"
    temp_dir.mkdir(exist_ok=True)
    
    session = requests.Session()
    
    # Скачиваем все сегменты
    print("Скачивание сегментов...")
    await send_status("downloading", 20, "Начало скачивания сегментов...")
    downloaded_segments: list[Path] = []
    
    with tqdm(total=len(segments), desc="Скачивание", unit="сегмент") as pbar:
        for i, segment_url in enumerate(segments, 1):
            segment_path = temp_dir / f"segment_{i:05d}.ts"
            
            if segment_path.exists():
                downloaded_segments.append(segment_path)
                pbar.update(1)
            else:
                # Выполняем синхронное скачивание в отдельном потоке
                success = await asyncio.to_thread(download_segment, segment_url, segment_path, session)
                if success:
                    downloaded_segments.append(segment_path)
                else:
                    print(f"\nНе удалось скачать сегмент {i}, продолжаем...")
                pbar.update(1)
            
            # Отправляем прогресс скачивания (20-80%)
            progress = 20 + (i / len(segments)) * 60
            await send_status("downloading", progress, f"Скачано сегментов: {i}/{len(segments)}")
    
    if not downloaded_segments:
        print("Не удалось скачать ни одного сегмента")
        await send_status("error", None, "Не удалось скачать ни одного сегмента")
        return False
    
    # Объединяем сегменты
    print(f"Объединение {len(downloaded_segments)} сегментов в файл {output_path}...")
    await send_status("merging", 80, "Объединение сегментов...")
    try:
        async def merge_segments_async() -> None:
            """Асинхронная функция для объединения сегментов с отправкой статуса."""
            with open(output_path, "wb") as outfile:
                for idx, segment_path in enumerate(downloaded_segments, 1):
                    with open(segment_path, "rb") as infile:
                        outfile.write(infile.read())
                    
                    # Отправляем прогресс объединения (80-95%)
                    progress = 80 + (idx / len(downloaded_segments)) * 15
                    await send_status("merging", progress, f"Объединение: {idx}/{len(downloaded_segments)}")
        
        # Выполняем объединение
        await merge_segments_async()
        
        # Удаляем временную директорию
        import shutil
        await asyncio.to_thread(shutil.rmtree, temp_dir)
        
        print(f"Видео успешно скачано: {output_path}")
        # НЕ отправляем сообщение "completed" здесь, так как финальное сообщение
        # с правильным именем файла будет отправлено из routes/video.py после переименования
        # await send_status("completed", 100, f"Видео успешно скачано: {output_path.name}")
        return True
    except Exception as e:
        print(f"Ошибка при объединении сегментов: {e}")
        await send_status("error", None, f"Ошибка при объединении сегментов: {e}")
        return False


async def download_rutube_video(
    url: str, 
    output_path: str | None = None,
    status_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None
) -> bool:
    """
    Основная функция для скачивания видео с Rutube.
    
    Args:
        url: URL видео с Rutube
        output_path: Путь для сохранения видео
        status_callback: Асинхронный callback для отправки статуса
    """
    async def send_status(status: str, progress: float | None = None, message: str | None = None) -> None:
        """Вспомогательная функция для отправки статуса."""
        if status_callback:
            await status_callback({
                "status": status,
                "progress": progress,
                "message": message
            })
    
    video_id = extract_video_id(url)
    if not video_id:
        error_msg = f"Не удалось извлечь ID видео из URL: {url}"
        print(error_msg)
        await send_status("error", None, error_msg)
        return False
    
    print(f"ID видео: {video_id}")
    await send_status("initializing", 0, f"Инициализация загрузки видео (ID: {video_id})...")
    
    # Используем Playwright для получения информации о видео
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU"
        )
        page = await context.new_page()
        
        try:
            # Сначала открываем страницу видео, чтобы получить cookies и контекст
            print(f"Открываем страницу видео: {url}")
            await send_status("fetching_info", 3, "Загрузка страницы видео...")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Ждем немного, чтобы страница полностью загрузилась
                await page.wait_for_timeout(2000)
            except Exception as page_error:
                print(f"Предупреждение при загрузке страницы видео: {page_error}")
                # Продолжаем, даже если страница не загрузилась полностью
            
            print("Получение информации о видео через API...")
            await send_status("fetching_info", 5, "Получение информации о видео...")
            video_info = await get_video_info(page, video_id)
            
            # Если API не сработал, пытаемся извлечь данные со страницы
            if not video_info:
                print("API не вернул данные, пытаемся извлечь информацию со страницы...")
                await send_status("fetching_info", 7, "Попытка альтернативного метода получения информации...")
                video_info = await extract_video_info_from_page(page)
            
            if not video_info:
                error_msg = (
                    f"Не удалось получить информацию о видео (ID: {video_id}). "
                    "Возможные причины: видео недоступно, заблокировано или удалено. "
                    "Проверьте, что видео доступно для просмотра на rutube.ru"
                )
                print(error_msg)
                await send_status("error", None, error_msg)
                return False
            
            # Определяем путь для сохранения на основе названия видео
            video_title = video_info.get("title", f"video_{video_id}")
            # Заменяем пробелы на подчеркивания и очищаем от недопустимых символов
            safe_title = re.sub(r'[<>:"/\\|?*\s]', '_', video_title)
            
            if output_path:
                output_path = Path(output_path)
                # Если указана директория или путь без расширения, добавляем название файла
                if output_path.suffix == '' or (output_path.exists() and output_path.is_dir()):
                    output_path = output_path / f"{safe_title}.mp4"
                # Если указан полный путь с расширением, используем его как есть
            else:
                # Используем название видео для имени файла
                output_path = Path(f"{safe_title}.mp4")
            
            await send_status("fetching_info", 10, f"Видео: {video_title}")
            
            m3u8_url = get_m3u8_url(video_info)
            if not m3u8_url:
                error_msg = "M3U8 URL не найден в информации о видео"
                print(error_msg)
                await send_status("error", None, error_msg)
                return False
            
            print(f"M3U8 URL: {m3u8_url}")
            
        finally:
            await browser.close()
        
        # Скачиваем видео
        return await download_video(m3u8_url, output_path, status_callback)


async def main() -> None:
    """Точка входа в программу."""
    if len(sys.argv) < 2:
        print("Использование: python rutube_downloader.py <URL> [output_path]")
        print("Пример: python rutube_downloader.py https://rutube.ru/video/55f0ce41c0a5adc5b5b263fdf9baa187/")
        sys.exit(1)
    
    url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = await download_rutube_video(url, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

