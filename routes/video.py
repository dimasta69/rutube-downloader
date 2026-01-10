from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, StreamingResponse

from services.video_service import VideoService

router = APIRouter(prefix="/api/v1", tags=["video"])


def get_download_directory() -> Path:
    """
    Возвращает директорию для загрузки файлов.
    
    Returns:
        Path к директории загрузки
    """
    download_path = os.getenv("DOWNLOAD_PATH")
    download_dir = None

    if download_path:
        download_dir = Path(download_path)
        # Проверяем, что директория существует и доступна
        if not download_dir.exists() or not download_dir.is_dir():
            download_dir = None

    if download_dir is None:
        # Используем /tmp как fallback, если DOWNLOAD_PATH не задан или недоступен
        download_dir = Path("/tmp")

    return download_dir


async def schedule_file_deletion(file_path: Path, delay_seconds: float) -> None:
    """
    Планирует удаление файла через указанное время.

    Args:
        file_path: Путь к файлу для удаления
        delay_seconds: Задержка в секундах перед удалением
    """
    await asyncio.sleep(delay_seconds)
    # Проверяем, что файл все еще существует перед удалением
    if file_path.exists() and file_path.is_file():
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            # Игнорируем ошибки при удалении (файл может быть занят)
            pass


def get_file_unused_ttl_seconds() -> float:
    """
    Получает время жизни неиспользованного файла в секундах из переменной окружения.
    
    Файл будет автоматически удален, если его не скачали в течение этого времени.

    Returns:
        Время жизни файла в секундах (по умолчанию 180 секунд = 3 минуты)
    """
    # Сначала проверяем новую переменную FILE_UNUSED_TTL_MINUTES
    ttl_minutes = os.getenv("FILE_UNUSED_TTL_MINUTES")
    
    # Если не задана, проверяем старую переменную для обратной совместимости
    if ttl_minutes is None:
        ttl_minutes = os.getenv("FILE_TTL_MINUTES", "3")
    
    try:
        ttl_minutes = float(ttl_minutes)
        if ttl_minutes <= 0:
            ttl_minutes = 3
    except (ValueError, TypeError):
        ttl_minutes = 3
    return ttl_minutes * 60  # Конвертируем минуты в секунды


@router.get("/")
async def root() -> dict[str, str]:
    """Корневой эндпоинт API."""
    return {"message": "RuTube Video Downloader API"}


@router.get("/download")
async def download_video(
    url: Annotated[str, Query(description="URL видео с RuTube")],
    file_name: Annotated[
        str | None,
        Query(description="Имя файла (без расширения, будет сохранено как .mp4)"),
    ] = None,
) -> StreamingResponse:
    """
    Скачивает видео с RuTube и возвращает его как поток.

    Args:
        url: URL видео с RuTube (например, https://rutube.ru/video/...)
        file_name: Опциональное имя файла (без расширения, будет сохранено как .mp4)

    Returns:
        StreamingResponse с видеофайлом в формате MP4
    """
    video_service = VideoService()

    try:
        # Скачиваем видео через сервис
        video_path = await video_service.download_and_get_path(url, None, file_name)

        # Создаем генератор для потоковой передачи файла
        stream_generator = video_service.create_stream_generator(video_path)

        # Возвращаем потоковый ответ
        return StreamingResponse(
            stream_generator,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{video_path.name}"'
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_msg = str(e) if str(e) else type(e).__name__
        print(f"Ошибка в эндпоинте /download: {error_msg}")
        print(f"Traceback:\n{error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обработке запроса: {error_msg}"
        )


@router.get("/files")
async def list_files() -> dict[str, list[dict[str, Any]]]:
    """
    Возвращает список всех доступных видеофайлов с информацией о них.
    
    Returns:
        Словарь с массивом файлов, каждый содержит name, size, created_at
    """
    download_dir = get_download_directory()
    ttl_seconds = get_file_unused_ttl_seconds()
    current_time = time.time()
    
    files = []
    
    try:
        # Получаем все .mp4 файлы в директории
        for file_path in download_dir.glob("*.mp4"):
            if not file_path.is_file():
                continue
                
            # Проверяем, не истекло ли время жизни файла
            file_age = current_time - file_path.stat().st_mtime
            if file_age > ttl_seconds:
                # Файл слишком старый, удаляем его
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            
            file_info = {
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "created_at": file_path.stat().st_mtime,
                "age_seconds": file_age,
            }
            files.append(file_info)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении списка файлов: {str(e)}"
        )
    
    return {"files": files}


