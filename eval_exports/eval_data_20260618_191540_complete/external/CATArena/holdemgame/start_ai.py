#!/usr/bin/env python3
"""
启动指定文件夹下所有AI的运行脚本
支持指定AI文件夹路径，每个子文件夹都是一个AI
使用 tmux 窗口管理服务
"""

import os
import argparse
import subprocess
import time
import logging
import socket
import threading
from flask import Flask, request, jsonify

def create_fallback_service_script(port, ai_name):
    """创建fallback服务脚本"""
    script_content = f'''#!/usr/bin/env python3
"""
Fallback服务 - 总是返回fold动作
为 {ai_name} 在端口 {port} 提供服务
"""

from flask import Flask, request, jsonify
import argparse

app = Flask(__name__)

@app.route('/action', methods=['POST'])
def get_action():
    game_state = request.get_json()
    valid_actions = game_state.get('valid_actions', [])
    
    # 总是返回fold动作
    fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)
    if fold_action:
        return jsonify(fold_action)
    else:
        # 如果没有fold动作，返回第一个可用动作
        return jsonify(valid_actions[0] if valid_actions else {{"action": "fold"}})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fallback AI HTTP Server")
    parser.add_argument('--port', type=int, default={port}, help='Port to listen on')
    args = parser.parse_args()
    
    print(f"启动Fallback服务 - {ai_name} 在端口 {{args.port}}")
    app.run(host='0.0.0.0', port=args.port)
'''
    
    # 创建临时脚本文件
    script_path = f"/tmp/fallback_{ai_name}_{port}.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # 设置执行权限
    os.chmod(script_path, 0o755)
    return script_path

def start_fallback_service_in_tmux(port, session_name, ai_name):
    """在tmux中启动fallback服务"""
    try:
        # 创建fallback服务脚本
        script_path = create_fallback_service_script(port, ai_name)
        
        # 创建fallback窗口名称
        fallback_window_name = f"{ai_name}_fallback"
        
        # 在tmux会话中创建新窗口运行fallback服务
        tmux_cmd = [
            'tmux', 'new-window', 
            '-t', session_name,
            '-n', fallback_window_name,
            'python3', script_path, '--port', str(port)
        ]
        
        subprocess.run(tmux_cmd, check=True)
        print(f"✓ Fallback服务已启动在tmux窗口: {session_name}:{fallback_window_name}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ 启动Fallback服务失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 启动Fallback服务异常: {e}")
        return False

def find_available_port(start_port):
    """查找可用端口（不kill端口服务，只找可用端口）"""
    port = start_port
    while port < 51999:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                s.close()  # 立即关闭socket，释放端口
                return port
        except OSError:
            port += 1
    raise RuntimeError("无法找到可用端口")

