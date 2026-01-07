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
        const readyDownloadBtn = document.getElementById('readyDownloadBtn');

        form.addEventListener('submit', (e) => this.handleSubmit(e));
        closeStatusBtn.addEventListener('click', () => this.hideStatus());
        closeErrorBtn.addEventListener('click', () => this.hideError());

        // Кнопка скачивания готового файла настраивается динамически
        if (readyDownloadBtn) {
            readyDownloadBtn.style.display = 'none';
            readyDownloadBtn.onclick = null;
        }
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

        const fileNameInput = document.getElementById('fileName');
        const fileName = fileNameInput.value.trim();

        this.startDownload(url, fileName);
    }

    startDownload(url, fileName = null) {
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
            // Отправляем URL и имя файла для начала загрузки
            const message = { url };
            if (fileName) {
                message.file_name = fileName;
            }
            this.ws.send(JSON.stringify(message));
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // Сохраняем последнее сообщение для отладки
                window.lastWebSocketData = data;
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
        const { status, progress, message, file_id } = data;

        // Обновляем статус
        if (message) {
            this.updateStatus(message, progress || 0);
        }

        // Обновляем класс контейнера статуса
        const statusContainer = document.getElementById('statusContainer');
        statusContainer.className = `status-container status-${status}`;

        // Обрабатываем завершение или ошибку
        if (status === 'completed') {
            this.onDownloadComplete(file_id);
        } else if (status === 'error') {
            this.showError(message || 'Произошла ошибка при загрузке');
            this.resetState();
        }
    }

    onDownloadComplete(fileId) {
        this.updateStatus('Видео успешно скачано! Теперь вы можете его скачать.', 100);

        const readyDownloadBtn = document.getElementById('readyDownloadBtn');
        
        // Проверяем, есть ли fileId в последнем сообщении WebSocket
        const lastData = window.lastWebSocketData || {};
        
        // Используем fileId из параметра или из последнего сообщения
        let actualFileId = fileId || lastData.file_id;
        
        // Если file_id все еще не найден, пытаемся извлечь из message
        if (!actualFileId && lastData.message) {
            const messageMatch = lastData.message.match(/скачано:\s*([^\s]+\.mp4)/i);
            if (messageMatch) {
                actualFileId = messageMatch[1];
            }
        }
        
        if (readyDownloadBtn && actualFileId) {
            const downloadUrl = `/api/v1/file/${encodeURIComponent(actualFileId)}`;

            readyDownloadBtn.style.display = 'inline-block';
            readyDownloadBtn.onclick = async () => {
                try {
                    // Проверяем доступность файла перед скачиванием
                    const response = await fetch(downloadUrl, { method: 'HEAD' });
                    
                    if (response.status === 404) {
                        // Файл уже удален с сервера
                        this.showError('Файл уже был удален с сервера. Пожалуйста, начните загрузку заново.');
                        this.hideStatus();
                        readyDownloadBtn.style.display = 'none';
                        readyDownloadBtn.onclick = null;
                        return;
                    }
                    
                    if (!response.ok) {
                        throw new Error(`Ошибка сервера: ${response.status}`);
                    }
                    
                    // Если файл доступен, открываем прямую ссылку на скачивание
                    window.location.href = downloadUrl;
                } catch (error) {
                    console.error('Ошибка при попытке скачать файл:', error);
                    this.showError('Ошибка при попытке скачать файл. Файл может быть уже удален с сервера.');
                    this.hideStatus();
                    readyDownloadBtn.style.display = 'none';
                    readyDownloadBtn.onclick = null;
                }
            };
        }

        // Закрываем WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        // Сбрасываем состояние кнопки, но не скрываем статус и кнопку скачивания,
        // чтобы пользователь успел кликнуть по ссылке и видеть результат.
        this.isDownloading = false;
        this.setButtonLoading(false);
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
        
        const readyDownloadBtn = document.getElementById('readyDownloadBtn');
        if (readyDownloadBtn) {
            readyDownloadBtn.style.display = 'none';
            readyDownloadBtn.onclick = null;
        }
        
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

