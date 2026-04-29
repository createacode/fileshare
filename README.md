# 局域网文件快速传输工具 - 完整开发文档

> 版本: 2.0.1  
> 最后更新: 2026-04-29  
> 作者: XAF
---
### 局域网文件快速传输助手 系统界面
![FileShareUI](https://raw.githubusercontent.com/createacode/fileshare/main/FileShareUI.png "系统界面截图")
---

## 目录

1. [项目概述](#1-项目概述)
2. [功能特性](#2-功能特性)
3. [技术栈](#3-技术栈)
4. [项目文件结构](#4-项目文件结构)
5. [安装与运行](#5-安装与运行)
6. [打包为 EXE](#6-打包为-exe)
7. [后端 API 文档](#7-后端-api-文档)
8. [前端模块说明](#8-前端模块说明)
9. [配置与自定义](#9-配置与自定义)
10. [常见问题](#10-常见问题)
11. [更新日志](#11-更新日志)

---

## 1. 项目概述

**局域网文件快速传输工具** 是一个基于 Web 的局域网文件共享与即时通讯系统。它利用 WebSocket 和分片上传技术，在局域网内实现极速文件传输（实测速度可达 300 MB/s 以上），支持断点续传、多文件并发、断网恢复、聊天室、下载计数、自动关闭等功能。

核心特点：
- 无需安装客户端，打开浏览器即可使用
- 支持 Windows / macOS / Linux 全平台
- 提供 PyInstaller 打包方案，可生成独立 EXE
- 内置二维码，手机扫码即连

---

## 2. 功能特性

### 文件传输
- **拖拽上传 / 点击上传**，支持多文件选择
- **分块上传**（1MB/块），防止大文件阻塞
- **断点续传下载**（自动处理 Range 请求）
- **文件打包下载**（ZIP，单次不超过 500MB）
- **批量化删除**选中的文件
- **本机快速复制**：直接复制本地文件到服务器（避免通过浏览器上传）
- **下载计数器**：记录每个文件的下载次数

### 聊天功能
- 全局聊天室（WebSocket 实时通信）
- 自动分配用户昵称（按 IP 生成 “用户1”、“用户2”……）
- 聊天历史持久化（每日单独文件）
- **消息删除**：下拉框内每条消息可永久删除（同步删除聊天记录文件）

### 房间管理
- 自动获取本机局域网 IP
- 生成房间二维码 (QR Code)
- 显示当前在线人数、文件总数、消息总数

### 系统维护
- **24 小时自动关闭**（可开关，默认开启）
- 日志系统（按天滚动，保留 30 天）
- 端口自动顺延（8888 → 8889 → … 直到空闲）

### UI/UX 改进（针对窄屏/手机）
- 窄屏下自动隐藏“全选/打包下载/删除选中”按钮
- 文件复选框左对齐垂直居中
- 文件名过长自动换行
- 文件图标放大并应用渐变色
- 刷新按钮增加按下动画

---

## 3. 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.8+，aiohttp，asyncio |
| 前端 | HTML5，CSS3，原生 JavaScript (ES6) |
| 实时通信 | WebSocket (aiohttp) |
| 文件处理 | aiofiles，shutil，zipfile |
| 二维码 | qrcode[pil] |
| 图标库 | Font Awesome 6.4.0 |
| 打包工具 | PyInstaller |

---

## 4. 项目文件结构

```
项目根目录/
├── main.py                     # 后端主程序 (Python)
├── FileTransferTool.spec       # PyInstaller 配置文件
├── app.ico                     # 程序图标 (根目录)
├── client/                     # 前端资源目录
│   ├── index.html              # 主页面
│   ├── style.css               # 样式表 (已适配窄屏)
│   ├── app.js                  # 前端逻辑 (含复制fallback、消息删除)
│   ├── all.min.css             # Font Awesome 主文件
│   └── webfonts/               # 字体文件
│       ├── fa-brands-400.woff2
│       ├── fa-regular-400.woff2
│       └── fa-solid-900.woff2
├── uploads/                    # 上传文件存储目录 (自动创建)
├── chat/                       # 聊天记录存储目录 (自动创建)
└── 日志/                       # 日志文件目录 (自动创建)
    └── file_transfer.log       # 按天滚动的日志文件
```

**说明**：
- `client/webfonts/` 和 `all.min.css` 来自 Font Awesome 6.4.0，已修改 CSS 中的字体路径为 `url(/client/webfonts/...)`。
- 运行时，`uploads/`、`chat/`、`日志/` 目录会创建在与 EXE 同级的目录下（开发环境下则与 `main.py` 同级）。
- `download_counts.json` 保存在 `uploads/` 中，记录每个文件的下载次数。

---

## 5. 安装与运行

### 5.1 开发环境运行

**前提**：Python 3.8+ 已安装。

1. **克隆/下载项目** 并进入根目录。
2. **安装依赖**：
   ```bash
   pip install aiohttp qrcode[pil] aiofiles
   ```
3. **运行**：
   ```bash
   python main.py
   ```
4. 控制台会输出本机访问地址（如 `http://localhost:8888`）和局域网访问地址，并自动打开浏览器。

### 5.2 生产环境运行（不打包）

与开发环境相同，确保依赖已安装，执行 `python main.py` 即可。可配合 `nohup` 或 `systemd` 实现后台运行。

---

## 6. 打包为 EXE

使用 **PyInstaller** 生成独立可执行文件，无需 Python 环境即可运行。

### 6.1 安装 PyInstaller

```bash
pip install pyinstaller
```

### 6.2 准备打包配置

确保项目根目录下存在 `FileTransferTool.spec`（已提供），且 `app.ico` 图标文件存在。

### 6.3 执行打包

```bash
pyinstaller FileTransferTool.spec
```

### 6.4 输出结果

- 打包后的 EXE 位于 `dist/FileTransferTool.exe`
- 首次运行会在 EXE 同级目录下自动创建 `uploads/`、`chat/`、`日志/` 文件夹

---

## 7. 后端 API 文档

### 7.1 通用信息

- 基础 URL：`http://<服务器IP>:<port>`
- 所有 API 返回 JSON 格式（文件下载除外）
- 字符编码：UTF-8

### 7.2 网页及静态资源

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` 或 `/index.html` | 返回主页面 |
| GET | `/client/*` | 静态资源（CSS、JS、图标等） |

### 7.3 房间信息与文件管理

| 方法 | 路径 | 描述 | 返回示例 |
|------|------|------|----------|
| GET | `/api/room-info` | 获取房间信息（含二维码、文件列表） | `{room_url, qr_code, total_files, total_clients, chat_messages, files, server_ip}` |
| GET | `/api/files` | 获取文件列表（下载链接） | `{files: [{id, name, size, modified, url, download_count}]}` |
| POST | `/api/upload` | 上传文件（multipart/form-data） | `{success, filename, size, url}` |
| GET | `/api/download/{file_id}` | 下载文件（支持断点续传） | 文件流 |
| DELETE | `/api/delete/{file_id}` | 删除文件 | `{success}` |
| POST | `/api/batch-delete` | 批量删除文件 | Body: `{files: ["a.txt","b.txt"]}` → `{deleted: [...]}` |
| POST | `/api/zip-download` | 打包下载选中文件（≤500MB） | Body: `{files: [...]}` → ZIP 流 |
| POST | `/api/local-copy` | 本机快速复制 | Body: `{file_path: "D:\\test.zip"}` → `{success, filename, size, url}` |

### 7.4 聊天功能

| 方法 | 路径 | 描述 | 返回示例 |
|------|------|------|----------|
| GET | `/api/chat/history` | 获取最近 50 条消息 | `{messages: [{id, message, client_name, client_ip, timestamp, time_str}]}` |
| POST | `/api/chat/send` | 发送文本消息 | Body: `{message: "hello"}` → `{success, message: {...}}` |
| DELETE | `/api/chat/message/{msg_id}` | 删除指定消息（永久删除） | `{success}` |
| GET | `/ws` | WebSocket 连接（实时聊天） | 详见 WebSocket 消息格式 |

### 7.5 系统设置

| 方法 | 路径 | 描述 | 返回示例 |
|------|------|------|----------|
| GET | `/api/auto-shutdown/status` | 获取自动关闭状态 | `{enabled, remain_seconds}` |
| POST | `/api/auto-shutdown` | 设置自动关闭开关 | Body: `{enable: true/false}` → `{status, remain_seconds}` |

### 7.6 WebSocket 消息格式

**连接后服务器发送**：
```json
{
  "type": "welcome",
  "client_id": "xxx",
  "client_name": "用户1",
  "chat_history": [...]   // 最近20条消息
}
```

**客户端发送**：
```json
{
  "type": "chat_message",
  "message": "文本内容"
}
```

**服务器广播**：
- 新消息：`{"type": "chat_message", "message": {...}}`
- 删除消息广播：`{"type": "delete_message", "message_id": "xxx"}`

---

## 8. 前端模块说明

前端为单页面应用 (`index.html`)，核心逻辑在 `app.js` 中。

### 8.1 主要类 `FileTransferApp`

负责：
- 文件上传/下载进度管理
- WebSocket 连接与消息收发
- 文件列表渲染与选择
- 下载计数本地存储（`localStorage`）
- 自动关闭倒计时
- 自定义确认对话框

### 8.2 关键函数

| 方法名 | 功能 |
|--------|------|
| `uploadFile(file)` | 使用 XMLHttpRequest 分块上传，实时更新进度 |
| `downloadFile(fileId, element)` | 流式下载，显示速度/剩余时间，完成后自动保存 |
| `copyToClipboard(text)` | 复制文本，自动降级（兼容非 HTTPS / 无网环境） |
| `deleteMessageFromBackend(msgId)` | 调用后端 API 删除消息，并更新界面 |
| `initAutoShutdown()` | 初始化自动关闭开关和倒计时 |
| `toggleSelectAll()` / `downloadZip()` / `batchDelete()` | 文件批量操作 |

### 8.3 样式适配 (`style.css`)

- **窄屏（≤768px）**：隐藏 `.file-toolbar .btn-secondary, .btn-primary, .btn-danger`
- **超窄屏（≤480px）**：调整内边距，文件元数据改为列布局
- **文件项**：`.file-item` 使用 `flex-wrap: wrap`，文件名 `word-break: break-all`
- **图标**：`.file-icon` 使用渐变文字，字号 36px
- **刷新按钮**：`.btn-refresh:active` 添加缩放效果

---

## 9. 配置与自定义

### 9.1 修改默认端口

在 `main.py` 的 `FileTransferServer` 初始化中修改 `port` 参数：
```python
server = FileTransferServer(port=9000)
```

### 9.2 修改自动关闭时长

修改 `shutdown_after_24h` 中的 `await asyncio.sleep(24 * 3600)` 中的数值（秒）。

### 9.3 修改文件上传分块大小

更改 `self.chunk_size = 1024 * 1024`（单位：字节）。

### 9.4 修改打包下载大小限制

在 `handle_zip_download` 方法中修改：
```python
if total_size > 500 * 1024 * 1024:   # 500 MB
```

### 9.5 日志级别

在 `main.py` 顶部修改：
```python
logger.setLevel(logging.DEBUG)   # 输出更详细日志
```

---

## 10. 常见问题

### Q1: 手机扫码后无法访问？
- 确保手机与电脑在同一局域网内。
- 检查电脑防火墙是否允许对应端口（默认 8888）入站。
- 尝试在电脑浏览器访问 `http://电脑IP:8888` 验证服务是否正常。

### Q2: 上传大文件时浏览器卡顿？
- 工具采用分块上传（1MB/块），理论上不会卡死。若遇到问题，请降低分块大小（如 512KB）。
- 建议使用现代浏览器（Chrome / Edge / Firefox）。

### Q3: 下载的文件损坏？
- 新版本已修复该问题（使用 `web.FileResponse` 替代了自定义生成器）。如仍有疑问，请检查网络稳定性，或查看日志文件。
- 确保磁盘空间充足。

### Q4: 聊天消息删除后刷新又出现？
- 新版本已实现后端真实删除，消息会从聊天记录文件中移除。请确保使用最新 `main.py` 并重启服务。

### Q5: 复制链接在无网环境下无效？
- 已增加 fallback 机制（临时 textarea + execCommand），即使没有 HTTPS 或 clipboard 权限也能复制。

### Q6: 如何停止服务器？
- 在控制台按 `Ctrl+C` 即可优雅关闭。若为 EXE，关闭命令行窗口即可。

### Q7: 打包后 EXE 报错 “No module named 'xxx'”？
- 检查 `FileTransferTool.spec` 中的 `hiddenimports` 是否包含所有依赖，重新打包。

---

## 11. 更新日志

### v2.0.1 (2026-04-29)
- 修复文件下载中断/损坏问题（改用 `web.FileResponse`）
- 增加详细控制台和文件日志输出（上传速度、下载断点、WebSocket 状态等）
- 添加聊天消息真实删除 API（`DELETE /api/chat/message/<id>`）
- 优化窄屏/手机端 CSS：
  - 隐藏多余工具栏按钮
  - 文件复选框左对齐居中
  - 文件名自动换行
  - 文件图标放大 + 渐变色
- 修复复制消息在无网环境下的 fallback
- 刷新按钮增加按下视觉效果

### v2.0.0 (2026-04-20)
- 初始稳定版发布
- 基于 WebSocket + 分片传输，支持断点续传
- 自动关闭、打包下载、本机复制等功能

---

## 附录：许可与致谢

- 本工具采用 MIT 协议开源。
- 感谢 `aiohttp`、`qrcode`、`Font Awesome` 等开源项目。
- 图标资源来自 Font Awesome 6.4.0。

**文档结束**
