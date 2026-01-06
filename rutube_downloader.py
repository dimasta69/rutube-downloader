from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import m3u8
import requests
from playwright.async_api import async_playwright, Browser, Page
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
        response = await page.goto(api_url)
        if response and response.ok:
            data = await response.json()
            return data
    except Exception as e:
        print(f"Ошибка при получении информации о видео: {e}")
    
    return None


def get_m3u8_url(video_info: dict[str, Any]) -> str | None:
    """Извлекает URL M3U8 плейлиста из информации о видео."""
    if "video_balancer" in video_info:
        balancer = video_info["video_balancer"]
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


def download_video(m3u8_url: str, output_path: Path) -> bool:
    """Скачивает видео из M3U8 плейлиста."""
    print(f"Парсинг M3U8 плейлиста: {m3u8_url}")
    
    try:
        segments = parse_m3u8_playlist(m3u8_url)
        print(f"Найдено сегментов: {len(segments)}")
    except Exception as e:
        print(f"Ошибка при парсинге M3U8: {e}")
        return False
    
    if not segments:
        print("Сегменты не найдены")
        return False
    
    # Создаем временную директорию для сегментов
    temp_dir = output_path.parent / f"{output_path.stem}_segments"
    temp_dir.mkdir(exist_ok=True)
    
    session = requests.Session()
    
    # Скачиваем все сегменты
    print("Скачивание сегментов...")
    downloaded_segments: list[Path] = []
    
    with tqdm(total=len(segments), desc="Скачивание", unit="сегмент") as pbar:
        for i, segment_url in enumerate(segments, 1):
            segment_path = temp_dir / f"segment_{i:05d}.ts"
            
            if segment_path.exists():
                downloaded_segments.append(segment_path)
                pbar.update(1)
                continue
            
            if download_segment(segment_url, segment_path, session):
                downloaded_segments.append(segment_path)
            else:
                print(f"\nНе удалось скачать сегмент {i}, продолжаем...")
            
            pbar.update(1)
    
    if not downloaded_segments:
        print("Не удалось скачать ни одного сегмента")
        return False
    
    # Объединяем сегменты
    print(f"Объединение {len(downloaded_segments)} сегментов в файл {output_path}...")
    try:
        with open(output_path, "wb") as outfile:
            for segment_path in tqdm(downloaded_segments, desc="Объединение", unit="сегмент"):
                with open(segment_path, "rb") as infile:
                    outfile.write(infile.read())
        
        # Удаляем временную директорию
        import shutil
        shutil.rmtree(temp_dir)
        
        print(f"Видео успешно скачано: {output_path}")
        return True
    except Exception as e:
        print(f"Ошибка при объединении сегментов: {e}")
        return False


async def download_rutube_video(url: str, output_path: str | None = None) -> bool:
    """Основная функция для скачивания видео с Rutube."""
    video_id = extract_video_id(url)
    if not video_id:
        print(f"Не удалось извлечь ID видео из URL: {url}")
        return False
    
    print(f"ID видео: {video_id}")
    
    # Используем Playwright для получения информации о видео
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        try:
            print("Получение информации о видео...")
            video_info = await get_video_info(page, video_id)
            
            if not video_info:
                print("Не удалось получить информацию о видео")
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
            
            m3u8_url = get_m3u8_url(video_info)
            if not m3u8_url:
                print("M3U8 URL не найден в информации о видео")
                return False
            
            print(f"M3U8 URL: {m3u8_url}")
            
        finally:
            await browser.close()
        
        # Скачиваем видео
        return download_video(m3u8_url, output_path)


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

