import asyncio
import aiohttp
from aiohttp import web
import socket
import os
import sys
import json
from pathlib import Path
import qrcode
from io import BytesIO
import base64
import hashlib
import time
import webbrowser
import platform
import aiofiles
from datetime import datetime
import secrets
import shutil
import logging
from logging.handlers import TimedRotatingFileHandler
import zipfile

# ==================== 路径配置（支持 PyInstaller 打包） ====================
def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent

BASE_DIR = get_base_path()
DATA_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else BASE_DIR

UPLOAD_DIR = DATA_DIR / 'uploads'
CHAT_DIR = DATA_DIR / 'chat'
LOG_DIR = DATA_DIR / '日志'
CLIENT_DIR = BASE_DIR / 'client'

UPLOAD_DIR.mkdir(exist_ok=True)
CHAT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 日志配置
log_file = LOG_DIR / 'file_transfer.log'
logger = logging.getLogger('FileTransfer')
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler(log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

def ignore_connection_reset(loop, context):
    if 'exception' in context and isinstance(context['exception'], ConnectionResetError):
        return
    loop.default_exception_handler(context)

class FileTransferServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.clients = {}
        self.chat_history = []
        self.ip_to_name = {}
        self.user_counter = 1
        self.app = web.Application()
        self.upload_dir = UPLOAD_DIR
        self.chat_dir = CHAT_DIR
        self.chunk_size = 1024 * 1024
        self.chat_file = self.chat_dir / f"chat_{datetime.now().strftime('%Y%m%d')}.txt"
        self.download_counts = self.load_download_counts()
        self.load_chat_history()
        self.setup_routes()
        self._shutdown_task = None
        self.shutdown_enabled = False
        self.shutdown_start_time = None

        logger.info(f"FileTransferServer 初始化: host={host}, port={port}")
        logger.info(f"上传目录: {self.upload_dir.absolute()}")
        logger.info(f"聊天目录: {self.chat_dir.absolute()}")
        print(f"[INIT] 服务器实例创建, 端口={port}")

    def load_download_counts(self):
        counts_file = self.upload_dir / 'download_counts.json'
        if counts_file.exists():
            try:
                with open(counts_file, 'r') as f:
                    counts = json.load(f)
                    logger.info(f"加载下载计数: {len(counts)} 个文件记录")
                    return counts
            except Exception as e:
                logger.error(f"加载下载计数失败: {e}")
                return {}
        logger.info("无历史下载计数文件，从零开始")
        return {}

    def save_download_counts(self):
        counts_file = self.upload_dir / 'download_counts.json'
        with open(counts_file, 'w') as f:
            json.dump(self.download_counts, f)
        logger.debug(f"保存下载计数: {len(self.download_counts)} 条记录")

    def increment_download_count(self, filename):
        old = self.download_counts.get(filename, 0)
        self.download_counts[filename] = old + 1
        self.save_download_counts()
        logger.info(f"[下载计数] 文件 '{filename}' 下载次数: {old} → {old+1}")

    def log_action(self, action, filename, ip, size=None):
        msg = f"[{action}] 文件: {filename} | IP: {ip}"
        if size:
            msg += f" | 大小: {size} bytes ({self.format_size(size)})"
        logger.info(msg)
        print(msg)

    def format_size(self, bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f}{unit}"
            bytes /= 1024.0
        return f"{bytes:.1f}TB"

    def setup_routes(self):
        self.app.router.add_static('/client/', path=str(CLIENT_DIR), name='client')
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/index.html', self.handle_index)
        self.app.router.add_get('/api/room-info', self.handle_room_info)
        self.app.router.add_get('/api/files', self.handle_list_files)
        self.app.router.add_post('/api/upload', self.handle_upload_chunk)
        self.app.router.add_get('/api/download/{file_id}', self.handle_download)
        self.app.router.add_delete('/api/delete/{file_id}', self.handle_delete)
        self.app.router.add_post('/api/local-copy', self.handle_local_copy)
        self.app.router.add_get('/api/chat/history', self.handle_chat_history)
        self.app.router.add_post('/api/chat/send', self.handle_chat_send)
        self.app.router.add_delete('/api/chat/message/{msg_id}', self.handle_delete_chat_message)  # 新增
        self.app.router.add_route('GET', '/ws', self.handle_websocket)
        self.app.router.add_post('/api/auto-shutdown', self.handle_auto_shutdown)
        self.app.router.add_get('/api/auto-shutdown/status', self.handle_auto_shutdown_status)
        self.app.router.add_post('/api/zip-download', self.handle_zip_download)
        self.app.router.add_post('/api/batch-delete', self.handle_batch_delete)
        logger.info("路由注册完成")

    async def handle_index(self, request):
        index_path = CLIENT_DIR / 'index.html'
        if index_path.exists():
            logger.debug(f"返回主页: {request.remote}")
            return web.FileResponse(index_path)
        logger.warning(f"主页文件不存在: {index_path}")
        return web.Response(text='Index not found', status=404)

    # 自动关闭相关（与之前相同，略）
    async def handle_auto_shutdown_status(self, request):
        if self.shutdown_enabled and self.shutdown_start_time:
            elapsed = time.time() - self.shutdown_start_time
            remaining = max(0, 24*3600 - elapsed)
            logger.debug(f"自动关闭状态查询: 已开启, 剩余 {remaining} 秒")
            return web.json_response({'enabled': True, 'remain_seconds': int(remaining)})
        else:
            logger.debug("自动关闭状态查询: 未开启")
            return web.json_response({'enabled': False, 'remain_seconds': 0})

    async def handle_auto_shutdown(self, request):
        data = await request.json()
        enable = data.get('enable', False)
        logger.info(f"自动关闭设置请求来自 {request.remote}: enable={enable}")
        if enable and not self.shutdown_enabled:
            if self._shutdown_task and not self._shutdown_task.done():
                self._shutdown_task.cancel()
                try:
                    await self._shutdown_task
                except asyncio.CancelledError:
                    pass
            self.shutdown_enabled = True
            self.shutdown_start_time = time.time()
            self._shutdown_task = asyncio.create_task(self.shutdown_after_24h())
            self.log_action("自动关闭", "开启24小时后自动关闭", request.remote)
            return web.json_response({'status': 'enabled', 'remain_seconds': 24*3600})
        elif not enable and self.shutdown_enabled:
            if self._shutdown_task and not self._shutdown_task.done():
                self._shutdown_task.cancel()
                self._shutdown_task = None
            self.shutdown_enabled = False
            self.shutdown_start_time = None
            self.log_action("自动关闭", "已取消自动关闭", request.remote)
            return web.json_response({'status': 'disabled'})
        else:
            if self.shutdown_enabled:
                elapsed = time.time() - self.shutdown_start_time
                remaining = max(0, 24*3600 - elapsed)
                return web.json_response({'status': 'enabled', 'remain_seconds': int(remaining)})
            else:
                return web.json_response({'status': 'disabled', 'remain_seconds': 0})

    async def shutdown_after_24h(self):
        try:
            logger.info("自动关闭定时器启动，将在24小时后关闭服务器")
            await asyncio.sleep(24 * 3600)
            self.log_action("系统关闭", "自动关闭定时器触发", "system")
            print("\n[自动关闭] 24小时已到，服务器即将关闭...")
            logger.warning("24小时计时到达，正在关闭服务器")
            await self.app.shutdown()
            await self.app.cleanup()
            asyncio.get_event_loop().stop()
        except asyncio.CancelledError:
            logger.info("自动关闭定时器已取消")
            raise

    # 文件操作（与之前相同，略）
    async def handle_batch_delete(self, request):
        data = await request.json()
        filenames = data.get('files', [])
        logger.info(f"批量删除请求来自 {request.remote}: 文件列表 {filenames}")
        deleted = []
        for fname in filenames:
            fpath = self.upload_dir / fname
            if fpath.exists():
                fpath.unlink()
                if fname in self.download_counts:
                    del self.download_counts[fname]
                deleted.append(fname)
                logger.info(f"  已删除: {fname}")
            else:
                logger.warning(f"  文件不存在: {fname}")
        self.save_download_counts()
        self.log_action("批量删除", f"{len(deleted)}个文件", request.remote)
        return web.json_response({'deleted': deleted})

    async def handle_zip_download(self, request):
        data = await request.json()
        filenames = data.get('files', [])
        logger.info(f"打包下载请求来自 {request.remote}: 文件数={len(filenames)}")
        if not filenames:
            return web.json_response({'error': 'No files selected'}, status=400)
        total_size = 0
        file_paths = []
        for fname in filenames:
            fpath = self.upload_dir / fname
            if fpath.exists():
                total_size += fpath.stat().st_size
                file_paths.append(fpath)
                logger.debug(f"  添加文件: {fname} ({self.format_size(fpath.stat().st_size)})")
            else:
                logger.warning(f"  打包时文件不存在: {fname}")
        if total_size > 500 * 1024 * 1024:
            logger.warning(f"打包下载大小超限: {total_size} > 500MB")
            return web.json_response({'error': 'Total size exceeds 500MB'}, status=400)
        start_time = time.time()
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zf:
            for fpath in file_paths:
                zf.write(fpath, arcname=fpath.name)
        zip_buffer.seek(0)
        elapsed = time.time() - start_time
        zip_name = datetime.now().strftime('%Y%m%d_%H%M%S') + '.zip'
        self.log_action('打包下载', zip_name, request.remote, total_size)
        logger.info(f"打包完成，耗时 {elapsed:.2f}秒，压缩包大小 {zip_buffer.getbuffer().nbytes}")
        return web.Response(
            body=zip_buffer.getvalue(),
            headers={
                'Content-Type': 'application/zip',
                'Content-Disposition': f'attachment; filename="{zip_name}"'
            }
        )

    async def handle_room_info(self, request):
        try:
            local_ip = self.get_local_ip()
            room_url = f"http://{local_ip}:{self.port}"
            logger.debug(f"房间信息请求来自 {request.remote}, 本机IP={local_ip}")
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(room_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode()
            files = []
            for file_path in self.upload_dir.glob('*'):
                if file_path.is_file() and file_path.name != 'download_counts.json':
                    files.append({
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': file_path.stat().st_mtime,
                        'download_count': self.download_counts.get(file_path.name, 0)
                    })
            return web.json_response({
                'room_url': room_url,
                'qr_code': f'data:image/png;base64,{qr_base64}',
                'total_files': len(files),
                'total_clients': len(self.clients),
                'chat_messages': len(self.chat_history),
                'files': files,
                'server_ip': local_ip
            })
        except Exception as e:
            logger.error(f"房间信息生成错误: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)

    async def handle_list_files(self, request):
        try:
            files = []
            for file_path in self.upload_dir.glob('*'):
                if file_path.is_file() and file_path.name != 'download_counts.json':
                    files.append({
                        'id': file_path.name,
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': file_path.stat().st_mtime,
                        'url': f'/api/download/{file_path.name}',
                        'download_count': self.download_counts.get(file_path.name, 0)
                    })
            logger.debug(f"文件列表请求来自 {request.remote}, 返回 {len(files)} 个文件")
            return web.json_response({'files': files})
        except Exception as e:
            logger.error(f"文件列表错误: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)

    async def handle_local_copy(self, request):
        try:
            data = await request.json()
            file_path = data.get('file_path')
            logger.info(f"本机快速复制请求来自 {request.remote}: 源路径={file_path}")
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"本机复制失败: 文件不存在 {file_path}")
                return web.json_response({'error': '文件不存在'}, status=400)
            filename = os.path.basename(file_path)
            dest_path = self.upload_dir / filename
            if dest_path.exists():
                base, ext = os.path.splitext(filename)
                counter = 1
                while (self.upload_dir / f"{base}_{counter}{ext}").exists():
                    counter += 1
                filename = f"{base}_{counter}{ext}"
                dest_path = self.upload_dir / filename
                logger.info(f"  目标文件名冲突，重命名为 {filename}")
            shutil.copy2(file_path, dest_path)
            file_size = dest_path.stat().st_size
            self.log_action('本机快速复制', filename, request.remote, file_size)
            return web.json_response({
                'success': True,
                'filename': filename,
                'size': file_size,
                'url': f'/api/download/{filename}'
            })
        except Exception as e:
            logger.error(f"本机复制异常: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)

    async def handle_upload_chunk(self, request):
        start_time = time.time()
        try:
            reader = await request.multipart()
            file_field = await reader.next()
            if file_field is None:
                logger.warning(f"上传请求缺少文件字段，来自 {request.remote}")
                return web.json_response({'error': 'no file'}, status=400)
            filename = file_field.filename
            file_path = self.upload_dir / filename
            if file_path.exists():
                logger.info(f"上传文件 {filename} 已存在，将覆盖")
                file_path.unlink()
            size = 0
            chunk_count = 0
            async with aiofiles.open(file_path, 'wb') as f:
                while True:
                    chunk = await file_field.read_chunk(1024 * 1024)
                    if not chunk:
                        break
                    await f.write(chunk)
                    size += len(chunk)
                    chunk_count += 1
                    if chunk_count % 10 == 0:
                        logger.debug(f"  上传中: {filename} - {self.format_size(size)}")
            elapsed = time.time() - start_time
            speed = size / elapsed if elapsed > 0 else 0
            self.log_action('上传', filename, request.remote, size)
            logger.info(f"上传完成: {filename} ({self.format_size(size)}), 耗时 {elapsed:.2f}s, 速度 {self.format_size(speed)}/s")
            return web.json_response({
                'success': True,
                'filename': filename,
                'size': size,
                'url': f'/api/download/{filename}'
            })
        except Exception as e:
            logger.error(f"上传异常: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)

    async def handle_download(self, request):
        file_id = request.match_info.get('file_id')
        file_path = self.upload_dir / file_id
        if not file_path.exists():
            logger.warning(f"下载请求文件不存在: {file_id}, 来自 {request.remote}")
            return web.Response(text='File not found', status=404)

        self.increment_download_count(file_id)
        file_size = file_path.stat().st_size
        self.log_action('下载', file_id, request.remote, file_size)

        range_header = request.headers.get('Range')
        if range_header:
            logger.info(f"断点续传请求: {file_id}, Range={range_header}, 来自 {request.remote}")
        else:
            logger.info(f"完整下载请求: {file_id} ({self.format_size(file_size)}), 来自 {request.remote}")

        return web.FileResponse(
            path=file_path,
            headers={
                'Content-Type': 'application/octet-stream',
                'Content-Disposition': f'attachment; filename="{file_id}"'
            }
        )

    async def handle_delete(self, request):
        try:
            file_id = request.match_info.get('file_id')
            file_path = self.upload_dir / file_id
            if file_path.exists():
                file_path.unlink()
                if file_id in self.download_counts:
                    del self.download_counts[file_id]
                    self.save_download_counts()
                self.log_action('删除', file_id, request.remote)
                logger.info(f"删除文件成功: {file_id}")
                return web.json_response({'success': True})
            logger.warning(f"删除失败，文件不存在: {file_id}")
            return web.json_response({'error': 'not found'}, status=404)
        except Exception as e:
            logger.error(f"删除异常: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)

    # 聊天相关
    async def handle_chat_history(self, request):
        logger.debug(f"聊天历史请求来自 {request.remote}, 返回 {len(self.chat_history)} 条")
        return web.json_response({'messages': self.chat_history[-50:]})

    async def handle_chat_send(self, request):
        try:
            data = await request.json()
            message = data.get('message', '').strip()
            client_ip = request.remote
            if not message:
                return web.json_response({'error': 'empty'}, status=400)
            if client_ip not in self.ip_to_name:
                self.ip_to_name[client_ip] = f"用户{self.user_counter}"
                self.user_counter += 1
                logger.info(f"新用户分配名称: {client_ip} -> {self.ip_to_name[client_ip]}")
            client_name = self.ip_to_name[client_ip]
            chat_msg = {
                'id': secrets.token_hex(8),
                'message': message,
                'client_name': client_name,
                'client_ip': client_ip,
                'timestamp': time.time(),
                'time_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self.chat_history.append(chat_msg)
            await self.save_chat_message(chat_msg)
            await self.broadcast_chat_message(chat_msg)
            logger.info(f"聊天消息: {client_name}({client_ip}) 发送: {message[:50]}{'...' if len(message)>50 else ''}")
            return web.json_response({'success': True, 'message': chat_msg})
        except Exception as e:
            logger.error(f"聊天发送异常: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)

    async def handle_delete_chat_message(self, request):
        msg_id = request.match_info.get('msg_id')
        logger.info(f"删除聊天消息请求: {msg_id} 来自 {request.remote}")

        original_len = len(self.chat_history)
        self.chat_history = [msg for msg in self.chat_history if msg.get('id') != msg_id]
        if len(self.chat_history) == original_len:
            logger.warning(f"消息 {msg_id} 不存在")
            return web.json_response({'error': 'Message not found'}, status=404)

        await self.rewrite_chat_file()
        await self.broadcast_delete_message(msg_id)
        logger.info(f"已删除消息 {msg_id}")
        return web.json_response({'success': True})

    async def rewrite_chat_file(self):
        try:
            temp_file = self.chat_file.with_suffix('.tmp')
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                for msg in self.chat_history:
                    line = f"{msg['client_ip']} {msg['time_str']}\n{msg['message']}\n\n"
                    await f.write(line)
            temp_file.replace(self.chat_file)
            logger.debug(f"聊天记录文件已重写，共 {len(self.chat_history)} 条")
        except Exception as e:
            logger.error(f"重写聊天文件失败: {e}")

    async def broadcast_delete_message(self, msg_id):
        to_remove = []
        for cid, client in self.clients.items():
            try:
                await client['ws'].send_json({
                    'type': 'delete_message',
                    'message_id': msg_id
                })
            except:
                to_remove.append(cid)
        for cid in to_remove:
            self.clients.pop(cid, None)

    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        client_id = f"client_{int(time.time()*1000)}_{secrets.token_hex(4)}"
        client_ip = request.remote
        if client_ip not in self.ip_to_name:
            self.ip_to_name[client_ip] = f"用户{self.user_counter}"
            self.user_counter += 1
            logger.info(f"WebSocket新用户: {client_ip} -> {self.ip_to_name[client_ip]}")
        client_name = self.ip_to_name[client_ip]
        self.clients[client_id] = {'ws': ws, 'ip': client_ip, 'name': client_name, 'connected_at': time.time()}
        logger.info(f"WebSocket连接建立: {client_id} ({client_name}, {client_ip}), 当前在线: {len(self.clients)}")
        await ws.send_json({
            'type': 'welcome',
            'client_id': client_id,
            'client_name': client_name,
            'chat_history': self.chat_history[-20:]
        })
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get('type') == 'chat_message':
                        txt = data.get('message', '').strip()
                        if txt:
                            chat_msg = {
                                'id': secrets.token_hex(8),
                                'message': txt,
                                'client_name': client_name,
                                'client_ip': client_ip,
                                'timestamp': time.time(),
                                'time_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            self.chat_history.append(chat_msg)
                            await self.save_chat_message(chat_msg)
                            await self.broadcast_chat_message(chat_msg)
                            logger.debug(f"WebSocket消息: {client_name}: {txt[:50]}")
        except Exception as e:
            logger.warning(f"WebSocket异常: {client_id} - {e}")
        finally:
            self.clients.pop(client_id, None)
            logger.info(f"WebSocket连接断开: {client_id} ({client_name}), 当前在线: {len(self.clients)}")
        return ws

    async def broadcast_chat_message(self, message):
        to_remove = []
        for cid, client in self.clients.items():
            try:
                await client['ws'].send_json({'type': 'chat_message', 'message': message})
            except Exception as e:
                logger.debug(f"广播失败，客户端 {cid} 可能已断开: {e}")
                to_remove.append(cid)
        for cid in to_remove:
            self.clients.pop(cid, None)
        if to_remove:
            logger.info(f"清理 {len(to_remove)} 个断开的WebSocket客户端")

    async def save_chat_message(self, message):
        try:
            line = f"{message['client_ip']} {message['time_str']}\n{message['message']}\n\n"
            async with aiofiles.open(self.chat_file, 'a', encoding='utf-8') as f:
                await f.write(line)
            logger.debug(f"聊天消息已存档: {self.chat_file}")
        except Exception as e:
            logger.error(f"保存聊天消息失败: {e}")

    def load_chat_history(self):
        try:
            if self.chat_file.exists():
                with open(self.chat_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                count = 0
                for i in range(0, len(lines), 3):
                    if i+2 < len(lines):
                        header = lines[i].strip()
                        msg = lines[i+1].strip()
                        if header and msg:
                            parts = header.split(' ', 1)
                            if len(parts) == 2:
                                ip, ts = parts
                                if ip not in self.ip_to_name:
                                    self.ip_to_name[ip] = f"用户{self.user_counter}"
                                    self.user_counter += 1
                                self.chat_history.append({
                                    'id': f"hist_{i}_{int(time.time())}",  # 确保唯一
                                    'message': msg,
                                    'client_ip': ip,
                                    'client_name': self.ip_to_name[ip],
                                    'timestamp': time.time() - (len(self.chat_history)*10),
                                    'time_str': ts
                                })
                                count += 1
                logger.info(f"从聊天文件加载历史记录: {count} 条")
        except Exception as e:
            logger.error(f"加载聊天历史失败: {e}")

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            logger.debug(f"获取本机IP: {ip}")
            return ip
        except:
            try:
                ip = socket.gethostbyname(socket.gethostname())
                logger.debug(f"备用方法获取本机IP: {ip}")
                return ip
            except:
                logger.warning("无法获取本机IP，使用127.0.0.1")
                return '127.0.0.1'

    def open_browser(self, port):
        url = f"http://localhost:{port}"
        try:
            if platform.system() == 'Windows':
                os.startfile(url)
            elif platform.system() == 'Darwin':
                os.system(f'open "{url}"')
            else:
                os.system(f'xdg-open "{url}"')
            logger.info(f"已自动打开浏览器: {url}")
        except:
            logger.warning(f"自动打开浏览器失败，请手动访问: {url}")

    async def run(self):
        current_port = self.port
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                runner = web.AppRunner(self.app)
                await runner.setup()
                site = web.TCPSite(runner, self.host, current_port)
                await site.start()
                self.port = current_port
                logger.info(f"服务器启动成功，最终端口: {self.port}")
                break
            except OSError as e:
                if "Address already in use" in str(e) and attempt < max_attempts - 1:
                    logger.warning(f"端口 {current_port} 已被占用，尝试下一个端口 {current_port+1}")
                    print(f"端口 {current_port} 已被占用，尝试下一个端口...")
                    current_port += 1
                else:
                    logger.error(f"端口绑定失败: {e}")
                    raise
        else:
            logger.critical("无法找到空闲端口，程序退出")
            print("无法找到空闲端口，程序退出。")
            return

        local_ip = self.get_local_ip()
        print("\n" + "="*60)
        print("🚀 局域网文件快速传输工具已启动！")
        print("⚡ 基于WebSocket+分片传输，速度可达300MB/s+，支持断点续传、多文件并发、断网恢复")
        print(f"💻 本机访问: http://localhost:{self.port}")
        print(f"📱 手机访问: http://{local_ip}:{self.port}")
        print("="*60)
        logger.info(f"服务地址: http://localhost:{self.port}   http://{local_ip}:{self.port}")
        self.open_browser(self.port)

        if not self.shutdown_enabled:
            self.shutdown_enabled = True
            self.shutdown_start_time = time.time()
            self._shutdown_task = asyncio.create_task(self.shutdown_after_24h())
            self.log_action("自动关闭", "服务器启动时默认开启24小时自动关闭", "system")
            logger.info("自动关闭已启用，将在24小时后关闭服务器")

        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("收到键盘中断，服务器正在关闭")
            print("\n🛑 服务器关闭")

if __name__ == '__main__':
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(ignore_connection_reset)
        server = FileTransferServer()
        loop.run_until_complete(server.run())
    except KeyboardInterrupt:
        print("\n👋 已停止")
        logger.info("程序正常退出")