@router.get("/files/search")
async def search_file_by_name(
    name: Annotated[str, Query(description="Часть имени файла для поиска (case-insensitive)")]
) -> dict[str, list[dict[str, Any]]]:
    """
    Ищет файлы по частичному совпадению имени.
    
    Args:
        name: Часть имени файла для поиска (без учета регистра)
    
    Returns:
        Словарь с массивом найденных файлов
    """
    download_dir = get_download_directory()
    ttl_seconds = get_file_unused_ttl_seconds()
    current_time = time.time()
    
    search_name_lower = name.lower()
    found_files = []
    
    try:
        # Ищем все .mp4 файлы, содержащие указанное имя
        for file_path in download_dir.glob("*.mp4"):
            if not file_path.is_file():
                continue
            
            file_name_lower = file_path.name.lower()
            
            # Проверяем, содержит ли имя файла искомую строку
            if search_name_lower not in file_name_lower:
                continue
                
            # Проверяем, не истекло ли время жизни файла
            file_age = current_time - file_path.stat().st_mtime
            if file_age > ttl_seconds:
                # Файл слишком старый, удаляем его
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            
            file_info = {
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "created_at": file_path.stat().st_mtime,
                "age_seconds": file_age,
            }
            found_files.append(file_info)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при поиске файлов: {str(e)}"
        )
    
    return {"files": found_files}


@router.get("/file/{filename}")
@router.head("/file/{filename}")
async def get_downloaded_file(
    filename: str,
    request: Request,
    background_tasks: BackgroundTasks,
    search: Annotated[bool, Query(description="Если True, ищет файл по частичному совпадению имени")] = False
) -> FileResponse:
    """
    Возвращает ранее скачанный видеофайл по имени.

    Если search=True, ищет первый файл, имя которого содержит указанное значение.

    Имя файла берется из ответа WebSocket (file_id) и ищется в той же
    директории, что используется сервисом загрузки.

    Поддерживает GET и HEAD методы для проверки доступности файла.
    """
    download_dir = get_download_directory()
    
    # Если включен режим поиска, ищем файл по частичному совпадению
    if search:
        filename_lower = filename.lower()
        file_path = None
        ttl_seconds = get_file_unused_ttl_seconds()
        current_time = time.time()
        
        # Ищем первый подходящий файл
        for path in download_dir.glob("*.mp4"):
            if not path.is_file():
                continue
            
            if filename_lower in path.name.lower():
                # Проверяем, не истекло ли время жизни файла
                file_age = current_time - path.stat().st_mtime
                if file_age <= ttl_seconds:
                    file_path = path
                    filename = path.name  # Обновляем filename для ответа
                    break
        
        if file_path is None:
            raise HTTPException(status_code=404, detail=f"Файл, содержащий '{filename}', не найден")
    else:
        # Точное совпадение имени файла
        file_path = download_dir / filename

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Файл не найден")

        # Проверяем, не истекло ли время жизни файла
        ttl_seconds = get_file_unused_ttl_seconds()
        file_age = time.time() - file_path.stat().st_mtime
        if file_age > ttl_seconds:
            # Файл слишком старый, удаляем его
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=404, detail="Файл не найден")

    # Для HEAD запросов просто возвращаем информацию о файле без удаления
    if request.method == "HEAD":
        return FileResponse(
            file_path,
            media_type="video/mp4",
            filename=filename,
        )

    # Для GET запросов удаляем файл сразу после отправки (однократное скачивание)
    background_tasks.add_task(file_path.unlink, missing_ok=True)

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=filename,
        background=background_tasks,
    )


