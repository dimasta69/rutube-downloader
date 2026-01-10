from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable, Awaitable

from rutube_downloader import download_rutube_video


class VideoService:
    """Сервис для работы с видео."""
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Очищает имя файла от недопустимых символов.
        
        Args:
            filename: Исходное имя файла
        
        Returns:
            Очищенное имя файла
        """
        # Удаляем расширение, если оно есть (мы всегда добавляем .mp4)
        name = filename
        if filename.lower().endswith('.mp4'):
            name = filename[:-4]
        
        # Удаляем недопустимые символы для имен файлов
        # Разрешаем: буквы, цифры, пробелы, дефисы, подчеркивания, точки
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        
        # Удаляем ведущие и завершающие пробелы и точки
        name = name.strip('. ')
        
        # Если после очистки имя пустое, используем дефолтное
        if not name:
            return None
        
        # Ограничиваем длину имени файла (например, 200 символов)
        if len(name) > 200:
            name = name[:200]
        
        return name
    
    @staticmethod
    async def download_and_get_path(
        url: str,
        status_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        file_name: str | None = None
    ) -> Path:
        """
        Скачивает видео с RuTube и возвращает путь к файлу.
        
        Args:
            url: URL видео с RuTube
            status_callback: Асинхронный callback для отправки статуса
            file_name: Опциональное имя файла (без расширения, будет добавлено .mp4)
        
        Returns:
            Path к файлу с видео
        
        Raises:
            ValueError: Если URL неверный или видео не удалось скачать
        """
        # Валидация URL
        if not url or "rutube.ru" not in url:
            raise ValueError("Неверный URL. Ожидается URL с rutube.ru")
        
        # Получаем путь для сохранения из переменной окружения
        download_path = os.getenv("DOWNLOAD_PATH")
        download_dir = None
        
        if download_path:
            download_dir = Path(download_path)
            try:
                # Создаем директорию, если она не существует
                download_dir.mkdir(parents=True, exist_ok=True)
                # Проверяем, что директория доступна для записи
                test_file = download_dir / ".write_test"
                try:
                    test_file.touch()
                    test_file.unlink()
                except (OSError, PermissionError):
                    # Директория недоступна для записи, используем /tmp
                    download_dir = None
            except (OSError, PermissionError):
                # Не удалось создать директорию, используем /tmp
                download_dir = None
        
        if download_dir is None:
            # Используем /tmp как fallback, если DOWNLOAD_PATH не задан или недоступен
            download_dir = Path("/tmp")
            download_dir.mkdir(parents=True, exist_ok=True)
        
        # Обрабатываем имя файла
        # Всегда переименовываем файл, даже если имя не указано (используем дефолтное)
        final_filename = None
        if file_name and file_name.strip():
            sanitized_name = VideoService._sanitize_filename(file_name.strip())
            if sanitized_name:
                final_filename = f"{sanitized_name}.mp4"
            else:
                # Если имя файла после очистки пустое, используем дефолтное имя
                final_filename = "video.mp4"
        
        # Если имя файла не указано, используем дефолтное имя
        if not final_filename:
            final_filename = "video.mp4"
        
        # Логируем для отладки
        print(f"DEBUG: file_name (input) = {file_name}")
        print(f"DEBUG: final_filename = {final_filename}")
        
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
        
        # Всегда переименовываем файл из временного в финальное имя
        # final_filename всегда должен быть установлен (либо из file_name, либо "video.mp4")
        if final_filename:
            final_path = download_dir / final_filename
            # Если файл с таким именем уже существует, добавляем номер
            counter = 1
            original_final_path = final_path
            while final_path.exists():
                name_without_ext = original_final_path.stem
                final_path = download_dir / f"{name_without_ext}_{counter}.mp4"
                counter += 1
            
            try:
                # Пытаемся переименовать файл
                temp_path.rename(final_path)
                # Убеждаемся, что возвращаем правильный путь с правильным именем
                print(f"Файл успешно переименован: {temp_path.name} -> {final_path.name}")
                return final_path
            except (OSError, PermissionError) as e:
                # Если не удалось переименовать, пытаемся скопировать файл
                # Это может помочь, если файл занят или есть проблемы с правами
                try:
                    import shutil
                    shutil.copy2(temp_path, final_path)
                    # Удаляем временный файл после успешного копирования
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                    return final_path
                except Exception as copy_error:
                    # Если и копирование не удалось, пытаемся использовать правильное имя
                    # путем создания жесткой ссылки или просто возвращаем путь с правильным именем
                    # Но файл физически останется с временным именем
                    print(f"Ошибка: не удалось переименовать или скопировать файл '{temp_path}' в '{final_path}': {e}, {copy_error}")
                    # Возвращаем путь с правильным именем, даже если файл физически не переименован
                    # Это позволит использовать правильное имя в ответе
                    # Но файл нужно будет искать по временному имени
                    # Лучше вернуть путь с правильным именем и попытаться создать ссылку
                    try:
                        import shutil
                        # Пытаемся создать жесткую ссылку с правильным именем
                        final_path.unlink(missing_ok=True)  # Удаляем, если существует
                        os.link(temp_path, final_path)
                        return final_path
                    except Exception:
                        # Если ничего не помогло, возвращаем временный файл
                        # Но логируем предупреждение
                        print(f"Критическая ошибка: файл останется с временным именем '{temp_path.name}' вместо '{final_filename}'")
                        return temp_path
        else:
            # Это не должно происходить, так как final_filename всегда должен быть установлен
            print(f"Предупреждение: final_filename не установлен, файл останется с временным именем '{temp_path.name}'")
            return temp_path
    
    @staticmethod
    def create_stream_generator(video_path: Path) -> Iterator[bytes]:
        """
        Создает генератор для потоковой передачи видеофайла.
        
        Файл удаляется после отправки (однократное скачивание).
        
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
            # Удаляем файл после отправки (однократное скачивание)
            if video_path.exists():
                try:
                    video_path.unlink()
                except Exception:
                    # Игнорируем ошибки при удалении (файл может быть занят)
                    pass

