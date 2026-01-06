from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from routes.video import router as video_router

# Загружаем переменные окружения из .env файла
load_dotenv()

app = FastAPI(title="RuTube Video Downloader API")

# Подключаем статические файлы
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def read_root() -> FileResponse:
    """Главная страница приложения."""
    index_path = static_dir / "index.html"
    return FileResponse(index_path)


# Регистрация роутов
app.include_router(video_router)

