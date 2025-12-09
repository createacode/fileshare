import asyncio
import aiohttp
from aiohttp import web
import socket
import os
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
import sys

def resource_path(relative_path):
    """获取资源的绝对路径，适用于开发和打包后的环境"""
    try:
        # PyInstaller创建临时文件夹，存储在_MEIPASS中
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def find_available_port(start_port=8888, max_attempts=100):
    """查找可用的端口"""
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
    return start_port  # 如果找不到可用端口，返回起始端口

class FileTransferServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.clients = {}
        self.transfers = {}
        self.chat_history = []
        self.ip_to_name = {}  # 映射IP到用户名
        self.user_counter = 1  # 用户编号计数器
        self.app = web.Application()
        
        # 获取基础路径
        if getattr(sys, 'frozen', False):
            # 打包后exe的目录
            base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境
            base_dir = os.getcwd()
        
        # 资源目录路径
        if getattr(sys, 'frozen', False):
            # 打包后，静态文件在临时目录中
            self.resource_dir = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(base_dir)
        else:
            self.resource_dir = Path(base_dir)
        
        self.upload_dir = Path(base_dir) / 'uploads'
        self.chat_dir = Path(base_dir) / 'chat'
        self.upload_dir.mkdir(exist_ok=True)
        self.chat_dir.mkdir(exist_ok=True)
        
        # 聊天文件路径
        self.chat_file = self.chat_dir / f"chat_{datetime.now().strftime('%Y%m%d')}.txt"
        
        # 从文件加载历史聊天记录
        self.load_chat_history()
        
        self.setup_routes()
    
    def setup_routes(self):
        """设置路由"""
        try:
            # 静态文件路由 - 指向资源目录中的client文件夹
            client_path = self.resource_dir / 'client'
            if client_path.exists():
                self.app.router.add_static('/client/', path=str(client_path), name='client')
            
            # 主页面
            self.app.router.add_get('/', self.handle_index)
            self.app.router.add_get('/index.html', self.handle_index)
            
            # API接口
            self.app.router.add_get('/api/room-info', self.handle_room_info)
            self.app.router.add_get('/api/files', self.handle_list_files)
            self.app.router.add_post('/api/upload', self.handle_upload_chunk)
            self.app.router.add_get('/api/download/{file_id}', self.handle_download)
            self.app.router.add_delete('/api/delete/{file_id}', self.handle_delete)
            
            # 聊天API
            self.app.router.add_get('/api/chat/history', self.handle_chat_history)
            self.app.router.add_post('/api/chat/send', self.handle_chat_send)
            
            # 修复WebSocket路由
            self.app.router.add_route('GET', '/ws', self.handle_websocket)
            
            # 直接访问CSS和JS
            self.app.router.add_get('/style.css', self.handle_css)
            self.app.router.add_get('/app.js', self.handle_js)
            
        except Exception as e:
            print(f"设置路由时出错: {e}")
            raise
    
    async def handle_index(self, request):
        """返回主页面"""
        try:
            # 尝试多个可能的路径
            possible_paths = [
                self.resource_dir / 'client' / 'index.html',
                Path('client/index.html'),
                Path('./client/index.html'),
            ]
            
            for html_path in possible_paths:
                if html_path.exists():
                    return web.FileResponse(str(html_path))
            
            # 如果没有找到文件，返回内联HTML
            return await self.get_inline_html()
            
        except Exception as e:
            print(f"处理主页请求时出错: {e}")
            return await self.get_inline_html()
    
    async def get_inline_html(self):
        """获取内联HTML页面"""
        html = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>文件传输工具</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; color: #333; }
                .container { max-width: 1200px; margin: 0 auto; background: rgba(255, 255, 255, 0.95); min-height: 100vh; box-shadow: 0 0 40px rgba(0, 0, 0, 0.2); }
                header { background: linear-gradient(90deg, #2c3e50, #4a6491); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
                .logo { display: flex; align-items: center; gap: 15px; }
                .logo i { font-size: 32px; color: #4fc3f7; }
                .logo h1 { font-size: 24px; }
                .main-content { padding: 30px; text-align: center; }
                .error-message { background: #ffebee; color: #c62828; padding: 20px; border-radius: 10px; margin: 20px 0; }
                .success-message { background: #e8f5e9; color: #2e7d32; padding: 20px; border-radius: 10px; margin: 20px 0; }
                .loading { font-size: 18px; margin: 50px 0; }
                .fa-spin { animation: fa-spin 2s infinite linear; }
                @keyframes fa-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            </style>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        </head>
        <body>
            <div class="container">
                <header>
                    <div class="logo">
                        <i class="fas fa-exchange-alt"></i>
                        <h1>局域网文件传输</h1>
                    </div>
                </header>
                <div class="main-content">
                    <div class="loading">
                        <i class="fas fa-spinner fa-spin"></i>
                        <p>正在加载页面...</p>
                    </div>
                    <div class="error-message" style="display:none;" id="errorMsg">
                        <h3><i class="fas fa-exclamation-triangle"></i> 加载失败</h3>
                        <p>无法加载页面资源，请确保应用正常运行</p>
                    </div>
                </div>
            </div>
            <script>
                // 尝试加载CSS和JS
                setTimeout(function() {
                    document.getElementById('errorMsg').style.display = 'block';
                }, 3000);
            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    async def handle_css(self, request):
        """处理CSS文件"""
        try:
            # 尝试多个可能的路径
            possible_paths = [
                self.resource_dir / 'client' / 'style.css',
                Path('client/style.css'),
                Path('./client/style.css'),
            ]
            
            for css_path in possible_paths:
                if css_path.exists():
                    return web.FileResponse(str(css_path))
            
            # 如果没有找到文件，返回默认样式
            default_css = """
            /* 默认样式 */
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            """
            return web.Response(text=default_css, content_type='text/css')
            
        except Exception as e:
            print(f"处理CSS请求时出错: {e}")
            return web.Response(text='/* 错误 */', content_type='text/css')
    
    async def handle_js(self, request):
        """处理JS文件"""
        try:
            # 尝试多个可能的路径
            possible_paths = [
                self.resource_dir / 'client' / 'app.js',
                Path('client/app.js'),
                Path('./client/app.js'),
            ]
            
            for js_path in possible_paths:
                if js_path.exists():
                    return web.FileResponse(str(js_path))
            
            # 如果没有找到文件，返回空JS
            return web.Response(text='// JS未找到', content_type='application/javascript')
            
        except Exception as e:
            print(f"处理JS请求时出错: {e}")
            return web.Response(text='// 错误', content_type='application/javascript')
    
    async def handle_room_info(self, request):
        """获取房间信息"""
        try:
            local_ip = self.get_local_ip()
            room_url = f"http://{local_ip}:{self.port}"
            
            # 生成二维码
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(room_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            # 获取文件列表
            files = []
            for file_path in self.upload_dir.glob('*'):
                if file_path.is_file():
                    files.append({
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': file_path.stat().st_mtime
                    })
            
            return web.json_response({
                'room_url': room_url,
                'qr_code': f'data:image/png;base64,{qr_base64}',
                'total_files': len(files),
                'total_clients': len(self.clients),
                'chat_messages': len(self.chat_history),
                'files': files
            })
        except Exception as e:
            print(f"处理房间信息请求时出错: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_list_files(self, request):
        """获取文件列表"""
        try:
            files = []
            for file_path in self.upload_dir.glob('*'):
                if file_path.is_file():
                    files.append({
                        'id': file_path.name,
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': file_path.stat().st_mtime,
                        'url': f'/api/download/{file_path.name}'
                    })
            
            return web.json_response({'files': files})
        except Exception as e:
            print(f"处理文件列表请求时出错: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_upload_chunk(self, request):
        """处理文件上传"""
        try:
            reader = await request.multipart()
            file_field = await reader.next()
            
            if file_field is None:
                return web.json_response({'error': '没有文件'}, status=400)
            
            filename = file_field.filename
            file_id = hashlib.md5(f"{filename}{time.time()}".encode()).hexdigest()[:8]
            
            # 保存文件
            file_path = self.upload_dir / filename
            size = 0
            
            async with aiofiles.open(file_path, 'wb') as f:
                while True:
                    chunk = await file_field.read_chunk(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    await f.write(chunk)
                    size += len(chunk)
            
            return web.json_response({
                'success': True,
                'filename': filename,
                'size': size,
                'url': f'/api/download/{filename}'
            })
            
        except Exception as e:
            print(f"处理文件上传时出错: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_download(self, request):
        """处理文件下载"""
        try:
            file_id = request.match_info.get('file_id')
            file_path = self.upload_dir / file_id
            
            if not file_path.exists():
                return web.Response(text='文件不存在', status=404)
            
            # 支持断点续传
            headers = {
                'Content-Type': 'application/octet-stream',
                'Content-Disposition': f'attachment; filename="{file_id}"'
            }
            
            # 检查Range请求
            range_header = request.headers.get('Range')
            if range_header:
                # 解析Range头
                range_start, range_end = self.parse_range_header(range_header, file_path.stat().st_size)
                
                if range_start >= range_end:
                    return web.Response(status=416)  # Range Not Satisfiable
                
                headers['Content-Range'] = f'bytes {range_start}-{range_end-1}/{file_path.stat().st_size}'
                headers['Content-Length'] = str(range_end - range_start)
                headers['Accept-Ranges'] = 'bytes'
                
                async with aiofiles.open(file_path, 'rb') as f:
                    await f.seek(range_start)
                    chunk_size = 1024 * 1024  # 1MB chunks
                    data = b''
                    
                    remaining = range_end - range_start
                    while remaining > 0:
                        to_read = min(chunk_size, remaining)
                        chunk = await f.read(to_read)
                        if not chunk:
                            break
                        data += chunk
                        remaining -= len(chunk)
                    
                    return web.Response(
                        body=data,
                        headers=headers,
                        status=206  # Partial Content
                    )
            else:
                # 普通下载
                return web.FileResponse(file_path, headers=headers)
                
        except Exception as e:
            print(f"处理文件下载时出错: {e}")
            return web.Response(text='下载失败', status=500)
    
    def parse_range_header(self, range_header, file_size):
        """解析Range头"""
        try:
            if not range_header.startswith('bytes='):
                return (0, file_size)
            
            range_str = range_header[6:]
            if '-' not in range_str:
                return (0, file_size)
            
            start_str, end_str = range_str.split('-', 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size
            
            return (start, min(end, file_size))
        except:
            return (0, file_size)
    
    async def handle_delete(self, request):
        """删除文件"""
        try:
            file_id = request.match_info.get('file_id')
            file_path = self.upload_dir / file_id
            
            if file_path.exists():
                file_path.unlink()
                return web.json_response({'success': True})
            
            return web.json_response({'error': '文件不存在'}, status=404)
        except Exception as e:
            print(f"删除文件时出错: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # 聊天相关功能
    async def handle_chat_history(self, request):
        """获取聊天历史"""
        try:
            return web.json_response({
                'messages': self.chat_history[-50:]  # 返回最近50条消息
            })
        except Exception as e:
            print(f"获取聊天历史时出错: {e}")
            return web.json_response({'messages': []})
    
    async def handle_chat_send(self, request):
        """发送聊天消息"""
        try:
            data = await request.json()
            message = data.get('message', '').strip()
            client_ip = request.remote
            
            if not message:
                return web.json_response({'error': '消息不能为空'}, status=400)
            
            # 为IP分配用户名（按照发消息顺序）
            if client_ip not in self.ip_to_name:
                self.ip_to_name[client_ip] = f"用户{self.user_counter}"
                self.user_counter += 1
            
            client_name = self.ip_to_name[client_ip]
            
            # 创建消息对象
            chat_message = {
                'id': secrets.token_hex(8),
                'message': message,
                'client_name': client_name,
                'client_ip': client_ip,
                'timestamp': time.time(),
                'time_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 添加到历史记录
            self.chat_history.append(chat_message)
            
            # 保存到文件
            await self.save_chat_message(chat_message)
            
            # 广播给所有连接的客户端
            await self.broadcast_chat_message(chat_message)
            
            return web.json_response({
                'success': True,
                'message': chat_message
            })
            
        except Exception as e:
            print(f"发送聊天消息时出错: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_websocket(self, request):
        """WebSocket连接"""
        ws = web.WebSocketResponse()
        try:
            await ws.prepare(request)
            
            client_id = f"client_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            client_ip = request.remote
            
            # 为IP分配用户名（如果还没有分配）
            if client_ip not in self.ip_to_name:
                self.ip_to_name[client_ip] = f"用户{self.user_counter}"
                self.user_counter += 1
            
            client_name = self.ip_to_name[client_ip]
            
            self.clients[client_id] = {
                'ws': ws,
                'ip': client_ip,
                'name': client_name,
                'connected_at': time.time()
            }
            
            print(f"客户端 {client_id} 已连接 ({client_ip} - {client_name})")
            
            # 发送欢迎消息和聊天历史
            await ws.send_json({
                'type': 'welcome',
                'client_id': client_id,
                'client_name': client_name,
                'chat_history': self.chat_history[-20:]  # 发送最近20条消息
            })
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_websocket_message(client_id, data)
                    except json.JSONDecodeError:
                        print(f"无法解析JSON: {msg.data}")
                    except Exception as e:
                        print(f"处理WebSocket消息时出错: {e}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f'WebSocket错误: {ws.exception()}')
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    print(f'客户端 {client_id} 断开连接')
                    break
                    
        except Exception as e:
            print(f"WebSocket连接处理时出错: {e}")
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
                print(f"客户端 {client_id} 已断开连接")
        
        return ws
    
    async def handle_websocket_message(self, client_id, data):
        """处理WebSocket消息"""
        try:
            msg_type = data.get('type')
            
            if msg_type == 'chat_message':
                message = data.get('message', '').strip()
                if message:
                    client_info = self.clients.get(client_id, {})
                    
                    chat_message = {
                        'id': secrets.token_hex(8),
                        'message': message,
                        'client_name': client_info.get('name', '未知用户'),
                        'client_ip': client_info.get('ip', '未知IP'),
                        'timestamp': time.time(),
                        'time_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # 添加到历史记录
                    self.chat_history.append(chat_message)
                    
                    # 保存到文件
                    await self.save_chat_message(chat_message)
                    
                    # 广播给所有客户端
                    await self.broadcast_chat_message(chat_message)
        except Exception as e:
            print(f"处理WebSocket消息时出错: {e}")
    
    async def broadcast_chat_message(self, message):
        """广播聊天消息给所有客户端"""
        try:
            broadcast_data = {
                'type': 'chat_message',
                'message': message
            }
            
            disconnected_clients = []
            
            for client_id, client in self.clients.items():
                try:
                    await client['ws'].send_json(broadcast_data)
                except:
                    disconnected_clients.append(client_id)
            
            # 清理断开连接的客户端
            for client_id in disconnected_clients:
                if client_id in self.clients:
                    del self.clients[client_id]
        except Exception as e:
            print(f"广播聊天消息时出错: {e}")
    
    async def save_chat_message(self, message):
        """保存聊天消息到文件"""
        try:
            # 格式：ip 日期-时间(到秒)
            # xxxxxxx
            log_line = f"{message['client_ip']} {message['time_str']}\n{message['message']}\n\n"
            
            async with aiofiles.open(self.chat_file, 'a', encoding='utf-8') as f:
                await f.write(log_line)
                
        except Exception as e:
            print(f"保存聊天消息失败: {e}")
    
    def load_chat_history(self):
        """从文件加载聊天历史"""
        try:
            if self.chat_file.exists():
                with open(self.chat_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # 解析聊天记录
                for i in range(0, len(lines), 3):
                    if i + 2 < len(lines):
                        header = lines[i].strip()
                        message = lines[i+1].strip()
                        
                        if header and message:
                            # 解析头部信息
                            parts = header.split(' ', 1)
                            if len(parts) == 2:
                                ip, timestamp = parts
                                
                                # 为IP分配用户名（如果还没有分配）
                                if ip not in self.ip_to_name:
                                    self.ip_to_name[ip] = f"用户{self.user_counter}"
                                    self.user_counter += 1
                                
                                client_name = self.ip_to_name[ip]
                                
                                self.chat_history.append({
                                    'id': f"hist_{i}",
                                    'message': message,
                                    'client_ip': ip,
                                    'client_name': client_name,
                                    'timestamp': time.time() - (len(self.chat_history) * 10),
                                    'time_str': timestamp
                                })
                                
        except Exception as e:
            print(f"加载聊天历史失败: {e}")
    
    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            try:
                return socket.gethostbyname(socket.gethostname())
            except:
                return '127.0.0.1'
    
    def open_browser(self):
        """自动打开浏览器"""
        url = f"http://localhost:{self.port}"
        print(f"正在打开浏览器: {url}")
        
        try:
            if platform.system() == 'Windows':
                os.startfile(url)
            elif platform.system() == 'Darwin':  # macOS
                os.system(f'open "{url}"')
            else:  # Linux
                os.system(f'xdg-open "{url}"')
        except:
            print(f"请手动打开浏览器访问: {url}")
    
    async def run(self):
        """启动服务器"""
        try:
            # 查找可用端口
            self.port = find_available_port(self.port)
            
            runner = web.AppRunner(self.app)
            await runner.setup()
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
            
            local_ip = self.get_local_ip()
            
            print("\n" + "="*60)
            print("🚀 文件传输服务器已启动！")
            print("="*60)
            print(f"💻 本机访问: http://localhost:{self.port}")
            print(f"📱 手机访问: http://{local_ip}:{self.port}")
            print("="*60)
            print(f"📂 上传目录: {self.upload_dir.absolute()}")
            print(f"💬 聊天文件: {self.chat_file.absolute()}")
            print("💡 拖拽文件到网页即可上传，支持文字共享")
            print("="*60)
            
            self.open_browser()
            
            try:
                await asyncio.Future()  # 永久运行
            except KeyboardInterrupt:
                print("\n🛑 服务器正在关闭...")
            finally:
                await runner.cleanup()
                
        except Exception as e:
            print(f"❌ 启动服务器失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    # 确保目录存在
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.getcwd()
    
    uploads_dir = Path(base_dir) / 'uploads'
    chat_dir = Path(base_dir) / 'chat'
    
    uploads_dir.mkdir(exist_ok=True)
    chat_dir.mkdir(exist_ok=True)
    
    print("正在启动文件传输服务器...")
    
    try:
        server = FileTransferServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按Enter键退出...")
