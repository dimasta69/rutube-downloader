# PowerShell скрипт для загрузки кода на GitHub после создания репозитория

$REPO_NAME = "rutube-downloader"
$GITHUB_USERNAME = ""  # Замените на ваш username GitHub

Write-Host "Настройка удаленного репозитория..." -ForegroundColor Cyan

# Проверяем, есть ли уже remote
$remoteUrl = git remote get-url origin 2>$null
if ($remoteUrl) {
    Write-Host "Remote 'origin' уже настроен. Обновляем URL..." -ForegroundColor Yellow
    git remote set-url origin "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
} else {
    Write-Host "Добавляем remote 'origin'..." -ForegroundColor Green
    git remote add origin "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
}

# Переименовываем ветку в main (если нужно)
git branch -M main

# Загружаем код
Write-Host "Загрузка кода на GitHub..." -ForegroundColor Cyan
git push -u origin main

Write-Host "✅ Код успешно загружен на GitHub!" -ForegroundColor Green
Write-Host "Репозиторий доступен по адресу: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}" -ForegroundColor Green

