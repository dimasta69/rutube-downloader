# Используем базовый образ Ubuntu
FROM ubuntu:22.04

# Устанавливаем Python 3.11 и необходимые инструменты
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Создаем символическую ссылку для python (python3 уже существует)
RUN ln -sf /usr/bin/python3.11 /usr/bin/python

# Устанавливаем системные зависимости для playwright и других инструментов
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
RUN uv run playwright install --with-deps chromium

# Открываем порт для FastAPI
EXPOSE 8000

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Запускаем приложение через uvicorn
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

