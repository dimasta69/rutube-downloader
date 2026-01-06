#!/bin/bash
# Скрипт для загрузки кода на GitHub после создания репозитория

REPO_NAME="rutube-downloader"
GITHUB_USERNAME=""  # Замените на ваш username GitHub

echo "Настройка удаленного репозитория..."

# Проверяем, есть ли уже remote
if git remote get-url origin 2>/dev/null; then
    echo "Remote 'origin' уже настроен. Обновляем URL..."
    git remote set-url origin "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
else
    echo "Добавляем remote 'origin'..."
    git remote add origin "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
fi

# Переименовываем ветку в main (если нужно)
git branch -M main

# Загружаем код
echo "Загрузка кода на GitHub..."
git push -u origin main

echo "✅ Код успешно загружен на GitHub!"
echo "Репозиторий доступен по адресу: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"

