# Базовый образ для ARM архитектуры (Nano Pi)
# Используем Debian slim для меньшего размера образа
FROM --platform=linux/arm64 debian:bookworm-slim

# Устанавливаем Python 3 и необходимые инструменты
# Используем python3 из репозитория (обычно 3.11+ в Debian bookworm)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Создаем символическую ссылку для python
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Устанавливаем системные зависимости для playwright и других инструментов
# Для ARM архитектуры некоторые пакеты могут иметь другие имена
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем uv
RUN pip install --no-cache-dir uv

# Устанавливаем рабочую директорию
WORKDIR /app

# Создаем директорию для загрузок
RUN mkdir -p /app/downloads && chmod 777 /app/downloads

# Копируем все файлы проекта
COPY . .

# Синхронизируем зависимости с помощью uv
# Используем --frozen только если есть uv.lock
RUN if [ -f uv.lock ]; then uv sync --frozen; else uv sync; fi

# Устанавливаем браузеры для playwright
# Для ARM может потребоваться больше времени и места
RUN uv run playwright install --with-deps chromium || \
    (echo "Playwright install failed, trying without deps..." && \
     uv run playwright install chromium)

# Открываем порт для FastAPI
EXPOSE 8000

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Запускаем приложение через uvicorn
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