@router.websocket("/download/status")
async def download_video_status(websocket: WebSocket) -> None:
    """
    WebSocket эндпоинт для получения статуса загрузки видео в реальном времени.

    Ожидает сообщение с JSON: {"url": "https://rutube.ru/video/..."}
    Отправляет статус загрузки в формате:
    {
        "status": "parsing" | "downloading" | "merging" | "completed" | "error",
        "progress": 0-100 (float) | null,
        "message": "Описание текущего этапа"
    }
    """
    await websocket.accept()

    try:
        # Получаем URL из первого сообщения
        data = await websocket.receive_text()
        message = json.loads(data)
        url = message.get("url")
        file_name = message.get("file_name")

        if not url:
            await websocket.send_json({
                "status": "error",
                "progress": None,
                "message": "URL не указан в сообщении"
            })
            await websocket.close()
            return

        # Валидация URL
        if "rutube.ru" not in url:
            await websocket.send_json({
                "status": "error",
                "progress": None,
                "message": "Неверный URL. Ожидается URL с rutube.ru"
            })
            await websocket.close()
            return

        # Создаем callback для отправки статуса через WebSocket
        async def status_callback(status_data: dict[str, str | float | None]) -> None:
            """Callback для отправки статуса через WebSocket."""
            try:
                await websocket.send_json(status_data)
            except Exception:
                # Если WebSocket закрыт, просто игнорируем ошибку
                pass

        # Создаем сервис и начинаем загрузку
        video_service = VideoService()

        try:
            # Скачиваем видео с отправкой статуса
            video_path = await video_service.download_and_get_path(url, status_callback, file_name)

            # Убеждаемся, что файл существует
            if not video_path.exists():
                raise ValueError("Файл не был создан")

            # Получаем актуальное имя файла из пути
            # video_path должен содержать правильное имя после переименования
            actual_filename = video_path.name
            actual_file_path = str(video_path)

            # Логируем для отладки
            print(f"DEBUG: video_path = {video_path}")
            print(f"DEBUG: actual_filename = {actual_filename}")
            print(f"DEBUG: file_name (requested) = {file_name}")

            # Планируем автоматическое удаление файла, если он не был скачан
            # через указанное время (FILE_UNUSED_TTL_MINUTES, по умолчанию 3 минуты)
            ttl_seconds = get_file_unused_ttl_seconds()
            asyncio.create_task(schedule_file_deletion(video_path, ttl_seconds))

            # Отправляем финальный статус об успешном завершении
            # Используем актуальное имя файла из пути
            websocket_message = {
                "status": "completed",
                "progress": 100,
                "message": f"Видео успешно скачано: {actual_filename}",
                "file_id": actual_filename,
                "file_path": actual_file_path,
            }
            print(f"DEBUG: Sending WebSocket message: {websocket_message}")
            await websocket.send_json(websocket_message)

        except ValueError as e:
            await websocket.send_json({
                "status": "error",
                "progress": None,
                "message": str(e)
            })
        except Exception as e:
            await websocket.send_json({
                "status": "error",
                "progress": None,
                "message": f"Ошибка при обработке запроса: {str(e)}"
            })

    except json.JSONDecodeError:
        await websocket.send_json({
            "status": "error",
            "progress": None,
            "message": "Неверный формат JSON в сообщении"
        })
    except WebSocketDisconnect:
        # Клиент отключился, это нормально
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "status": "error",
                "progress": None,
                "message": f"Неожиданная ошибка: {str(e)}"
            })
        except Exception:
            # WebSocket уже закрыт
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            # WebSocket уже закрыт
            pass
