class VideoDownloader {
    constructor() {
        this.ws = null;
        this.isDownloading = false;
        this.completedFileId = null; // Сохраняем file_id из сообщения со статусом "completed"
        this.init();
    }

    init() {
        const form = document.getElementById('downloadForm');
        const downloadByNameForm = document.getElementById('downloadByNameForm');
        const listFilesBtn = document.getElementById('listFilesBtn');
        const closeStatusBtn = document.getElementById('closeStatusBtn');
        const closeErrorBtn = document.getElementById('closeErrorBtn');
        const readyDownloadBtn = document.getElementById('readyDownloadBtn');

        form.addEventListener('submit', (e) => this.handleSubmit(e));
        if (downloadByNameForm) {
            downloadByNameForm.addEventListener('submit', (e) => this.handleDownloadByName(e));
        }
        if (listFilesBtn) {
            listFilesBtn.addEventListener('click', () => this.loadFilesList());
        }
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
                // Логируем для отладки
                if (data.status === 'completed') {
                    console.log('DEBUG: WebSocket completed message:', data);
                    console.log('DEBUG: file_id from WebSocket:', data.file_id);
                    // Сохраняем file_id из сообщения со статусом "completed" отдельно
                    // чтобы гарантировать использование правильного значения
                    this.completedFileId = data.file_id;
                }
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
            // Убеждаемся, что window.lastWebSocketData обновлен перед вызовом onDownloadComplete
            // Передаем весь объект data, чтобы гарантировать использование правильного file_id
            // из сообщения со статусом "completed"
            console.log('DEBUG: handleStatusUpdate - completed status, data:', data);
            console.log('DEBUG: handleStatusUpdate - file_id:', data.file_id);
            this.onDownloadComplete(data);
        } else if (status === 'error') {
            this.showError(message || 'Произошла ошибка при загрузке');
            this.resetState();
        }
    }

    onDownloadComplete(completedData) {
        this.updateStatus('Видео успешно скачано! Теперь вы можете его скачать.', 100);

        const readyDownloadBtn = document.getElementById('readyDownloadBtn');
        
        // Приоритет 1: Используем сохраненный file_id из сообщения со статусом "completed"
        // Это гарантирует использование правильного имени файла после переименования
        let actualFileId = this.completedFileId;
        
        console.log('DEBUG: onDownloadComplete called with:', completedData);
        console.log('DEBUG: this.completedFileId:', this.completedFileId);
        console.log('DEBUG: completedData.file_id:', completedData.file_id);
        
        // Приоритет 2: Если не сохранен, используем file_id из переданных данных
        if (!actualFileId) {
            actualFileId = completedData.file_id;
            console.log('DEBUG: using file_id from completedData:', actualFileId);
        }
        
        // Приоритет 3: Если file_id не найден в данных, пытаемся извлечь из message
        if (!actualFileId && completedData.message) {
            const messageMatch = completedData.message.match(/скачано:\s*([^\s]+\.mp4)/i);
            if (messageMatch) {
                actualFileId = messageMatch[1];
                console.log('DEBUG: extracted file_id from message:', actualFileId);
            }
        }
        
        // Приоритет 4: Если все еще не найдено, используем последние данные (fallback)
        if (!actualFileId) {
            const lastData = window.lastWebSocketData || {};
            actualFileId = lastData.file_id;
            console.log('DEBUG: using file_id from lastData (fallback):', actualFileId);
        }
        
        console.log('DEBUG: final actualFileId:', actualFileId);
        
        if (readyDownloadBtn && actualFileId) {
            const downloadUrl = `/api/v1/file/${encodeURIComponent(actualFileId)}`;
            console.log('DEBUG: downloadUrl:', downloadUrl);

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
        this.completedFileId = null; // Сбрасываем сохраненный file_id
        
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

    async handleDownloadByName(e) {
        e.preventDefault();
        
        const fileNameInput = document.getElementById('fileNameInput');
        const searchMode = document.getElementById('searchMode');
        const fileName = fileNameInput.value.trim();

        if (!fileName) {
            this.showError('Пожалуйста, введите имя файла');
            return;
        }

        try {
            let downloadUrl;
            if (searchMode && searchMode.checked) {
                // Используем поиск по частичному совпадению
                downloadUrl = `/api/v1/file/${encodeURIComponent(fileName)}?search=true`;
            } else {
                // Точное совпадение имени
                downloadUrl = `/api/v1/file/${encodeURIComponent(fileName)}`;
            }

            // Проверяем доступность файла перед скачиванием
            const response = await fetch(downloadUrl, { method: 'HEAD' });
            
            if (response.status === 404) {
                this.showError('Файл не найден. Проверьте имя файла или используйте поиск по частичному совпадению.');
                return;
            }
            
            if (!response.ok) {
                throw new Error(`Ошибка сервера: ${response.status}`);
            }
            
            // Если файл доступен, открываем прямую ссылку на скачивание
            window.location.href = downloadUrl;
        } catch (error) {
            console.error('Ошибка при попытке скачать файл:', error);
            this.showError('Ошибка при попытке скачать файл: ' + error.message);
        }
    }

    async loadFilesList() {
        const filesListContainer = document.getElementById('filesListContainer');
        const filesList = document.getElementById('filesList');
        
        try {
            filesList.innerHTML = '<p>Загрузка списка файлов...</p>';
            filesListContainer.style.display = 'block';
            
            const response = await fetch('/api/v1/files');
            
            if (!response.ok) {
                throw new Error(`Ошибка сервера: ${response.status}`);
            }
            
            const data = await response.json();
            const files = data.files || [];
            
            if (files.length === 0) {
                filesList.innerHTML = '<p>Нет доступных файлов</p>';
                return;
            }
            
            filesList.innerHTML = '';
            files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.style.cssText = 'padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;';
                
                const fileInfo = document.createElement('div');
                const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
                const fileAgeMinutes = Math.floor(file.age_seconds / 60);
                const fileAgeSeconds = Math.floor(file.age_seconds % 60);
                fileInfo.innerHTML = `
                    <strong>${file.name}</strong><br>
                    <small>Размер: ${fileSizeMB} MB | Возраст: ${fileAgeMinutes} мин ${fileAgeSeconds} сек</small>
                `;
                
                const downloadBtn = document.createElement('button');
                downloadBtn.className = 'btn btn-primary';
                downloadBtn.textContent = 'Скачать';
                downloadBtn.style.cssText = 'margin-left: 12px;';
                downloadBtn.onclick = () => {
                    window.location.href = `/api/v1/file/${encodeURIComponent(file.name)}`;
                };
                
                fileItem.appendChild(fileInfo);
                fileItem.appendChild(downloadBtn);
                filesList.appendChild(fileItem);
            });
        } catch (error) {
            console.error('Ошибка при загрузке списка файлов:', error);
            filesList.innerHTML = `<p style="color: red;">Ошибка при загрузке списка файлов: ${error.message}</p>`;
        }
    }
}

// Инициализируем приложение при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new VideoDownloader();
});