def is_port_in_use(port):
    """检查端口是否被使用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result == 0
    except:
        return False

def check_port_available(port, max_retries=3):
    """检查端口是否可用 - 只检查端口是否被监听"""
    for attempt in range(max_retries):
        try:
            # 检查端口是否被监听
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    return True
        except Exception as e:
            pass
        # 如果失败，等待后重试
        if attempt < max_retries - 1:
            time.sleep(2)
    return False

def create_tmux_session(session_name):
    """创建 tmux 会话"""
    try:
        # 检查会话是否已存在
        result = subprocess.run(['tmux', 'has-session', '-t', session_name], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"tmux 会话 '{session_name}' 已存在，正在终止...")
            # 终止现有会话
            subprocess.run(['tmux', 'kill-session', '-t', session_name], 
                          check=True, timeout=10)
            print(f"已终止现有会话: {session_name}")
        
        # 创建新会话
        subprocess.run(['tmux', 'new-session', '-d', '-s', session_name], 
                      check=True)
        print(f"创建新 tmux 会话: {session_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"创建 tmux 会话失败: {e}")
        return False
    except subprocess.TimeoutExpired:
        print(f"终止 tmux 会话超时，尝试强制终止...")
        try:
            # 强制终止会话
            subprocess.run(['tmux', 'kill-session', '-t', session_name, '-9'], 
                          check=True, timeout=5)
            # 重新创建会话
            subprocess.run(['tmux', 'new-session', '-d', '-s', session_name], 
                          check=True)
            print(f"强制终止后创建新 tmux 会话: {session_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"强制终止和重新创建 tmux 会话失败: {e}")
            return False

def start_ai_in_tmux(ai_path, port, session_name, ai_name):
    """在 tmux 窗口中启动单个AI"""
    start_script = os.path.join(ai_path, "start_ai.sh")
    
    print(f"启动 {ai_name} (端口: {port}) 在 tmux 窗口")
    print(f"启动脚本: {start_script}")
    
    # 检查启动脚本是否存在
    if not os.path.exists(start_script):
        print(f"✗ 启动脚本不存在: {start_script}")
        return False, "启动脚本不存在"
    
    try:
        # 创建 tmux 窗口名称（使用AI名称）
        window_name = ai_name
        
        # 在 tmux 会话中创建新窗口，先进入目录再运行启动脚本
        tmux_cmd = [
            'tmux', 'new-window', 
            '-t', session_name,
            '-n', window_name,
            '-c', ai_path,
            'bash', '-c', f'cd "{ai_path}" && bash start_ai.sh {port}'
        ]
        
        subprocess.run(tmux_cmd, check=True)
        
        # 等待一段时间让服务启动
        time.sleep(3)
        
        # 检查端口是否可用
        print(f"  正在检查 {ai_name} 的端口 {port}...")
        if check_port_available(port):
            print(f"✓ {ai_name} 启动成功 (端口 {port} 可用)")
            print(f"  tmux 窗口: {session_name}:{window_name}")
            return True, "启动成功"
        else:
            print(f"⚠ {ai_name} 启动脚本执行完成但端口 {port} 无活动，启动fallback服务...")
            # 启动fallback服务
            fallback_success = start_fallback_service_in_tmux(port, session_name, ai_name)
            time.sleep(3)  # 等待fallback服务启动
            
            # 再次检查端口
            if fallback_success and check_port_available(port):
                print(f"✓ {ai_name} fallback服务启动成功 (端口 {port} 可用)")
                print(f"  tmux 窗口: {session_name}:{window_name}")
                return True, "fallback服务启动成功"
            else:
                print(f"✗ {ai_name} fallback服务启动失败 (端口 {port} 不可用)")
                return False, "fallback服务启动失败"
            
    except subprocess.CalledProcessError as e:
        print(f"✗ {ai_name} 启动异常: {e}")
        return False, f"启动异常: {e}"
    except Exception as e:
        print(f"✗ {ai_name} 启动异常: {e}")
        return False, f"启动异常: {e}"

def list_tmux_windows(session_name):
    """列出 tmux 会话中的所有窗口"""
    try:
        result = subprocess.run(['tmux', 'list-windows', '-t', session_name], 
                              capture_output=True, text=True, check=True)
        print(f"\n{session_name} 会话中的窗口:")
        print(result.stdout)
    except subprocess.CalledProcessError:
        print(f"无法列出 {session_name} 会话的窗口")

def scan_ai_folders(ai_path):
    """扫描AI文件夹，返回所有AI子文件夹和错误路径"""
    ai_folders = []
    error_paths = []
    
    if not os.path.exists(ai_path):
        print(f"✗ AI文件夹路径不存在: {ai_path}")
        error_paths.append(f"AI文件夹路径不存在: {ai_path}")
        return ai_folders, error_paths
    
    if not os.path.isdir(ai_path):
        print(f"✗ 指定路径不是文件夹: {ai_path}")
        error_paths.append(f"指定路径不是文件夹: {ai_path}")
        return ai_folders, error_paths
    
    # 扫描所有子文件夹
    for item in os.listdir(ai_path):
        item_path = os.path.join(ai_path, item)
        if os.path.isdir(item_path):
            # 检查是否有start_ai.sh脚本
            start_script = os.path.join(item_path, "start_ai.sh")
            if os.path.exists(start_script):
                ai_folders.append((item, item_path))
                print(f"发现AI: {item} (路径: {item_path})")
            else:
                print(f"⚠ 跳过文件夹 {item} (缺少start_ai.sh脚本)")
                error_paths.append(f"缺少start_ai.sh脚本: {item_path}")
    
    return ai_folders, error_paths

def main():
    parser = argparse.ArgumentParser(description="启动指定文件夹下所有AI的运行脚本")
    parser.add_argument("path", type=str, help="AI文件夹路径（包含所有AI子文件夹）")
    parser.add_argument("tmux_name", type=str, help="tmux会话名称")
    parser.add_argument("--start_port", type=int, default=51000, help="起始端口号")
    parser.add_argument("--game_port", type=int, default=9010, help="游戏服务器端口")
    args = parser.parse_args()
    
    print(f"启动AI文件夹: {args.path}")
    print(f"tmux会话名称: {args.tmux_name}")
    print(f"起始端口: {args.start_port}")
    print("=" * 60)
    
    # 扫描AI文件夹
    ai_folders, error_paths = scan_ai_folders(args.path)
    
    if not ai_folders:
        print("✗ 未找到任何AI文件夹")
        if error_paths:
            print("\n错误路径:")
            for error_path in error_paths:
                print(f"  - {error_path}")
        return
    
    print(f"找到 {len(ai_folders)} 个AI文件夹")
    
    # 创建 tmux 会话
    if not create_tmux_session(args.tmux_name):
        print("无法创建 tmux 会话，退出")
        return
    
    # 启动所有AI
    current_port = args.start_port
    results = {}
    has_basic_errors = False
    
    for i, (ai_name, ai_path) in enumerate(ai_folders, 1):
        print(f"\n[{i}/{len(ai_folders)}] 处理 {ai_name}")
        print(f"路径: {ai_path}")
        
        # 查找可用端口
        try:
            port = find_available_port(current_port)
            current_port = port + 1
        except RuntimeError as e:
            print(f"错误: 无法为 {ai_name} 分配端口")
            results[ai_name] = (None, False, "端口分配失败")
            has_basic_errors = True
            continue
        
        # 启动AI
        success, message = start_ai_in_tmux(ai_path, port, args.tmux_name, ai_name)
        results[ai_name] = (port, success, message)
        
        # 检查是否有基础错误（文件不存在等）
        if not success and ("启动脚本不存在" in message or "启动异常" in message):
            has_basic_errors = True
    
    # 打印结果摘要
    print(f"\n{'='*60}")
    print("启动结果摘要")
    print(f"{'='*60}")
    
    success_count = 0
    for ai_name, (port, success, message) in results.items():
        status = "✓ 成功" if success else "✗ 失败"
        port_str = str(port) if port else "N/A"
        print(f"{ai_name:<25} | 端口: {port_str:<6} | {status}")
        if success:
            success_count += 1
    
    print(f"{'='*60}")
    print(f"总计: {len(results)} 个AI实例, 成功: {success_count} 个, 失败: {len(results) - success_count} 个")
    
    # 生成配置字典
    print(f"\n{'='*60}")
    print("生成配置文件")
    print(f"{'='*60}")
    
    # 检查是否有基础错误
    if has_basic_errors:
        print("✗ 检测到基础错误（文件不存在等），不保存config.json")
        print("错误详情:")
        for ai_name, (port, success, message) in results.items():
            if not success and ("启动脚本不存在" in message or "启动异常" in message):
                print(f"  - {ai_name}: {message}")
        if error_paths:
            print("扫描阶段错误:")
            for error_path in error_paths:
                print(f"  - {error_path}")
    else:
        # 只包含成功启动的AI
        ais_config = []
        for ai_name, (port, success, message) in results.items():
            if success and port:  # 只包含成功启动且有端口的AI
                config_entry = {
                    "ai_id": ai_name,
                    "ai_name": ai_name,
                    "port": port,
                    "description": f"{ai_name} AI"
                }
                ais_config.append(config_entry)
        
        # 按端口号排序
        ais_config.sort(key=lambda x: x["port"])
        
        root_path = os.path.dirname(os.path.abspath(__file__))
        # 创建完整的配置文件
        config_dict = {
            "game_server": {
                "url": f"http://localhost:{args.game_port}"
            },
            "tournament": {
                "max_players": 12,
                "blind_structure_file": os.path.join(root_path, "arena", "blind_structure.json"),
                "rounds": 100,
                "initial_chips": 2000,
                "max_hands_per_round": 720
            },
            "timeout": 3,
            "ais": ais_config
        }
        
        # 保存配置文件
        config_file_path = os.path.join(args.path, "config.json")
        try:
            import json
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            print(f"✓ 配置文件已保存: {config_file_path}")
            print(f"✓ 包含 {len(ais_config)} 个成功启动的AI")
        except Exception as e:
            print(f"✗ 保存配置文件失败: {e}")
    
    # 列出 tmux 窗口
    list_tmux_windows(args.tmux_name)
    
    print(f"\n使用以下命令连接到 tmux 会话:")
    print(f"tmux attach-session -t {args.tmux_name}")
    print(f"\n使用以下命令列出所有窗口:")
    print(f"tmux list-windows -t {args.tmux_name}")

if __name__ == "__main__":
    main()
