from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from services.video_service import VideoService

router = APIRouter(prefix="/api/v1", tags=["video"])


@router.get("/")
async def root() -> dict[str, str]:
    """Корневой эндпоинт API."""
    return {"message": "RuTube Video Downloader API"}


@router.get("/download")
async def download_video(
    url: Annotated[str, Query(description="URL видео с RuTube")]
) -> StreamingResponse:
    """
    Скачивает видео с RuTube и возвращает его как поток.
    
    Args:
        url: URL видео с RuTube (например, https://rutube.ru/video/...)
    
    Returns:
        StreamingResponse с видеофайлом в формате MP4
    """
    video_service = VideoService()
    
    try:
        # Скачиваем видео через сервис
        video_path = await video_service.download_and_get_path(url)
        
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
            except Exception as e:
                # Если WebSocket закрыт, просто игнорируем ошибку
                pass
        
        # Создаем сервис и начинаем загрузку
        video_service = VideoService()
        
        try:
            # Скачиваем видео с отправкой статуса
            video_path = await video_service.download_and_get_path(url, status_callback)
            
            # Отправляем финальный статус об успешном завершении
            await websocket.send_json({
                "status": "completed",
                "progress": 100,
                "message": f"Видео успешно скачано: {video_path.name}",
                "file_path": str(video_path)
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

