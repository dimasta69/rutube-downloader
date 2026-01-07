from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, StreamingResponse

from services.video_service import VideoService

router = APIRouter(prefix="/api/v1", tags=["video"])


@router.get("/")
async def root() -> dict[str, str]:
    """Корневой эндпоинт API."""
    return {"message": "RuTube Video Downloader API"}


@router.get("/download")
async def download_video(
    url: Annotated[str, Query(description="URL видео с RuTube")],
    file_name: Annotated[str | None, Query(description="Имя файла (без расширения, будет сохранено как .mp4)", default=None)] = None
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


@router.get("/file/{filename}")
async def get_downloaded_file(filename: str, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Возвращает ранее скачанный видеофайл по имени.
    
    Имя файла берется из ответа WebSocket (file_id) и ищется в той же
    директории, что используется сервисом загрузки.
    """
    # Используем ту же логику определения директории, что и в VideoService
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

    file_path = download_dir / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    # Настраиваем фоновой таск на удаление файла после отправки
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
            
            # Отправляем финальный статус об успешном завершении
            await websocket.send_json({
                "status": "completed",
                "progress": 100,
                "message": f"Видео успешно скачано: {video_path.name}",
                "file_id": video_path.name,
                "file_path": str(video_path),
            })
            
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
    
        