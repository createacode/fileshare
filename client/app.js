class FileTransferApp {
    constructor() {
        this.uploads = new Map();
        this.currentUpload = null;
        this.roomInfo = null;
        this.ws = null;
        this.clientName = '等待分配...';
        this.messages = [];
        this.isHistoryVisible = false;
        
        this.init();
    }
    
    async init() {
        // 加载房间信息
        await this.loadRoomInfo();
        
        // 初始化WebSocket连接
        this.initWebSocket();
        
        // 设置事件监听器
        this.setupEventListeners();
        
        // 加载文件列表
        await this.loadFileList();
        
        // 开始定时刷新
        this.startAutoRefresh();
    }
    
    async loadRoomInfo() {
        try {
            const response = await fetch('/api/room-info');
            this.roomInfo = await response.json();
            
            // 更新界面
            document.getElementById('qrCode').src = this.roomInfo.qr_code;
            document.getElementById('roomUrl').textContent = this.roomInfo.room_url;
            document.getElementById('clientCount').textContent = this.roomInfo.total_clients || 0;
            document.getElementById('chatCount').textContent = this.roomInfo.chat_messages || 0;
            document.getElementById('fileCount').textContent = this.roomInfo.total_files || 0;
            
        } catch (error) {
            console.error('加载房间信息失败:', error);
            this.showMessage('无法连接到服务器', 'error');
        }
    }
    
    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket连接已建立');
            document.getElementById('status').textContent = '已连接';
            document.getElementById('sharedTextStatus').textContent = '已连接';
            this.showMessage('连接成功', 'success');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('解析WebSocket消息失败:', error);
            }
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket连接已关闭');
            document.getElementById('status').textContent = '连接断开，正在重连...';
            document.getElementById('sharedTextStatus').textContent = '连接断开';
            
            // 3秒后尝试重连
            setTimeout(() => {
                this.initWebSocket();
            }, 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket错误:', error);
            document.getElementById('status').textContent = '连接错误';
            document.getElementById('sharedTextStatus').textContent = '连接错误';
            this.showMessage('连接错误，正在重连...', 'error');
        };
    }
    
    handleWebSocketMessage(data) {
        try {
            switch (data.type) {
                case 'welcome':
                    this.clientName = data.client_name || '未知用户';
                    // 收到欢迎消息，显示聊天历史
                    if (data.chat_history) {
                        this.addChatHistory(data.chat_history);
                    }
                    break;
                    
                case 'chat_message':
                    // 收到新聊天消息
                    this.addMessage(data.message);
                    break;
            }
        } catch (error) {
            console.error('处理WebSocket消息时出错:', error);
        }
    }
    
    addChatHistory(messages) {
        try {
            // 清空当前消息
            this.messages = [];
            const historyContent = document.getElementById('historyContent');
            historyContent.innerHTML = '';
            
            // 添加历史消息
            messages.forEach(message => {
                this.addMessage(message, true);
            });
            
            // 更新最新消息显示
            if (messages.length > 0) {
                this.updateLatestMessage(messages[messages.length - 1]);
            }
            
        } catch (error) {
            console.error('添加聊天历史时出错:', error);
        }
    }
    
    addMessage(message, isHistory = false) {
        try {
            // 添加到消息数组
            this.messages.push(message);
            
            // 更新消息计数
            const chatCountElement = document.getElementById('chatCount');
            if (chatCountElement) {
                chatCountElement.textContent = parseInt(chatCountElement.textContent || 0) + 1;
            }
            
            // 更新最新消息显示
            this.updateLatestMessage(message);
            
            // 添加到历史列表（如果可见）
            if (this.isHistoryVisible || isHistory) {
                this.addMessageToHistory(message);
            }
            
            // 限制消息数量
            if (this.messages.length > 100) {
                this.messages.shift();
                // 更新历史列表
                if (this.isHistoryVisible) {
                    this.refreshHistoryList();
                }
            }
            
        } catch (error) {
            console.error('添加消息时出错:', error);
        }
    }
    
    updateLatestMessage(message) {
        try {
            const latestMessageDiv = document.getElementById('latestMessage');
            const timeStr = new Date(message.timestamp * 1000).toLocaleTimeString();
            
            latestMessageDiv.innerHTML = `
                <div class="latest-message-content">
                    <div class="latest-message-header">
                        <span class="latest-message-sender">${this.escapeHtml(message.client_name)}</span>
                        <span class="latest-message-time">${message.time_str || timeStr}</span>
                    </div>
                    <div class="latest-message-text">${this.escapeHtml(message.message)}</div>
                </div>
            `;
            
            // 添加淡入动画
            latestMessageDiv.style.animation = 'none';
            setTimeout(() => {
                latestMessageDiv.style.animation = 'fadeIn 0.5s ease-out';
            }, 10);
            
        } catch (error) {
            console.error('更新最新消息时出错:', error);
        }
    }
    
    addMessageToHistory(message) {
        try {
            const historyContent = document.getElementById('historyContent');
            const emptyHistory = historyContent.querySelector('.empty-history');
            
            if (emptyHistory) {
                emptyHistory.remove();
            }
            
            const template = document.getElementById('messageItemTemplate');
            const clone = template.content.cloneNode(true);
            const item = clone.querySelector('.message-item');
            
            const timeStr = new Date(message.timestamp * 1000).toLocaleTimeString();
            
            item.querySelector('.message-sender').textContent = message.client_name;
            item.querySelector('.message-time').textContent = message.time_str || timeStr;
            item.querySelector('.message-content').textContent = message.message;
            
            historyContent.appendChild(item);
            
            // 滚动到底部
            historyContent.scrollTop = historyContent.scrollHeight;
            
        } catch (error) {
            console.error('添加消息到历史时出错:', error);
        }
    }
    
    refreshHistoryList() {
        try {
            const historyContent = document.getElementById('historyContent');
            historyContent.innerHTML = '';
            
            if (this.messages.length === 0) {
                historyContent.innerHTML = '<div class="empty-history">暂无消息历史</div>';
                return;
            }
            
            this.messages.forEach(message => {
                this.addMessageToHistory(message);
            });
            
        } catch (error) {
            console.error('刷新历史列表时出错:', error);
        }
    }
    
    async loadFileList() {
        try {
            const response = await fetch('/api/files');
            const data = await response.json();
            
            const filesList = document.getElementById('filesList');
            
            if (data.files.length === 0) {
                filesList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-inbox"></i>
                        <p>暂无文件</p>
                        <p>上传文件后将显示在这里</p>
                    </div>
                `;
                return;
            }
            
            filesList.innerHTML = '';
            data.files.forEach(file => {
                this.addFileItem(file);
            });
            
        } catch (error) {
            console.error('加载文件列表失败:', error);
            this.showMessage('加载文件列表失败', 'error');
        }
    }
    
    addFileItem(file) {
        try {
            const template = document.getElementById('fileItemTemplate');
            const clone = template.content.cloneNode(true);
            const item = clone.querySelector('.file-item');
            
            // 设置文件信息
            item.dataset.fileId = file.id;
            item.querySelector('.file-name').textContent = file.name;
            item.querySelector('.file-size').textContent = this.formatFileSize(file.size);
            item.querySelector('.file-date').textContent = this.formatDate(file.modified);
            
            // 设置事件监听器
            const btnDownload = item.querySelector('.btn-download');
            const btnCopy = item.querySelector('.btn-copy');
            const btnDelete = item.querySelector('.btn-delete');
            
            btnDownload.addEventListener('click', () => this.downloadFile(file));
            btnCopy.addEventListener('click', () => this.copyFileLink(file));
            btnDelete.addEventListener('click', () => this.deleteFile(file.id));
            
            document.getElementById('filesList').appendChild(item);
            
        } catch (error) {
            console.error('添加文件项时出错:', error);
        }
    }
    
    setupEventListeners() {
        try {
            const uploadZone = document.getElementById('uploadZone');
            const fileInput = document.getElementById('fileInput');
            const refreshBtn = document.getElementById('refreshBtn');
            const sharedTextInput = document.getElementById('sharedTextInput');
            const sharedTextSendBtn = document.getElementById('sharedTextSendBtn');
            const toggleHistoryBtn = document.getElementById('toggleHistory');
            
            // 点击上传区域
            uploadZone.addEventListener('click', () => {
                fileInput.click();
            });
            
            // 选择文件
            fileInput.addEventListener('change', (e) => {
                this.handleFileSelect(e.target.files);
                fileInput.value = '';
            });
            
            // 拖放支持
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadZone.classList.add('dragover');
            });
            
            uploadZone.addEventListener('dragleave', () => {
                uploadZone.classList.remove('dragover');
            });
            
            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone.classList.remove('dragover');
                
                if (e.dataTransfer.files.length > 0) {
                    this.handleFileSelect(e.dataTransfer.files);
                }
            });
            
            // 刷新按钮
            refreshBtn.addEventListener('click', () => {
                this.loadFileList();
                this.showMessage('已刷新', 'info');
            });
            
            // 文字共享输入框回车发送
            sharedTextInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendSharedText();
                }
            });
            
            // 文字共享发送按钮
            sharedTextSendBtn.addEventListener('click', () => {
                this.sendSharedText();
            });
            
            // 切换历史显示
            toggleHistoryBtn.addEventListener('click', () => {
                this.toggleHistoryVisibility();
            });
            
        } catch (error) {
            console.error('设置事件监听器时出错:', error);
        }
    }
    
    toggleHistoryVisibility() {
        try {
            const historyContent = document.getElementById('historyContent');
            const toggleBtn = document.getElementById('toggleHistory');
            
            this.isHistoryVisible = !this.isHistoryVisible;
            
            if (this.isHistoryVisible) {
                historyContent.classList.add('active');
                toggleBtn.classList.add('active');
                toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
                
                // 刷新历史列表
                this.refreshHistoryList();
            } else {
                historyContent.classList.remove('active');
                toggleBtn.classList.remove('active');
                toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
            }
            
        } catch (error) {
            console.error('切换历史显示时出错:', error);
        }
    }
    
    async sendSharedText() {
        try {
            const sharedTextInput = document.getElementById('sharedTextInput');
            const message = sharedTextInput.value.trim();
            
            if (!message) {
                this.showMessage('消息不能为空', 'error');
                return;
            }
            
            // 清空输入框
            sharedTextInput.value = '';
            
            // 通过WebSocket发送消息
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'chat_message',
                    message: message
                }));
                
                // 暂时显示发送中的消息
                const tempMessage = {
                    id: 'temp_' + Date.now(),
                    message: message,
                    client_name: this.clientName,
                    client_ip: '正在发送...',
                    timestamp: Date.now() / 1000,
                    time_str: new Date().toLocaleTimeString()
                };
                
                this.updateLatestMessage(tempMessage);
                
            } else {
                // 如果WebSocket不可用，使用HTTP API
                const response = await fetch('/api/chat/send', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        message: message
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.addMessage(data.message);
                } else {
                    throw new Error('发送失败');
                }
            }
            
        } catch (error) {
            console.error('发送共享文字时出错:', error);
            this.showMessage('发送失败，请重试', 'error');
        }
    }
    
    async handleFileSelect(files) {
        try {
            for (const file of files) {
                await this.uploadFile(file);
            }
        } catch (error) {
            console.error('处理文件选择时出错:', error);
            this.showMessage('文件处理失败', 'error');
        }
    }
    
    async uploadFile(file) {
        const fileId = 'upload_' + Date.now();
        const startTime = Date.now();
        
        // 创建上传记录
        const upload = {
            id: fileId,
            file: file,
            progress: 0,
            uploaded: 0,
            total: file.size,
            startTime: startTime,
            chunks: [],
            status: 'uploading'
        };
        
        this.uploads.set(fileId, upload);
        
        // 添加文件项到列表
        const filesList = document.getElementById('filesList');
        const emptyState = filesList.querySelector('.empty-state');
        if (emptyState) emptyState.remove();
        
        const template = document.getElementById('fileItemTemplate');
        const clone = template.content.cloneNode(true);
        const item = clone.querySelector('.file-item');
        item.id = `upload-${fileId}`;
        
        item.querySelector('.file-name').textContent = file.name;
        item.querySelector('.file-size').textContent = this.formatFileSize(file.size);
        item.querySelector('.file-date').textContent = '上传中...';
        
        filesList.prepend(item);
        
        try {
            // 创建FormData
            const formData = new FormData();
            formData.append('file', file);
            
            // 创建XMLHttpRequest（支持进度监控）
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const progress = (e.loaded / e.total) * 100;
                    upload.progress = progress;
                    upload.uploaded = e.loaded;
                    
                    this.updateUploadProgress(fileId, progress, e.loaded, e.total);
                }
            });
            
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    upload.status = 'completed';
                    
                    // 更新UI
                    item.classList.add('completed');
                    item.querySelector('.progress-text').textContent = '100%';
                    item.querySelector('.file-date').textContent = '上传完成';
                    
                    // 重新加载文件列表
                    this.loadFileList();
                    
                    // 显示成功消息
                    this.showMessage(`文件 ${file.name} 上传成功`, 'success');
                    
                } else {
                    upload.status = 'error';
                    item.querySelector('.file-date').textContent = '上传失败';
                    this.showMessage(`文件 ${file.name} 上传失败`, 'error');
                }
            });
            
            xhr.addEventListener('error', () => {
                upload.status = 'error';
                item.querySelector('.file-date').textContent = '上传失败';
                this.showMessage(`文件 ${file.name} 上传失败`, 'error');
            });
            
            // 开始上传
            xhr.open('POST', '/api/upload');
            xhr.send(formData);
            
        } catch (error) {
            console.error('上传失败:', error);
            upload.status = 'error';
            item.querySelector('.file-date').textContent = '上传失败';
            this.showMessage(`文件 ${file.name} 上传失败: ${error.message}`, 'error');
        }
    }
    
    updateUploadProgress(fileId, progress, uploaded, total) {
        try {
            const item = document.getElementById(`upload-${fileId}`);
            if (!item) return;
            
            // 更新进度条
            item.querySelector('.progress-fill').style.width = `${progress}%`;
            item.querySelector('.progress-text').textContent = `${progress.toFixed(1)}%`;
            
            // 计算速度和剩余时间
            const upload = this.uploads.get(fileId);
            if (upload) {
                const elapsed = (Date.now() - upload.startTime) / 1000; // 秒
                const speed = elapsed > 0 ? uploaded / elapsed : 0; // bytes/s
                
                // 更新速度显示
                item.querySelector('.transfer-speed').textContent = this.formatSpeed(speed);
                
                // 更新总速度显示
                document.getElementById('uploadSpeed').textContent = this.formatSpeed(speed);
                
                if (speed > 0) {
                    const remaining = (total - uploaded) / speed;
                    document.getElementById('uploadTime').textContent = `${remaining.toFixed(1)}s`;
                }
            }
        } catch (error) {
            console.error('更新上传进度时出错:', error);
        }
    }
    
    async downloadFile(file) {
        try {
            // 使用Fetch API下载，支持断点续传
            const response = await fetch(file.url);
            
            if (!response.ok) {
                throw new Error(`下载失败: ${response.status}`);
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = file.name;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showMessage(`开始下载: ${file.name}`, 'success');
            
        } catch (error) {
            console.error('下载失败:', error);
            this.showMessage(`下载失败: ${error.message}`, 'error');
        }
    }
    
    copyFileLink(file) {
        try {
            const fullUrl = window.location.origin + file.url;
            navigator.clipboard.writeText(fullUrl)
                .then(() => {
                    this.showMessage('链接已复制到剪贴板', 'success');
                })
                .catch(err => {
                    console.error('复制失败:', err);
                    this.showMessage('复制失败', 'error');
                });
        } catch (error) {
            console.error('复制文件链接时出错:', error);
        }
    }
    
    async deleteFile(fileId) {
        try {
            if (!confirm('确定要删除这个文件吗？')) {
                return;
            }
            
            const response = await fetch(`/api/delete/${fileId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                // 从UI中移除
                const item = document.querySelector(`[data-file-id="${fileId}"]`);
                if (item) item.remove();
                
                this.showMessage('文件已删除', 'success');
                
                // 重新加载文件列表
                await this.loadFileList();
                
            } else {
                throw new Error('删除失败');
            }
        } catch (error) {
            console.error('删除失败:', error);
            this.showMessage('删除失败', 'error');
        }
    }
    
    formatFileSize(bytes) {
        try {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        } catch (error) {
            return '未知大小';
        }
    }
    
    formatSpeed(bytesPerSecond) {
        try {
            if (bytesPerSecond < 1024) {
                return bytesPerSecond.toFixed(0) + ' B/s';
            } else if (bytesPerSecond < 1024 * 1024) {
                return (bytesPerSecond / 1024).toFixed(1) + ' KB/s';
            } else {
                return (bytesPerSecond / (1024 * 1024)).toFixed(1) + ' MB/s';
            }
        } catch (error) {
            return '0 B/s';
        }
    }
    
    formatDate(timestamp) {
        try {
            const date = new Date(timestamp * 1000);
            return date.toLocaleString();
        } catch (error) {
            return '未知时间';
        }
    }
    
    escapeHtml(text) {
        try {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        } catch (error) {
            return text;
        }
    }
    
    showMessage(message, type = 'info') {
        try {
            // 移除现有的消息
            const existingMessages = document.querySelectorAll('.message-notification');
            existingMessages.forEach(msg => msg.remove());
            
            // 创建消息提示
            const messageEl = document.createElement('div');
            messageEl.className = `message-notification ${type}`;
            messageEl.textContent = message;
            
            // 添加到页面
            document.body.appendChild(messageEl);
            
            // 3秒后自动消失
            setTimeout(() => {
                messageEl.style.animation = 'slideOut 0.3s ease-out forwards';
                setTimeout(() => {
                    if (messageEl.parentNode) {
                        messageEl.parentNode.removeChild(messageEl);
                    }
                }, 300);
            }, 3000);
            
        } catch (error) {
            console.error('显示消息时出错:', error);
        }
    }
    
    startAutoRefresh() {
        // 每30秒刷新一次文件列表和房间信息
        setInterval(() => {
            try {
                this.loadFileList();
                this.loadRoomInfo();
            } catch (error) {
                console.error('自动刷新时出错:', error);
            }
        }, 30000);
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    try {
        window.app = new FileTransferApp();
    } catch (error) {
        console.error('启动应用时出错:', error);
        alert('应用启动失败，请刷新页面重试');
    }
});