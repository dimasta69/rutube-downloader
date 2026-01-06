# Установка на Nano Pi с OpenWrt

## Быстрый старт

### 1. Установка Docker на OpenWrt

```bash
opkg update
opkg install docker docker-compose
/etc/init.d/docker start
/etc/init.d/docker enable
```

### 2. Проверка архитектуры

```bash
uname -m
```

- `aarch64` - используйте `Dockerfile.arm` с `linux/arm64`
- `armv7l` - нужно изменить в `Dockerfile.arm` на `linux/arm/v7`

### 3. Клонирование проекта

```bash
cd /root  # или в другую директорию с достаточным местом
git clone <ваш-репозиторий> rutube-downloader
cd rutube-downloader
```

### 4. Создание .env файла

```bash
cat > .env << EOF
DOWNLOAD_PATH=/app/downloads
EOF
```

### 5. Сборка и запуск

```bash
# Сборка образа (может занять 10-30 минут на ARM)
docker-compose -f docker-compose.arm.yml build

# Запуск контейнера
docker-compose -f docker-compose.arm.yml up -d

# Просмотр логов
docker-compose -f docker-compose.arm.yml logs -f
```

### 6. Проверка работы

```bash
# Проверка статуса
docker ps

# Проверка доступности
curl http://localhost:8000
```

## Решение проблем

### Недостаточно места

```bash
# Проверка свободного места
df -h

# Очистка Docker
docker system prune -a
```

### Playwright не устанавливается

Если установка Chromium для Playwright не удается, можно попробовать:

1. Увеличить место на диске (минимум 3-4 GB)
2. Использовать более легковесную альтернативу (требует изменения кода)
3. Установить зависимости вручную:

```bash
docker exec -it rutube_app bash
cd /app
uv run playwright install chromium
```

### Медленная работа

- ARM процессоры работают медленнее x86_64
- Убедитесь, что устройство не перегружено другими процессами
- Рассмотрите возможность использования более мощной модели Nano Pi

### Проблемы с сетью

```bash
# Проверка DNS
ping 8.8.8.8

# Проверка доступа к интернету
curl https://rutube.ru
```

## Ограничения OpenWrt

- Ограниченная память: убедитесь, что у вас минимум 1-2 GB RAM
- Ограниченное место: минимум 3-4 GB свободного места
- Медленная работа: ARM процессоры работают медленнее

## Альтернативный вариант

Если Docker не подходит, можно запустить приложение напрямую на OpenWrt:

```bash
# Установка Python и зависимостей
opkg install python3 python3-pip

# Установка зависимостей проекта
pip3 install -r requirements.txt

# Запуск приложения
python3 app.py
```

Однако это может быть сложнее из-за ограничений OpenWrt и отсутствия некоторых системных библиотек.

