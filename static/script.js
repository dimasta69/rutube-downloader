class VideoDownloader {
    constructor() {
        this.ws = null;
        this.isDownloading = false;
        this.init();
    }

    init() {
        const form = document.getElementById('downloadForm');
        const closeStatusBtn = document.getElementById('closeStatusBtn');
        const closeErrorBtn = document.getElementById('closeErrorBtn');

        form.addEventListener('submit', (e) => this.handleSubmit(e));
        closeStatusBtn.addEventListener('click', () => this.hideStatus());
        closeErrorBtn.addEventListener('click', () => this.hideError());
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        if (this.isDownloading) {
            return;
        }

        const urlInput = document.getElementById('videoUrl');
        const url = urlInput.value.trim();

        if (!url) {
            this.showError('Пожалуйста, введите URL видео');
            return;
        }

        if (!url.includes('rutube.ru')) {
            this.showError('URL должен быть с сайта rutube.ru');
            return;
        }

        this.startDownload(url);
    }

    startDownload(url) {
        this.isDownloading = true;
        this.hideError();
        this.showStatus();
        this.setButtonLoading(true);
        this.updateStatus('Инициализация подключения...', 0);

        // Создаем WebSocket подключение
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/v1/download/status`;
        
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            // Отправляем URL для начала загрузки
            this.ws.send(JSON.stringify({ url }));
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleStatusUpdate(data);
            } catch (error) {
                console.error('Ошибка парсинга сообщения:', error);
                this.showError('Ошибка при получении статуса');
                this.resetState();
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket ошибка:', error);
            this.showError('Ошибка подключения к серверу');
            this.resetState();
        };

        this.ws.onclose = () => {
            // Если загрузка не завершена, возможно произошла ошибка
            if (this.isDownloading) {
                // Проверяем, была ли это нормальное закрытие после завершения
                // (это обработается в handleStatusUpdate)
            }
        };
    }

    handleStatusUpdate(data) {
        const { status, progress, message, file_path } = data;

        // Обновляем статус
        if (message) {
            this.updateStatus(message, progress || 0);
        }

        // Обновляем класс контейнера статуса
        const statusContainer = document.getElementById('statusContainer');
        statusContainer.className = `status-container status-${status}`;

        // Обрабатываем завершение или ошибку
        if (status === 'completed') {
            this.onDownloadComplete(file_path);
        } else if (status === 'error') {
            this.showError(message || 'Произошла ошибка при загрузке');
            this.resetState();
        }
    }

    onDownloadComplete(file_path) {
        this.updateStatus('Видео успешно скачано! Начинаем загрузку файла...', 100);
        
        // Скачиваем файл через обычный GET запрос
        const urlInput = document.getElementById('videoUrl');
        const videoUrl = urlInput.value.trim();
        const downloadUrl = `/api/v1/download?url=${encodeURIComponent(videoUrl)}`;
        
        // Создаем временную ссылку для скачивания
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Закрываем WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        // Через несколько секунд сбрасываем состояние
        setTimeout(() => {
            this.resetState();
            this.hideStatus();
            this.updateStatus('Готово к новой загрузке', 0);
        }, 3000);
    }

    updateStatus(message, progress) {
        const statusMessage = document.getElementById('statusMessage');
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');

        if (statusMessage) {
            statusMessage.textContent = message;
        }

        const progressValue = Math.round(progress || 0);
        
        if (progressFill) {
            progressFill.style.width = `${progressValue}%`;
        }

        if (progressText) {
            progressText.textContent = `${progressValue}%`;
        }
    }

    showStatus() {
        const statusContainer = document.getElementById('statusContainer');
        statusContainer.style.display = 'block';
    }

    hideStatus() {
        const statusContainer = document.getElementById('statusContainer');
        statusContainer.style.display = 'none';
    }

    showError(message) {
        const errorContainer = document.getElementById('errorContainer');
        const errorMessage = document.getElementById('errorMessage');
        
        errorMessage.textContent = message;
        errorContainer.style.display = 'block';
    }

    hideError() {
        const errorContainer = document.getElementById('errorContainer');
        errorContainer.style.display = 'none';
    }

    setButtonLoading(loading) {
        const btn = document.getElementById('downloadBtn');
        const btnText = btn.querySelector('.btn-text');
        const btnLoader = btn.querySelector('.btn-loader');

        if (loading) {
            btn.disabled = true;
            btnText.style.display = 'none';
            btnLoader.style.display = 'flex';
        } else {
            btn.disabled = false;
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    }

    resetState() {
        this.isDownloading = false;
        this.setButtonLoading(false);
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Инициализируем приложение при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new VideoDownloader();
});

