class FileTransferApp {
    constructor() {
        this.uploads = new Map();
        this.downloads = new Map();
        this.ws = null;
        this.messages = [];
        this.isHistoryVisible = false;
        this.allFiles = new Map();
        this.downloadedFileIds = new Set();
        this.autoShutdownEnabled = false;
        this.countdownInterval = null;
        this.selectedFiles = new Set();
        this.loadDownloadedRecords();
        this.init();
    }

    loadDownloadedRecords() {
        const stored = localStorage.getItem('downloadedFiles');
        if (stored) this.downloadedFileIds = new Set(JSON.parse(stored));
    }

    saveDownloadedRecords() {
        localStorage.setItem('downloadedFiles', JSON.stringify(Array.from(this.downloadedFileIds)));
    }

    async init() {
        await this.loadRoomInfo();
        this.initWebSocket();
        this.setupEventListeners();
        await this.loadFileList();
        this.startAutoRefresh();
        this.initAutoShutdown();
        setInterval(() => this.syncAutoShutdownStatus(), 30 * 60 * 1000);
    }

    async loadRoomInfo() {
        try {
            const res = await fetch('/api/room-info');
            const data = await res.json();
            document.getElementById('qrCode').src = data.qr_code;
            document.getElementById('roomUrl').textContent = data.room_url;
            document.getElementById('clientCount').textContent = data.total_clients || 0;
            document.getElementById('chatCount').textContent = data.chat_messages || 0;
            document.getElementById('fileCount').textContent = data.total_files || 0;
        } catch (e) { console.error(e); }
    }

    initWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${location.host}/ws`;
        this.ws = new WebSocket(wsUrl);
        this.ws.onopen = () => {
            document.getElementById('status').textContent = '已连接';
            document.getElementById('sharedTextStatus').textContent = '已连接';
        };
        this.ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'welcome') {
                    if (data.chat_history) this.addChatHistory(data.chat_history);
                } else if (data.type === 'chat_message') {
                    this.addMessage(data.message);
                } else if (data.type === 'delete_message') {
                    // 收到删除消息广播，从本地删除
                    this.deleteMessageLocally(data.message_id);
                }
            } catch (err) { console.error(err); }
        };
        this.ws.onclose = () => {
            document.getElementById('status').textContent = '断开，重连中...';
            document.getElementById('sharedTextStatus').textContent = '断开';
            setTimeout(() => this.initWebSocket(), 3000);
        };
    }

    deleteMessageLocally(msgId) {
        this.messages = this.messages.filter(m => m.id !== msgId);
        const msgElement = document.querySelector(`.message-item[data-msg-id="${msgId}"]`);
        if (msgElement) msgElement.remove();
        const latestMsg = this.messages[this.messages.length - 1];
        if (latestMsg) this.updateLatestMessage(latestMsg);
        else document.getElementById('latestMessage').innerHTML = '<div class="message-placeholder">等待消息...</div>';
    }

    async deleteMessageFromBackend(msgId) {
        try {
            const res = await fetch(`/api/chat/message/${msgId}`, { method: 'DELETE' });
            if (res.ok) {
                this.deleteMessageLocally(msgId);
                this.showMessage('消息已删除', 'success');
            } else {
                this.showMessage('删除失败', 'error');
            }
        } catch (e) {
            console.error(e);
            this.showMessage('删除失败', 'error');
        }
    }

    addChatHistory(messages) {
        this.messages = [];
        const historyDiv = document.getElementById('historyContent');
        historyDiv.innerHTML = '';
        messages.forEach(msg => this.addMessage(msg, true));
        if (messages.length) this.updateLatestMessage(messages[messages.length - 1]);
    }

    addMessage(msg, isHistory = false) {
        this.messages.push(msg);
        this.updateLatestMessage(msg);
        if (this.isHistoryVisible || isHistory) this.addMessageToHistory(msg);
        const chatCount = document.getElementById('chatCount');
        chatCount.textContent = parseInt(chatCount.textContent) + 1;
        if (this.messages.length > 100) this.messages.shift();
    }

    updateLatestMessage(msg) {
        const container = document.getElementById('latestMessage');
        const time = new Date(msg.timestamp * 1000).toLocaleTimeString();
        container.innerHTML = `
            <div class="latest-message-content">
                <div class="latest-message-header">
                    <span class="latest-message-sender">${this.escapeHtml(msg.client_name)}</span>
                    <span class="latest-message-time">${msg.time_str || time}</span>
                    <button class="btn-copy-message" title="复制消息"><i class="fas fa-copy"></i></button>
                </div>
                <div class="latest-message-text">${this.escapeHtml(msg.message)}</div>
            </div>`;
        const copyBtn = container.querySelector('.btn-copy-message');
        copyBtn.addEventListener('click', () => {
            this.copyToClipboard(msg.message);
        });
    }

    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showMessage('已复制', 'success');
        } catch (err) {
            // fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            this.showMessage('已复制', 'success');
        }
    }

    addMessageToHistory(msg) {
        const historyDiv = document.getElementById('historyContent');
        const empty = historyDiv.querySelector('.empty-history');
        if (empty) empty.remove();
        const template = document.getElementById('messageItemTemplate');
        const clone = template.content.cloneNode(true);
        const item = clone.querySelector('.message-item');
        item.dataset.msgId = msg.id;
        const time = new Date(msg.timestamp * 1000).toLocaleTimeString();
        item.querySelector('.message-sender').textContent = msg.client_name;
        item.querySelector('.message-time').textContent = msg.time_str || time;
        item.querySelector('.message-content').textContent = msg.message;
        const delBtn = item.querySelector('.btn-msg-delete');
        delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.deleteMessageFromBackend(msg.id);
        });
        historyDiv.appendChild(item);
        historyDiv.scrollTop = historyDiv.scrollHeight;
    }

    async loadFileList() {
        try {
            const res = await fetch('/api/files');
            const data = await res.json();
            this.allFiles.clear();
            data.files.forEach(file => { this.allFiles.set(file.id, file); });
            const uploadedDiv = document.getElementById('uploadedFilesList');
            const uploadedFiles = data.files.filter(f => !this.downloadedFileIds.has(f.id));
            if (uploadedFiles.length === 0) {
                uploadedDiv.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>暂无文件</p></div>';
            } else {
                uploadedDiv.innerHTML = '';
                uploadedFiles.forEach(file => this.addUploadedFileItem(file));
            }
            const downloadedDiv = document.getElementById('downloadedFilesList');
            const downloadedFiles = data.files.filter(f => this.downloadedFileIds.has(f.id));
            if (downloadedFiles.length === 0) {
                downloadedDiv.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>暂无已下载文件</p></div>';
            } else {
                downloadedDiv.innerHTML = '';
                downloadedFiles.forEach(file => this.addDownloadedFileItem(file));
            }
            this.attachCheckboxEvents();
            this.updateCheckboxLimits();
        } catch (e) { console.error(e); }
    }

    attachCheckboxEvents() {
        const handler = (e) => {
            const cb = e.target;
            const fileId = cb.dataset.fileId;
            if (cb.checked) this.selectedFiles.add(fileId);
            else this.selectedFiles.delete(fileId);
            this.updateCheckboxLimits();
        };
        document.querySelectorAll('.file-checkbox').forEach(cb => {
            cb.removeEventListener('change', this.checkboxHandler);
            cb.addEventListener('change', handler);
            this.checkboxHandler = handler;
        });
    }

    updateCheckboxLimits() {
        let totalSize = 0;
        for (const id of this.selectedFiles) {
            const f = this.allFiles.get(id);
            if (f) totalSize += f.size;
        }
        const limit = 500 * 1024 * 1024;
        const zipHint = document.getElementById('zipLimitHint');
        const checkboxes = document.querySelectorAll('.file-checkbox');
        if (totalSize > limit) {
            checkboxes.forEach(cb => {
                const fileId = cb.dataset.fileId;
                if (!cb.checked) cb.disabled = true;
            });
            zipHint.textContent = `已超500MB限制，请取消部分文件`;
            zipHint.style.color = '#f44336';
        } else {
            checkboxes.forEach(cb => cb.disabled = false);
            zipHint.textContent = `限500MB以内 (当前${this.formatSize(totalSize)})`;
            zipHint.style.color = '';
        }
    }

    addUploadedFileItem(file) {
        const template = document.getElementById('fileItemTemplate');
        const clone = template.content.cloneNode(true);
        const item = clone.querySelector('.file-item');
        item.dataset.fileId = file.id;
        const checkbox = item.querySelector('.file-checkbox');
        checkbox.dataset.fileId = file.id;
        item.querySelector('.file-name').textContent = file.name;
        item.querySelector('.file-size').textContent = this.formatSize(file.size);
        item.querySelector('.file-date').textContent = new Date(file.modified * 1000).toLocaleString();
        item.querySelector('.download-count').innerHTML = `⬇️ ${file.download_count || 0}`;
        const downloadBtn = item.querySelector('.btn-download');
        downloadBtn.addEventListener('click', () => this.downloadFile(file.id, item));
        const copyBtn = item.querySelector('.btn-copy');
        copyBtn.addEventListener('click', () => this.copyLink(file.url));
        const deleteBtn = item.querySelector('.btn-delete');
        deleteBtn.addEventListener('click', () => this.confirmDelete(file.id));
        document.getElementById('uploadedFilesList').appendChild(item);
    }

    addDownloadedFileItem(file) {
        const template = document.getElementById('downloadedItemTemplate');
        const clone = template.content.cloneNode(true);
        const item = clone.querySelector('.file-item');
        item.dataset.fileId = file.id;
        item.querySelector('.file-name').textContent = file.name;
        item.querySelector('.file-size').textContent = this.formatSize(file.size);
        item.querySelector('.file-date').textContent = new Date(file.modified * 1000).toLocaleString();
        item.querySelector('.download-count').innerHTML = `⬇️ ${file.download_count || 0}`;
        const redownloadBtn = item.querySelector('.btn-redownload');
        redownloadBtn.addEventListener('click', () => this.downloadFile(file.id, item));
        const restoreBtn = item.querySelector('.btn-restore');
        restoreBtn.addEventListener('click', () => this.restoreFileFromDownloaded(file.id));
        const deleteBtn = item.querySelector('.btn-delete');
        deleteBtn.addEventListener('click', () => this.confirmDelete(file.id));
        document.getElementById('downloadedFilesList').appendChild(item);
    }

    async downloadFile(fileId, fileItemElement) {
        if (this.downloads.has(fileId)) {
            this.showMessage('已在下载中', 'info');
            return;
        }
        const fileInfo = this.allFiles.get(fileId);
        if (!fileInfo) return;
        const progressDiv = fileItemElement.querySelector('.download-progress');
        const progressFill = progressDiv.querySelector('.progress-fill');
        const progressText = progressDiv.querySelector('.progress-text');
        const speedSpan = fileItemElement.querySelector('.transfer-speed');
        const timeSpan = fileItemElement.querySelector('.transfer-time');
        progressDiv.style.display = 'flex';
        progressFill.style.width = '0%';
        progressText.textContent = '0%';
        speedSpan.textContent = '0 B/s';
        timeSpan.textContent = '--s';
        const startTime = Date.now();
        let downloaded = 0;
        const total = fileInfo.size;
        try {
            const response = await fetch(fileInfo.url);
            if (!response.ok) throw new Error('下载失败');
            const reader = response.body.getReader();
            const chunks = [];
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                chunks.push(value);
                downloaded += value.length;
                const percent = (downloaded / total) * 100;
                progressFill.style.width = `${percent}%`;
                progressText.textContent = `${percent.toFixed(1)}%`;
                const elapsed = (Date.now() - startTime) / 1000;
                const speed = elapsed > 0 ? downloaded / elapsed : 0;
                speedSpan.textContent = this.formatSpeed(speed);
                if (speed > 0) {
                    const remaining = (total - downloaded) / speed;
                    timeSpan.textContent = `${remaining.toFixed(1)}s`;
                }
            }
            const blob = new Blob(chunks);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileInfo.name;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            this.showMessage(`文件 ${fileInfo.name} 下载完成`, 'success');
            if (!this.downloadedFileIds.has(fileId)) {
                this.downloadedFileIds.add(fileId);
                this.saveDownloadedRecords();
                await this.loadFileList();
            }
        } catch (err) {
            console.error(err);
            this.showMessage(`下载失败: ${err.message}`, 'error');
        } finally {
            this.downloads.delete(fileId);
            progressDiv.style.display = 'none';
            speedSpan.textContent = '';
            timeSpan.textContent = '';
        }
    }

    restoreFileFromDownloaded(fileId) {
        this.downloadedFileIds.delete(fileId);
        this.saveDownloadedRecords();
        this.loadFileList();
        this.showMessage('已移回已上传列表', 'success');
    }

    confirmDelete(fileId) {
        this.showConfirm('确定要删除该文件吗？删除后不可恢复。', async () => {
            try {
                const res = await fetch(`/api/delete/${fileId}`, { method: 'DELETE' });
                if (res.ok) {
                    this.showMessage('文件已删除', 'success');
                    if (this.downloadedFileIds.has(fileId)) {
                        this.downloadedFileIds.delete(fileId);
                        this.saveDownloadedRecords();
                    }
                    this.loadFileList();
                } else throw new Error('删除失败');
            } catch (e) { this.showMessage('删除失败', 'error'); }
        });
    }

    copyLink(url) {
        const full = window.location.origin + url;
        this.copyToClipboard(full);
    }

    setupEventListeners() {
        const zone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');
        const refreshBtn = document.getElementById('refreshBtn');
        const sendBtn = document.getElementById('sharedTextSendBtn');
        const textInput = document.getElementById('sharedTextInput');
        const toggleHistoryBtn = document.getElementById('toggleHistory');
        const clearDownloadedBtn = document.getElementById('clearDownloadedBtn');
        const toggleSelectBtn = document.getElementById('toggleSelectBtn');
        const downloadZipBtn = document.getElementById('downloadZipBtn');
        const batchDeleteBtn = document.getElementById('batchDeleteBtn');

        zone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files));
        zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) this.handleFileSelect(e.dataTransfer.files);
        });
        refreshBtn.addEventListener('click', () => this.loadFileList());
        sendBtn.addEventListener('click', () => this.sendText());
        textInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') this.sendText(); });
        toggleHistoryBtn.addEventListener('click', () => {
            const content = document.getElementById('historyContent');
            const btn = document.getElementById('toggleHistory');
            this.isHistoryVisible = !this.isHistoryVisible;
            if (this.isHistoryVisible) {
                content.classList.add('active');
                btn.classList.add('active');
                btn.innerHTML = '<i class="fas fa-chevron-up"></i>';
                this.refreshHistoryList();
            } else {
                content.classList.remove('active');
                btn.classList.remove('active');
                btn.innerHTML = '<i class="fas fa-chevron-down"></i>';
            }
        });
        clearDownloadedBtn.addEventListener('click', () => this.clearDownloadedRecords());
        toggleSelectBtn.addEventListener('click', () => this.toggleSelectAll());
        downloadZipBtn.addEventListener('click', () => this.downloadZip());
        batchDeleteBtn.addEventListener('click', () => this.batchDelete());
    }

    refreshHistoryList() {
        const historyDiv = document.getElementById('historyContent');
        historyDiv.innerHTML = '';
        if (this.messages.length === 0) {
            historyDiv.innerHTML = '<div class="empty-history">暂无消息历史</div>';
            return;
        }
        this.messages.forEach(msg => this.addMessageToHistory(msg));
    }

    sendText() {
        const input = document.getElementById('sharedTextInput');
        const msg = input.value.trim();
        if (!msg) return;
        input.value = '';
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'chat_message', message: msg }));
        } else {
            fetch('/api/chat/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) })
                .catch(console.error);
        }
    }

    async handleFileSelect(files) {
        for (const file of Array.from(files)) {
            await this.uploadFile(file);
        }
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        const taskId = 'upload_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
        const upload = { id: taskId, file: file, xhr: null, startTime: Date.now() };
        this.uploads.set(taskId, upload);
        this.addUploadUI(taskId, file);
        const xhr = new XMLHttpRequest();
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                this.updateUploadProgress(taskId, percent, e.loaded, e.total);
            }
        });
        xhr.onload = () => {
            if (xhr.status === 200) {
                this.showMessage(`文件 ${file.name} 上传成功`, 'success');
                this.loadFileList();
            } else {
                this.showMessage(`文件 ${file.name} 上传失败`, 'error');
            }
            this.uploads.delete(taskId);
            const item = document.getElementById(`upload-${taskId}`);
            if (item) item.remove();
        };
        xhr.onerror = () => {
            this.showMessage(`文件 ${file.name} 上传失败`, 'error');
            this.uploads.delete(taskId);
        };
        xhr.open('POST', '/api/upload');
        xhr.send(formData);
        upload.xhr = xhr;
    }

    addUploadUI(taskId, file) {
        const listDiv = document.getElementById('uploadedFilesList');
        const empty = listDiv.querySelector('.empty-state');
        if (empty) empty.remove();
        const item = document.createElement('div');
        item.className = 'file-item';
        item.id = `upload-${taskId}`;
        item.innerHTML = `
            <div class="file-icon"><i class="fas fa-file"></i></div>
            <div class="file-info">
                <div class="file-name">${this.escapeHtml(file.name)}</div>
                <div class="file-meta"><span class="file-size">${this.formatSize(file.size)}</span><span class="file-date">上传中...</span></div>
                <div class="file-progress"><div class="progress-bar"><div class="progress-fill"></div></div><span class="progress-text">0%</span></div>
                <div class="transfer-info"><span class="transfer-speed"></span><span class="transfer-time"></span></div>
            </div>
            <div class="file-actions"><button class="btn-action btn-cancel"><i class="fas fa-times"></i></button></div>
        `;
        const cancelBtn = item.querySelector('.btn-cancel');
        cancelBtn.addEventListener('click', () => {
            const up = this.uploads.get(taskId);
            if (up && up.xhr) {
                up.xhr.abort();
                this.uploads.delete(taskId);
                item.remove();
                this.showMessage('上传已取消', 'info');
            }
        });
        listDiv.prepend(item);
    }

    updateUploadProgress(taskId, percent, loaded, total) {
        const item = document.getElementById(`upload-${taskId}`);
        if (!item) return;
        item.querySelector('.progress-fill').style.width = `${percent}%`;
        item.querySelector('.progress-text').textContent = `${percent.toFixed(1)}%`;
        const elapsed = (Date.now() - this.uploads.get(taskId).startTime) / 1000;
        const speed = elapsed > 0 ? loaded / elapsed : 0;
        item.querySelector('.transfer-speed').textContent = this.formatSpeed(speed);
        if (speed > 0) {
            const remaining = (total - loaded) / speed;
            item.querySelector('.transfer-time').textContent = `${remaining.toFixed(1)}s`;
        }
        document.getElementById('uploadSpeed').textContent = this.formatSpeed(speed);
        if (speed > 0) {
            const remaining = (total - loaded) / speed;
            document.getElementById('uploadTime').textContent = `${remaining.toFixed(1)}s`;
        }
    }

    toggleSelectAll() {
        const checkboxes = document.querySelectorAll('.file-checkbox:not(:disabled)');
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        if (allChecked) {
            checkboxes.forEach(cb => { cb.checked = false; this.selectedFiles.delete(cb.dataset.fileId); });
        } else {
            checkboxes.forEach(cb => { cb.checked = true; this.selectedFiles.add(cb.dataset.fileId); });
        }
        this.updateCheckboxLimits();
    }

    async downloadZip() {
        if (this.selectedFiles.size === 0) {
            this.showMessage('请至少选择一个文件', 'info');
            return;
        }
        const fileNames = Array.from(this.selectedFiles).map(id => this.allFiles.get(id).name);
        let totalSize = 0;
        for (const id of this.selectedFiles) totalSize += this.allFiles.get(id).size;
        if (totalSize > 500 * 1024 * 1024) {
            this.showMessage('所选文件总大小超过500MB，无法打包', 'error');
            return;
        }
        try {
            const response = await fetch('/api/zip-download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: fileNames })
            });
            if (!response.ok) throw new Error('打包失败');
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `files_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.zip`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            this.showMessage('打包下载已开始', 'success');
        } catch (e) {
            this.showMessage('打包失败: ' + e.message, 'error');
        }
    }

    async batchDelete() {
        if (this.selectedFiles.size === 0) {
            this.showMessage('请至少选择一个文件', 'info');
            return;
        }
        this.showConfirm(`确定要删除选中的 ${this.selectedFiles.size} 个文件吗？`, async () => {
            const fileNames = Array.from(this.selectedFiles).map(id => this.allFiles.get(id).name);
            try {
                const res = await fetch('/api/batch-delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ files: fileNames })
                });
                if (res.ok) {
                    this.showMessage('批量删除成功', 'success');
                    for (const id of this.selectedFiles) {
                        if (this.downloadedFileIds.has(id)) this.downloadedFileIds.delete(id);
                    }
                    this.saveDownloadedRecords();
                    this.selectedFiles.clear();
                    this.loadFileList();
                } else {
                    throw new Error('删除失败');
                }
            } catch (e) {
                this.showMessage('批量删除失败', 'error');
            }
        });
    }

    clearDownloadedRecords() {
        this.showConfirm('清空已下载记录不会删除实际文件，确定清空？', () => {
            this.downloadedFileIds.clear();
            this.saveDownloadedRecords();
            this.loadFileList();
            this.showMessage('已清空下载记录', 'success');
        });
    }

    async initAutoShutdown() {
        try {
            const res = await fetch('/api/auto-shutdown/status');
            const data = await res.json();
            const toggle = document.getElementById('autoShutdownToggle');
            if (data.enabled) {
                this.autoShutdownEnabled = true;
                this.startCountdown(data.remain_seconds);
                toggle.checked = true;
            } else {
                this.autoShutdownEnabled = false;
                document.getElementById('countdownDisplay').textContent = '未开启';
                toggle.checked = false;
            }
            const newToggle = toggle.cloneNode(true);
            toggle.parentNode.replaceChild(newToggle, toggle);
            newToggle.addEventListener('change', async () => {
                const enable = newToggle.checked;
                try {
                    const res = await fetch('/api/auto-shutdown', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enable })
                    });
                    const data = await res.json();
                    if (data.status === 'enabled') {
                        this.autoShutdownEnabled = true;
                        this.startCountdown(data.remain_seconds);
                    } else {
                        this.autoShutdownEnabled = false;
                        if (this.countdownInterval) clearInterval(this.countdownInterval);
                        document.getElementById('countdownDisplay').textContent = '未开启';
                    }
                } catch (e) { console.error(e); }
            });
        } catch (e) { console.error(e); }
    }

    async syncAutoShutdownStatus() {
        if (!this.autoShutdownEnabled) return;
        try {
            const res = await fetch('/api/auto-shutdown/status');
            const data = await res.json();
            if (data.enabled) {
                this.startCountdown(data.remain_seconds);
            }
        } catch (e) { console.error(e); }
    }

    startCountdown(seconds) {
        if (this.countdownInterval) clearInterval(this.countdownInterval);
        const countdownSpan = document.getElementById('countdownDisplay');
        const update = () => {
            if (seconds <= 0) {
                clearInterval(this.countdownInterval);
                countdownSpan.textContent = '已到期';
                return;
            }
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            countdownSpan.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            seconds--;
        };
        update();
        this.countdownInterval = setInterval(update, 1000);
    }

    showConfirm(message, onConfirm) {
        const modal = document.getElementById('customConfirm');
        const msgDiv = document.getElementById('confirmMessage');
        msgDiv.textContent = message;
        modal.style.display = 'flex';
        const yesBtn = document.getElementById('confirmYes');
        const noBtn = document.getElementById('confirmNo');
        noBtn.focus();
        const handleKeydown = (e) => {
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                yesBtn.focus();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                noBtn.focus();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                document.activeElement.click();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                close();
            }
        };
        const close = () => {
            modal.style.display = 'none';
            document.removeEventListener('keydown', handleKeydown);
            yesBtn.removeEventListener('click', handler);
            noBtn.removeEventListener('click', close);
        };
        const handler = () => {
            close();
            onConfirm();
        };
        yesBtn.addEventListener('click', handler);
        noBtn.addEventListener('click', close);
        document.addEventListener('keydown', handleKeydown);
    }

    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    formatSpeed(bps) {
        if (bps < 1024) return bps.toFixed(0) + ' B/s';
        if (bps < 1024 * 1024) return (bps / 1024).toFixed(1) + ' KB/s';
        return (bps / (1024 * 1024)).toFixed(1) + ' MB/s';
    }

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    showMessage(msg, type) {
        const el = document.createElement('div');
        el.className = 'message-notification';
        el.textContent = msg;
        if (type === 'error') el.style.background = '#f44336';
        else if (type === 'info') el.style.background = '#2196F3';
        else el.style.background = '#4CAF50';
        document.body.appendChild(el);
        setTimeout(() => {
            el.style.animation = 'slideOut 0.3s forwards';
            setTimeout(() => el.remove(), 300);
        }, 3000);
    }

    startAutoRefresh() {
        setInterval(() => { this.loadFileList(); this.loadRoomInfo(); }, 30000);
    }
}

document.addEventListener('DOMContentLoaded', () => { window.app = new FileTransferApp(); });