from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable, Awaitable

from rutube_downloader import download_rutube_video


class VideoService:
    """Сервис для работы с видео."""
    
    @staticmethod
    async def download_and_get_path(
        url: str,
        status_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None
    ) -> Path:
        """
        Скачивает видео с RuTube и возвращает путь к временному файлу.
        
        Args:
            url: URL видео с RuTube
            status_callback: Асинхронный callback для отправки статуса
        
        Returns:
            Path к временному файлу с видео
        
        Raises:
            ValueError: Если URL неверный или видео не удалось скачать
        """
        # Валидация URL
        if not url or "rutube.ru" not in url:
            raise ValueError("Неверный URL. Ожидается URL с rutube.ru")
        
        # Получаем путь для сохранения из переменной окружения
        download_path = os.getenv("DOWNLOAD_PATH")
        if download_path:
            download_dir = Path(download_path)
            # Создаем директорию, если она не существует
            download_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Используем текущую директорию, если переменная не задана
            download_dir = Path.cwd()
        
        # Создаем временный файл для сохранения видео
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp4", dir=download_dir
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
        
        # Скачиваем видео
        success = await download_rutube_video(url, str(temp_path), status_callback)
        
        if not success:
            # Удаляем временный файл при ошибке
            if temp_path.exists():
                temp_path.unlink()
            raise ValueError("Не удалось скачать видео")
        
        # Проверяем, что файл существует и не пустой
        if not temp_path.exists() or temp_path.stat().st_size == 0:
            if temp_path.exists():
                temp_path.unlink()
            raise ValueError("Видеофайл не был создан или пуст")
        
        return temp_path
    
    @staticmethod
    def create_stream_generator(video_path: Path) -> Iterator[bytes]:
        """
        Создает генератор для потоковой передачи видеофайла.
        
        Args:
            video_path: Путь к видеофайлу
        
        Yields:
            Байты видеофайла (chunks)
        """
        chunk_size = 8192  # 8KB chunks
        try:
            with open(video_path, mode="rb") as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        finally:
            # Удаляем временный файл после отправки
            if video_path.exists():
                try:
                    video_path.unlink()
                except Exception:
                    # Игнорируем ошибки при удалении (файл может быть занят)
                    pass

