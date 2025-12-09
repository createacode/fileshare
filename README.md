# 局域网互传工具

#### 介绍
一款局域网共享工具，传输文件极快，实测家用普通路由器，电脑向手机传输文件，理想速度可达127Mb/s以上，比数据线还快，同时还支持文字共享，使用简单双击exe即可运行，手机扫码加入


#### 软件架构
基于WebSocket协议+python+html


## 目录结构

```
fileshare/
├── main.py              # 主程序文件
├── client/              # 前端文件目录
│   ├── index.html      # 主页面
│   ├── style.css       # 样式文件
│   └── app.js          # 前端逻辑
├── uploads/            # 文件上传目录（运行时自动创建）
└── chat/               # 聊天记录目录（运行时自动创建）
```

---

## 技术栈

### 后端技术
- **Python 3.7+**
- **aiohttp**: 异步HTTP服务器和WebSocket支持
- **qrcode**: 二维码生成
- **PIL/Pillow**: 图像处理
- **asyncio**: 异步IO支持

### 前端技术
- **HTML5/CSS3**: 页面结构和样式
- **JavaScript (ES6)**: 前端交互逻辑
- **WebSocket**: 实时通信
- **Font Awesome**: 图标库

## 核心功能

### 1. 文件传输功能
- 拖拽上传和点击上传
- 断点续传支持
- 多文件同时上传
- 实时上传进度显示
- 下载速度显示
- 文件列表管理
- 文件链接复制

### 2. 文字共享功能
- 实时文字聊天
- 消息历史记录
- 用户自动分配
- IP地址识别
- 消息持久化存储

### 3. 网络功能
- 局域网IP自动发现
- 二维码分享
- WebSocket实时通信
- 端口自动检测
- 多客户端支持

### 4. 用户界面
- 响应式设计
- 实时状态显示
- 进度条动画
- 消息通知系统
- 暗色主题

---

## 详细API接口

### 1. 服务器信息接口
```http
GET /api/room-info
```
**响应格式：**
```json
{
  "room_url": "http://192.168.1.100:8888",
  "qr_code": "data:image/png;base64,...",
  "total_files": 5,
  "total_clients": 3,
  "chat_messages": 20,
  "files": [
    {
      "name": "example.jpg",
      "size": 1024000,
      "modified": 1634567890
    }
  ]
}
```

### 2. 文件列表接口
```http
GET /api/files
```
**响应格式：**
```json
{
  "files": [
    {
      "id": "example.jpg",
      "name": "example.jpg",
      "size": 1024000,
      "modified": 1634567890,
      "url": "/api/download/example.jpg"
    }
  ]
}
```

### 3. 文件上传接口
```http
POST /api/upload
```
**请求格式：** multipart/form-data
**响应格式：**
```json
{
  "success": true,
  "filename": "example.jpg",
  "size": 1024000,
  "url": "/api/download/example.jpg"
}
```

### 4. 文件下载接口
```http
GET /api/download/{filename}
```
支持Range头部，支持断点续传。

### 5. 文件删除接口
```http
DELETE /api/delete/{filename}
```

### 6. 聊天历史接口
```http
GET /api/chat/history
```
**响应格式：**
```json
{
  "messages": [
    {
      "id": "abc123def",
      "message": "Hello",
      "client_name": "用户1",
      "client_ip": "192.168.1.101",
      "timestamp": 1634567890,
      "time_str": "2023-10-20 14:30:00"
    }
  ]
}
```

### 7. 发送消息接口
```http
POST /api/chat/send
```
**请求格式：**
```json
{
  "message": "Hello World"
}
```

### 8. WebSocket接口
```http
WS /ws
```
**消息类型：**
- `welcome`: 连接欢迎消息
- `chat_message`: 聊天消息

---

## 数据存储格式

### 1. 聊天记录格式
```
{客户端IP} {日期时间}
{消息内容}

示例：
192.168.1.101 2023-10-20 14:30:00
大家好，开始传输文件吧！

192.168.1.102 2023-10-20 14:31:00
收到！
```

### 2. 文件存储
- 文件存储在`uploads/`目录下
- 使用原始文件名保存
- 不支持重名文件（后上传的会覆盖之前的）

### 3. 用户映射
- 用户按IP地址自动分配用户名
- 映射关系存储在内存中，重启后重置
- 格式：`{IP地址}: {用户名}`

---

### 端口占用处理逻辑
```python
# 端口自动递增算法
def find_available_port(start_port=8888, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        try:
            # 尝试绑定端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except OSError:
            continue
    return start_port
```

---

## 网络和安全考虑

### 1. 局域网限制
- 服务仅监听局域网接口
- 不支持外网访问
- 建议在受信任的网络环境中使用

### 2. 文件安全
- 不支持用户认证
- 所有连接用户具有相同权限
- 上传文件直接保存，无病毒扫描
- 建议定期清理上传目录

### 3. 资源限制
- 无文件大小限制
- 无用户连接数限制
- 无存储空间限制

### 4. 建议的安全措施
```python
# 可以添加的简单安全措施
class SecurityMiddleware:
    def check_request(self, request):
        # 限制文件类型
        allowed_extensions = {'.jpg', '.png', '.pdf', '.txt'}
        # 检查Referer
        # 限制上传频率
        pass
```
