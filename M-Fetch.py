#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================================
Project     : M-Fetch (极简 M3U8 下载器)
Version     : 1.4.0
Description : A minimalist, ad-free, bilingual M3U8 & Streaming downloader 
              GUI based on N_m3u8DL-RE and FFmpeg.
Author      : Okqiyi (https://github.com/Nanobanana-AI/M-Fetch)
Copyright   : (c) 2026 Okqiyi. All rights reserved.
License     : MIT License
=============================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import subprocess
import os
import sqlite3
import re
import sys
import json             
import shutil
import random
import urllib.request
from datetime import datetime
import concurrent.futures
import webbrowser  
import locale
import pystray
from PIL import Image

# ==========================================
# --- 新增：Windows 任务栏进度条底层接口 ---
# ==========================================
import ctypes
from ctypes import wintypes
try:
    import comtypes.client
    
    # 定义任务栏进度条状态常量
    TBPF_NOPROGRESS = 0
    TBPF_INDETERMINATE = 1
    TBPF_NORMAL = 2
    TBPF_ERROR = 4
    TBPF_PAUSED = 8

    # 定义 ITaskbarList3 接口
    class ITaskbarList3(comtypes.IUnknown):
        _iid_ = comtypes.GUID('{ea1afb91-9e28-4b86-90e9-9e9f8a5eefaf}')
        _methods_ = [
            comtypes.COMMETHOD([], ctypes.HRESULT, 'HrInit'),
            comtypes.COMMETHOD([], ctypes.HRESULT, 'AddTab', (['in'], wintypes.HWND, 'hwnd')),
            comtypes.COMMETHOD([], ctypes.HRESULT, 'DeleteTab', (['in'], wintypes.HWND, 'hwnd')),
            comtypes.COMMETHOD([], ctypes.HRESULT, 'ActivateTab', (['in'], wintypes.HWND, 'hwnd')),
            comtypes.COMMETHOD([], ctypes.HRESULT, 'SetActiveAlt', (['in'], wintypes.HWND, 'hwnd')),
            comtypes.COMMETHOD([], ctypes.HRESULT, 'MarkFullscreenWindow', (['in'], wintypes.HWND, 'hwnd'), (['in'], wintypes.BOOL, 'fFullscreen')),
            comtypes.COMMETHOD([], ctypes.HRESULT, 'SetProgressValue', (['in'], wintypes.HWND, 'hwnd'), (['in'], ctypes.c_ulonglong, 'ullCompleted'), (['in'], ctypes.c_ulonglong, 'ullTotal')),
            comtypes.COMMETHOD([], ctypes.HRESULT, 'SetProgressState', (['in'], wintypes.HWND, 'hwnd'), (['in'], ctypes.c_int, 'tbpFlags')),
        ]
    comtypes.CoInitialize()
    taskbar = comtypes.client.CreateObject("{56FDF344-FD6D-11d0-958A-006097C9A090}", interface=ITaskbarList3)
    taskbar.HrInit()
    TASKBAR_AVAILABLE = True
except Exception:
    # 容错：如果系统不支持或没安装 comtypes，静默失败，不影响软件运行
    TASKBAR_AVAILABLE = False
    taskbar = None

# ==========================================
# --- 新增：双语字典与语言检测引擎 ---
# ==========================================
def get_sys_language():
    try:
        import os
        if os.name == 'nt':  # 完美规避警告，直接调用 Windows 底层 API
            import ctypes
            import locale
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            sys_lang = locale.windows_locale.get(lang_id, 'en_US')
        else:
            import locale
            sys_lang, _ = locale.getlocale()
        return 'zh_CN' if sys_lang and sys_lang.startswith('zh') else 'en_US'
    except:
        return 'en_US'

# 初始获取系统语言 (稍后会在 load_config 中被用户自定义设置覆盖)
LANG = get_sys_language()

UI_TEXT = {
    'zh_CN': {
        'title': "M-Fetch | 极简 M3U8 下载器 V1.4.0",
        'url_label': "下载地址:",
        'name_label': "保存文件:",
        'path_label': "保存路径:",
        'btn_select': "选择",
        'btn_open': "打开",
        'btn_dl': "立即下载",
        'chk_auto': "监听到链接后自动开始",
        'tab_dl': " 正在下载 ",
        'tab_ok': " 下载完成 ",
        'tab_fail': " 下载失败 ",
        'tab_set': " ⚙️ 高级设置 ",
        'tab_about': " 💡 关于 ",
        'col_id': "ID",
        'col_name': "文件名",
        'col_prog': "进度",
        'col_speed': "速度",
        'col_status': "状态",
        'col_size': "文件大小",
        'btn_start_all': "全部开始 ",
        'btn_clear_ok': "清空完成记录",
        'btn_resume_all': "全部断点续传",
        'btn_clear_fail': "清空失败记录",
        'set_max_workers': "最大并发任务数:",
        'set_thread_count': "单任务下载线程:",
        'set_timeout': "网络超时阀值(秒):",
        'set_retry': "失败重试次数:",
        'set_max_speed': "单任务限速 (Mbps, 0为不限):",  
        'set_file_handle': "文件处理 ",
        'set_skip_merge': "下载后保留原始 TS 分片 (不合并 MP4)",
        'set_network': "网络与请求 ",
        'set_headers': "自定义请求头:",
        'set_headers_hint': "(支持多行，User-Agent: iOS  Cookie: mycookie )",
        'set_proxy': "本地代理地址:",
        'set_proxy_enable': "启用",
        'set_rules': "启用同目录下的规则文件 (rules.json)",
        'set_language': "界面语言 (Language):",
        'lang_auto': "自动 (Auto)",
        'msg_restart': "语言设置已更改，请重启软件生效！\n(Language setting saved, please restart M-Fetch.)",
        'btn_reset': "恢复默认",
        'btn_save': "保存设置",
        'btn_pause_all': "全部暂停 ",
        'menu_pause': "⏸ 暂停下载",
        'status_paused': "已暂停",
        'about_desc': (
            "本软件为纯粹的效率工具，基于 N_m3u8DL-RE 强力内核构建。\n"
            "主打极简、秒开、无感后台运行与批量断点续传。\n"
            "【V1.4.0 核心升级】\n"
            "新增任务栏与托盘状态映射，内核同步升至 v0.6.0。\n"
            "如果您觉得这款工具为您节省了宝贵的时间，\n"
            "欢迎扫码请开发者喝杯咖啡 ☕ \n"
            "2026年07月01日"
        ),
        'about_github': "👉 访问 GitHub 获取最新源码与完整更新日志",
        'about_site': "🌐 访问作者官网：okqiyi.com",
        'about_qr_fail': "[请放置 donate.png]",
        'msg_confirm': "确认",
        'msg_reset': "确定要恢复到默认设置吗？\n(包含高级设置与默认下载路径)",
        'msg_tips': "提示",
        'msg_incomplete': "信息不完整！",
        'msg_open_fail': "打开失败",
        'msg_open_fail_detail': "无法打开该目录:\n",
        'msg_clear_confirm': "清理确认",
        'msg_clear_desc': "确定要清除列表记录吗？\n(仅清理软件记录，硬盘上的文件不会被删除)",
        'msg_success': "成功",
        'msg_save_ok': "设置已保存！\n(部分设置将在下一次任务生效)",
        'msg_error': "错误",
        'msg_number_err': "请确保并发、线程、超时等输入均为有效数字！",
        'status_wait': "等待中",
        'status_dl': "下载中",
        'status_fail': "失败",
        'status_repeat': "重复拦截",
        'status_resume': "正在恢复",
        'status_unknown': "未知",
        'status_kept': "分片已保留",
        'status_verify_fail': "校验失败/断流",
        'menu_start': "▶ 开始/继续下载",
        'menu_open_dir': "📂 打开所在文件夹",
        'menu_re_dl': "🔄 重新下载 (断点续传)",
        'dialog_sel_dir': "选择默认保存目录",
        'btn_merge_ts': "🧰 合并外部 TS 文件夹",
        'dialog_sel_ts': "请选择包含 TS 分片的文件夹",
        'msg_merge_none': "该文件夹下没有找到任何 .ts 文件！",
        'msg_merge_ok': "合并完成！\n已在原目录生成: ",
        'msg_merge_fail': "合并失败:\n",
        'set_ad_filter_title': "广告过滤 (Ad Filter)",
        'set_ad_filter': "跳过分片规则 (正则):",
        'set_ad_filter_hint': "(例如输入 ad|promo 自动丢弃带广告的 TS 切片)",
        'tray_restore': "显示主界面",
        'tray_quit': "完全退出",
        'tray_hover': "M-Fetch 后台运行中",
        'rules_hint': (
            '//进阶玩法: 请在软件同级目录自行新建 rules.json。\n'
            '//格式如下 (可直接复制修改):\n'
            '{\n'
            '    "网址1": {\n'
            '        "Origin": "https://www.网址.com",\n'
            '        "Referer": "https://www.网址.com/"\n'
            '    }\n'
            '}'
        )
    },
    'en_US': {
        'title': "M-Fetch | Minimalist M3U8 Downloader V1.4.0",
        'url_label': "Download URL:",
        'name_label': "File Name:",
        'path_label': "Save Path:",
        'btn_select': "Select",
        'btn_open': "Open",
        'btn_dl': "Download",
        'chk_auto': "Auto start when link detected",
        'tab_dl': " Downloading ",
        'tab_ok': " Completed ",
        'tab_fail': " Failed ",
        'tab_set': " ⚙️ Settings ",
        'tab_about': " 💡 About ",
        'col_id': "ID",
        'col_name': "File Name",
        'col_prog': "Progress",
        'col_speed': "Speed",
        'col_status': "Status",
        'col_size': "Size",
        'btn_start_all': "Start All ",
        'btn_clear_ok': "Clear History",
        'btn_resume_all': "Resume All",
        'btn_clear_fail': "Clear Failed",
        'set_max_workers': "Max Concurrent Tasks:",
        'set_thread_count': "Threads per Task:",
        'set_timeout': "Network Timeout (s):",
        'set_retry': "Retry Count:",
        'set_max_speed': "Per-Task Speed Limit (Mbps, 0=unlimited):", 
        'set_file_handle': "File Handling ",
        'set_skip_merge': "Keep original TS segments (Do not merge to MP4)",
        'set_network': "Network & Requests ",
        'set_headers': "Custom Headers:",
        'set_headers_hint': "(Multi-line supported, e.g., User-Agent: iOS)",
        'set_proxy': "Local Proxy:",
        'set_proxy_enable': "Enable",
        'set_rules': "Enable local rules file (rules.json)",
        'set_language': "Interface Language:",
        'lang_auto': "Auto Detect",
        'msg_restart': "Language setting saved, please restart M-Fetch to take effect!",
        'btn_reset': "Reset Default",
        'btn_save': "Save Config",
        'btn_pause_all': "Pause All ",
        'menu_pause': "⏸ Pause",
        'status_paused': "Paused",
        'about_desc': (
            "A minimalist, ad-free efficiency tool based on N_m3u8DL-RE.\n"
            "Features background running, batch downloading, and resumable tasks.\n"
            "[V1.4.0 Core Updates]\n"
            "Added Taskbar & Tray status mapping; Core updated to v0.6.0.\n"
            "If this tool saved your precious time,\n"
            "consider buying the developer a coffee ☕ \n"
            "July 01, 2026"
        ),
        'about_github': "👉 Visit GitHub for source code & updates",
        'about_site': "🌐 Official Website: okqiyi.com",
        'about_qr_fail': "[Missing donate.png]",
        'msg_confirm': "Confirm",
        'msg_reset': "Are you sure you want to reset to default settings?\n(Includes advanced settings and download path)",
        'msg_tips': "Notice",
        'msg_incomplete': "Incomplete information!",
        'msg_open_fail': "Open Failed",
        'msg_open_fail_detail': "Cannot open directory:\n",
        'msg_clear_confirm': "Clear Confirmation",
        'msg_clear_desc': "Are you sure you want to clear the list?\n(Only removes records, local files will NOT be deleted)",
        'msg_success': "Success",
        'msg_save_ok': "Settings saved!\n(Some settings will take effect on the next task)",
        'msg_error': "Error",
        'msg_number_err': "Please ensure concurrent, thread, and timeout inputs are valid numbers!",
        'status_wait': "Waiting",
        'status_dl': "Downloading",
        'status_fail': "Failed",
        'status_repeat': "Duplicated",
        'status_resume': "Resuming",
        'status_unknown': "Unknown",
        'status_kept': "Segments kept",
        'status_verify_fail': "Verify Failed/Broken",
        'menu_start': "▶ Start/Resume",
        'menu_open_dir': "📂 Open Folder",
        'menu_re_dl': "🔄 Restart (Resume)",
        'dialog_sel_dir': "Select Default Save Directory",
        'btn_merge_ts': "🧰 Merge External TS Folder",
        'dialog_sel_ts': "Select folder containing TS segments",
        'msg_merge_none': "No .ts files found in this directory!",
        'msg_merge_ok': "Merged successfully!\nSaved as: ",
        'msg_merge_fail': "Merge failed:\n",
        'set_ad_filter_title': "Ad Filtering",
        'set_ad_filter': "Skip Segments (Regex):",
        'set_ad_filter_hint': "(e.g., input ad|promo to drop ad TS segments)",
        'tray_restore': "Show Main Window",
        'tray_quit': "Quit M-Fetch",
        'tray_hover': "M-Fetch is running in background",
        'rules_hint': (
            '//Pro tip: Create rules.json in the same directory.\n'
            '//Format (copy and modify):\n'
            '{\n'
            '    "domain1": {\n'
            '        "Origin": "https://www.domain.com",\n'
            '        "Referer": "https://www.domain.com/"\n'
            '    }\n'
            '}'
        )
    }
}

def get_text(key):
    return UI_TEXT.get(LANG, UI_TEXT['en_US']).get(key, "")
# ==========================================

def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境与 PyInstaller 打包后的单文件环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class M3U8TaskApp:
    def __init__(self, root):
        self.root = root
        
        # --- 核心修复：必须先加载配置（确定最终语言），再去渲染带文字的组件 ---
        self.load_config()
        
        self.root.title(get_text('title'))
        self.root.geometry("620x500")
        self.root.resizable(False, False)
        # --- 新增：设置窗口左上角的 Logo ---
        try:
            self.root.iconbitmap(resource_path("logo.ico"))
        except:
            pass
        
        # 核心设置：改由配置文件接管
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.config.get("max_workers", 10))
        
        self.last_clipboard = ""
        
        
        # --- 新增：进程与暂停追踪器 ---
        self.active_processes = {}  # 记录正在运行的底层进程 {task_id: process}
        self.paused_tasks = set()   # 记录被手动点击暂停的任务 ID
        
        # 初始化目录和数据库
        self.init_env()
        
        # UI 构建
        self.setup_ui()
        
        # 加载数据库历史记录
        self.load_tasks_from_db()
        
        # 启动剪贴板监听
        self.monitor_clipboard()
        
        # --- 新增：接管最小化按钮 (-) 和 关闭按钮 (X) ---
        self.root.bind("<Unmap>", self.on_unmap)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
                      
              
        # --- 优化后的获取主窗口 Windows 底层句柄 HWND ---
        self.root.update_idletasks() # 确保窗口已在系统彻底渲染
        try:
            import ctypes
            # 穿透 Tkinter 表层，直接向 Windows 强要最底层的真实窗口句柄
            self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        except Exception:
            try:
                self.hwnd = int(self.root.wm_frame(), 16) # 兜底方案
            except Exception:
                self.hwnd = None
        
        # 启动剪贴板监听
        self.monitor_clipboard()
        
        # --- 新增：定义当前版本并启动无感版本检测 ---
        self.current_version = "V1.4.0"
        self.check_for_updates()
        
        # --- 新增：接管最小化按钮 (-) 和 关闭按钮 (X) ---
        self.root.bind("<Unmap>", self.on_unmap)
        
        
        
    def get_system_proxy_url(self):
        """自动探测并获取 Windows 系统当前的代理地址"""
        try:
            # 调用原生库读取系统代理配置
            proxies = urllib.request.getproxies()
            if 'http' in proxies:
                return proxies['http']
            elif 'https' in proxies:
                return proxies['https']
        except Exception:
            pass
        # 如果系统没开代理，或者探测失败，给一个常见的兜底值
        return "http://127.0.0.1:10809"       

    def init_env(self):
        """初始化必要文件夹与 SQLite 数据库"""
        # --- 新增：每次启动软件时，顺手把历史 Logs 文件夹干掉 ---
        import shutil
        try:
            shutil.rmtree(os.path.abspath("./tools/Logs"), ignore_errors=True)
        except:
            pass
            
        
        for d in ["Downloads", "tools"]:
            os.makedirs(d, exist_ok=True)
            
        # 连接数据库 (设置 check_same_thread=False 允许线程间通信，但我们统一在主线程写 DB)
        self.conn = sqlite3.connect('tasks.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # 创建任务表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                filename TEXT,
                save_path TEXT,
                status INTEGER,  -- 0:等待, 1:下载中, 2:完成, 3:失败
                size TEXT,
                progress TEXT,
                speed TEXT
            )
        ''')
        
        # ★ 状态机重启保护：将上次所有意外中断的下载中(1)改为等待中(0)
        self.cursor.execute("UPDATE tasks SET status=0 WHERE status=1")
        self.conn.commit()
        
    def on_unmap(self, event):
        """精准拦截点击 [-] 最小化按钮的动作"""
        # 判断必须是主窗口，且状态确实变成了最小化 ('iconic')
        if event.widget == self.root and self.root.state() == 'iconic':
            self.root.withdraw()  # 核心：从任务栏彻底隐藏
            self.show_tray()      # 呼出系统右下角托盘图标

    def on_closing(self):
        """精准拦截点击 [X] 关闭按钮的动作：不弹窗，直接绝杀"""
        try:
            self.conn.close() # 礼貌性地断开数据库
        except:
            pass
        self.root.destroy()
        os._exit(0) # 暴力而干净地清空所有后台下载线程，直接退出

    def show_tray(self):
        """构建右下角托盘图标与右键菜单"""
        # 尝试加载你的 logo，如果没有就临时画个蓝色的纯色方块兜底
        try:
            image = Image.open(resource_path("logo.ico"))
        except:
            image = Image.new('RGB', (64, 64), color=(33, 150, 243))

        menu = pystray.Menu(
            # default=True 意味着你双击那个小图标，就会执行这个命令
            pystray.MenuItem(get_text('tray_restore'), self.restore_window, default=True),
            pystray.MenuItem(get_text('tray_quit'), self.quit_window)
        )
        self.tray_icon = pystray.Icon("M-Fetch", image, get_text('tray_hover'), menu)
        
        # 必须把托盘扔进后台线程跑，否则会把 Tkinter 的界面卡死
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_window(self, icon, item):
        """从托盘恢复到桌面"""
        icon.stop() # 销毁托盘图标
        self.root.after(0, self.root.deiconify) # 将窗口重新放回任务栏和桌面

    def quit_window(self, icon, item):
        """在托盘右键点退出的逻辑"""
        icon.stop()
        self.on_closing()       
       
    def load_config(self):
        """加载配置文件，如果为空或不存在则使用默认值"""
        self.config_file = "config.json"
        self.default_config = {
            "max_workers": 10,           # 最大同时下载任务数
            "thread_count": 4,           # 单任务底层下载线程数
            "timeout": 30,               # 超时时间(秒)
            "retry_count": 3,             # 失败重试次数
            "max_speed": 0,             # <--- 新增：默认 0 为不限速
            "custom_header": "",        # <--- 新增：自定义请求头
            "skip_merge": False,    # <--- 新增：默认不跳过，也就是默认会合并成 MP4
            "enable_rules": False,       # 👇 加上这行：给规则文件一个默认不开启的初始状态
            "use_proxy": False,                          # 新增：代理开关
            "proxy_url": self.get_system_proxy_url(),         # 新增：默认代理地址
            "language": "auto"   # 默认自动探测
            
        }
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                self.config = json.loads(content) if content else self.default_config
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = self.default_config.copy()
            self.save_config() # 初始化一个干净的 json
            
        # --- 新增：读取用户设定的语言，并覆写全局 LANG 变量 ---
        global LANG
        saved_lang = self.config.get("language", "auto")
        if saved_lang != "auto":
            LANG = saved_lang
        else:
            LANG = get_sys_language()

    def save_config(self):
        """保存当前配置到 JSON"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def restore_settings(self):
        """恢复默认设置并更新 UI"""
        if messagebox.askyesno(get_text('msg_confirm'), get_text('msg_reset')):
            # 1. 恢复配置字典里的参数（并发、线程、超时等）
            for key, default_val in self.default_config.items():
                if key in self.setting_vars:
                    self.setting_vars[key].set(str(default_val))
                    
            # 2. 恢复代理的默认值
            self.use_proxy_var.set(self.default_config["use_proxy"])
            self.proxy_url_var.set(self.default_config["proxy_url"])
            self.enable_rules_var.set(self.default_config["enable_rules"])
            self.header_text.delete("1.0", tk.END)
            
            # 3. --- 新增：恢复默认下载路径 ---
            abs_download_path = os.path.abspath("Downloads")
            os.makedirs(abs_download_path, exist_ok=True) # 确保目录存在
            self.dir_var.set(abs_download_path)
            
            # 4. 自动应用并保存
            self.apply_settings() 
        

    def setup_ui(self):
        """构建现代选项卡式 UI"""
      
        
        # --- 顶部输入区 ---
        tk.Label(self.root, text=get_text('url_label')).place(x=15, y=15)
        self.url_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.url_var, width=65).place(x=80, y=15)

        tk.Label(self.root, text=get_text('name_label')).place(x=15, y=55)
        self.name_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.name_var, width=65).place(x=80, y=55)

        # --- 新版：保存路径区域 ---
        tk.Label(self.root, text=get_text('path_label')).place(x=15, y=95)
        
        # 1. 自动获取当前目录下 Downloads 的绝对路径，并确保目录存在
        abs_download_path = os.path.abspath("Downloads")
        os.makedirs(abs_download_path, exist_ok=True)
        self.dir_var = tk.StringVar(value=abs_download_path)
        
        # 缩短输入框宽度，为右侧按钮留出位置
        tk.Entry(self.root, textvariable=self.dir_var, width=48).place(x=80, y=95)
        
        # 2. “选择”按钮
        tk.Button(self.root, text=get_text('btn_select'), cursor="hand2", command=self.choose_dir).place(x=435, y=91, width=50, height=25)
        
        # 3. “打开”按钮
        tk.Button(self.root, text=get_text('btn_open'), cursor="hand2", command=self.open_current_dir).place(x=495, y=91, width=50, height=25)

        self.download_btn = tk.Button(self.root, text=get_text('btn_dl'), bg="#4CAF50", fg="white", 
                                      font=("Microsoft YaHei", 10, "bold"), command=self.add_new_task)
        self.download_btn.place(x=250, y=135, width=120, height=35)
        
        # --- 新增：自动下载复选框 ---
        self.auto_dl_var = tk.BooleanVar(value=True) # 默认值为 True（开启）
        tk.Checkbutton(self.root, text=get_text('chk_auto'), variable=self.auto_dl_var).place(x=390, y=140)

        # --- 底部任务管理器 (Tab) ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.place(x=15, y=190, width=590, height=290)

        # 1. 正在下载 Tab
        self.frame_dl = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_dl, text=get_text('tab_dl'))
        
        # --- 修复：重新排版，缩小按钮并留出合理间距 ---
        tk.Button(self.frame_dl, text=get_text('btn_start_all'), command=self.start_all_waiting).place(x=360, y=5, width=95, height=25)
        tk.Button(self.frame_dl, text=get_text('btn_pause_all'), command=self.pause_all_active).place(x=475, y=5, width=95, height=25)
        
        # 调整了宽度，新增了 "status" (状态) 列
        self.tree_dl = self.create_treeview(self.frame_dl, columns=("id", "name", "progress", "speed", "status"), 
                                            headings=(get_text('col_id'), get_text('col_name'), get_text('col_prog'), get_text('col_speed'), get_text('col_status')), widths=(40, 220, 80, 100, 80))
        
        
        # 绑定右键菜单：手动开始等待中的任务
        self.tree_dl.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_dl, "dl"))
        # --- 新增：为下载列表绑定 Del 键 ---
        self.tree_dl.bind("<Delete>", lambda e: self.delete_selected_item(self.tree_dl))

        # 2. 下载完成 Tab
        self.frame_ok = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_ok, text=get_text('tab_ok'))
        self.tree_ok = self.create_treeview(self.frame_ok, columns=("id", "name", "size"), 
                                            headings=(get_text('col_id'), get_text('col_name'), get_text('col_size')), widths=(40, 360, 140))
        tk.Button(self.frame_ok, text=get_text('btn_clear_ok'), command=lambda: self.clear_records(2)).place(x=480, y=5, width=90, height=25)
        self.tree_ok.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_ok, "ok"))

        # 3. 下载失败 Tab
        self.frame_fail = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_fail, text=get_text('tab_fail'))
        self.tree_fail = self.create_treeview(self.frame_fail, columns=("id", "name", "status"), 
                                              headings=(get_text('col_id'), get_text('col_name'), get_text('col_status')), widths=(40, 360, 140))
        # --- 新增：为失败列表绑定 Del 键 ---
        self.tree_fail.bind("<Delete>", lambda e: self.delete_selected_item(self.tree_fail))
                                              
        # --- 新增：全部断点续传按钮（放在清空按钮左侧） ---
        tk.Button(self.frame_fail, text=get_text('btn_resume_all'), command=self.resume_all_failed).place(x=380, y=5, width=90, height=25)                                               
        tk.Button(self.frame_fail, text=get_text('btn_clear_fail'), command=lambda: self.clear_records(3)).place(x=480, y=5, width=90, height=25)
        self.tree_fail.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_fail, "fail"))
        
        
        # 4. 高级设置 Tab
        self.frame_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_settings, text=get_text('tab_set'))
        

        # 创建一个 Canvas 和 Scrollbar 来实现滑动效果
        self.canvas_set = tk.Canvas(self.frame_settings, highlightthickness=0)
        self.scrollbar_set = ttk.Scrollbar(self.frame_settings, orient="vertical", command=self.canvas_set.yview)
        self.scrollable_frame = ttk.Frame(self.canvas_set)

        # 绑定尺寸变化，自动更新滚动区域
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas_set.configure(scrollregion=self.canvas_set.bbox("all"))
        )
        self.canvas_set.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas_set.configure(yscrollcommand=self.scrollbar_set.set)

        # 布局滑动区域 (给底部的按钮留出空间)
        self.canvas_set.place(x=5, y=5, width=560, height=215)
        self.scrollbar_set.place(x=565, y=5, height=215)

        # 绑定鼠标滚轮滑动体验
        def _on_mousewheel(event):
            self.canvas_set.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas_set.bind('<Enter>', lambda e: self.canvas_set.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas_set.bind('<Leave>', lambda e: self.canvas_set.unbind_all("<MouseWheel>"))

       # ==========================================
        # 1. 全局与基础设置 (Global Settings)
        # ==========================================
        current_row = 0  # 引入自动行号机制，后续插入极其方便
        
        # --- 界面语言 ---
        tk.Label(self.scrollable_frame, text=get_text('set_language'), fg="#333").grid(row=current_row, column=0, padx=20, pady=8, sticky="w")
        self.lang_map = {get_text('lang_auto'): "auto", "简体中文": "zh_CN", "English": "en_US"}
        self.reverse_lang_map = {v: k for k, v in self.lang_map.items()}
        current_lang_val = self.config.get("language", "auto")
        self.lang_display_var = tk.StringVar(value=self.reverse_lang_map.get(current_lang_val, get_text('lang_auto')))
        lang_combo = ttk.Combobox(self.scrollable_frame, textvariable=self.lang_display_var, state="readonly", width=18)
        lang_combo['values'] = list(self.lang_map.keys())
        lang_combo.grid(row=current_row, column=1, padx=10, pady=8, sticky="w")
        current_row += 1

        ttk.Separator(self.scrollable_frame, orient='horizontal').grid(row=current_row, column=0, columnspan=2, sticky="ew", pady=10, padx=10)
        current_row += 1

        # --- 基础下载参数 ---
        self.setting_vars = {}
        labels = {"max_workers": get_text('set_max_workers'), "thread_count": get_text('set_thread_count'), 
                  "timeout": get_text('set_timeout'), "retry_count": get_text('set_retry'),
                  "max_speed": get_text('set_max_speed')}  # <--- 加上这个键值对
        
        for key, label_text in labels.items():
            tk.Label(self.scrollable_frame, text=label_text).grid(row=current_row, column=0, padx=20, pady=12, sticky="w")
            var = tk.StringVar(value=str(self.config.get(key, self.default_config[key])))
            tk.Entry(self.scrollable_frame, textvariable=var, width=20).grid(row=current_row, column=1, padx=10, pady=12, sticky="w")
            self.setting_vars[key] = var
            current_row += 1

        # ==========================================
        # 2. 文件处理 (File Handling)
        # ==========================================
        ttk.Separator(self.scrollable_frame, orient='horizontal').grid(row=current_row, column=0, columnspan=2, sticky="ew", pady=10, padx=10)
        current_row += 1
        
        tk.Label(self.scrollable_frame, text=get_text('set_file_handle'), fg="#2196F3", font=("", 9, "bold")).grid(row=current_row, column=0, columnspan=2, sticky="w", padx=15, pady=5)
        current_row += 1
        
        file_frame = tk.Frame(self.scrollable_frame)
        file_frame.grid(row=current_row, column=0, columnspan=2, sticky="w", padx=20, pady=5)
        self.skip_merge_var = tk.BooleanVar(value=self.config.get("skip_merge", False))
        ttk.Checkbutton(file_frame, text=get_text('set_skip_merge'), variable=self.skip_merge_var).pack(side="left")
        
        self.btn_merge_ui = tk.Button(file_frame, text=get_text('btn_merge_ts'), cursor="hand2", command=self.merge_external_ts)
        self.btn_merge_ui.pack(side="left", padx=25)
        current_row += 1

        # ==========================================
        # 3. 网络与进阶突破 (Network & Hacks)
        # ==========================================
        ttk.Separator(self.scrollable_frame, orient='horizontal').grid(row=current_row, column=0, columnspan=2, sticky="ew", pady=10, padx=10)
        current_row += 1
        
        tk.Label(self.scrollable_frame, text=get_text('set_network'), fg="#2196F3", font=("", 9, "bold")).grid(row=current_row, column=0, columnspan=2, sticky="w", padx=15, pady=5)
        current_row += 1

        # --- 本地代理 ---
        tk.Label(self.scrollable_frame, text=get_text('set_proxy'), fg="#333").grid(row=current_row, column=0, padx=20, pady=8, sticky="w")
        proxy_frame = tk.Frame(self.scrollable_frame)
        proxy_frame.grid(row=current_row, column=1, padx=10, pady=8, sticky="w")
        self.use_proxy_var = tk.BooleanVar(value=self.config.get("use_proxy", False))
        ttk.Checkbutton(proxy_frame, text=get_text('set_proxy_enable'), variable=self.use_proxy_var).pack(side="left")
        self.proxy_url_var = tk.StringVar(value=self.config.get("proxy_url", ""))
        tk.Entry(proxy_frame, textvariable=self.proxy_url_var, width=32).pack(side="left", padx=10)
        current_row += 1

        # --- 自定义请求头 ---
        tk.Label(self.scrollable_frame, text=get_text('set_headers'), fg="#333").grid(row=current_row, column=0, padx=20, pady=8, sticky="nw")
        self.header_text = tk.Text(self.scrollable_frame, width=40, height=3, font=("Microsoft YaHei", 9))
        self.header_text.grid(row=current_row, column=1, padx=10, pady=8, sticky="w")
        self.header_text.insert("1.0", self.config.get("custom_header", "")) 
        current_row += 1
        tk.Label(self.scrollable_frame, text=get_text('set_headers_hint'), fg="gray", font=("", 8), justify="left").grid(row=current_row, column=1, sticky="nw", padx=10, pady=(0, 5))
        current_row += 1

        # --- 广告过滤 (紧跟网络请求之下，去掉了多余的蓝色大标题) ---
        tk.Label(self.scrollable_frame, text=get_text('set_ad_filter'), fg="#333").grid(row=current_row, column=0, padx=20, pady=8, sticky="w")
        self.ad_filter_var = tk.StringVar(value=self.config.get("ad_filter", ""))
        tk.Entry(self.scrollable_frame, textvariable=self.ad_filter_var, width=40).grid(row=current_row, column=1, padx=10, pady=8, sticky="w")
        current_row += 1
        tk.Label(self.scrollable_frame, text=get_text('set_ad_filter_hint'), fg="gray", font=("", 8)).grid(row=current_row, column=1, sticky="nw", padx=10, pady=(0, 10))
        current_row += 1

        # --- 外部规则库文件 ---
        self.enable_rules_var = tk.BooleanVar(value=self.config.get("enable_rules", False))
        ttk.Checkbutton(self.scrollable_frame, text=get_text('set_rules'), variable=self.enable_rules_var).grid(row=current_row, column=0, columnspan=2, padx=20, pady=(5, 0), sticky="w")
        current_row += 1
        rules_hint = get_text('rules_hint')
        hint_box = tk.Text(self.scrollable_frame, height=7, width=65, bg="#f0f0f0", bd=0, fg="gray", font=("", 8))
        hint_box.grid(row=current_row, column=0, columnspan=2, sticky="w", padx=40, pady=(0, 10))
        hint_box.insert("1.0", rules_hint)
        hint_box.bind("<Key>", lambda e: "break" if not (e.state & 4 and e.keysym.lower() == 'c') else None)   
        current_row += 1

        # 底部两个功能按钮 (固定在 Tab 最下方，不随内容滑动)
        tk.Button(self.frame_settings, text=get_text('btn_reset'), command=self.restore_settings).place(x=340, y=225, width=100, height=30)
        tk.Button(self.frame_settings, text=get_text('btn_save'), bg="#2196F3", fg="white", command=self.apply_settings).place(x=460, y=225, width=100, height=30) 

       # 5. 关于与赞赏 Tab
        self.frame_about = ttk.Frame(self.notebook)
        
        # --- 新增：默认加载暗色灯泡 (bulb_off.png) ---
        active_lang = self.config.get("language", "auto")
        if active_lang == "auto": active_lang = LANG
        clean_tab_text = " 关于 " if active_lang == "zh_CN" else " About "
        
        try:
            # 必须绑定为 self.bulb_off_icon 防止被内存回收
            self.bulb_off_icon = tk.PhotoImage(file=resource_path("bulb_off.png"))
            self.notebook.add(self.frame_about, text=clean_tab_text, image=self.bulb_off_icon, compound="left")
        except Exception:
            # 容错：万一打包时忘了放图片，退回原版的 Unicode 文字兜底
            self.notebook.add(self.frame_about, text=get_text('tab_about'))

        # 增加 Canvas 和 Scrollbar 支持滑动
        self.canvas_about = tk.Canvas(self.frame_about, highlightthickness=0)
        self.scrollbar_about = ttk.Scrollbar(self.frame_about, orient="vertical", command=self.canvas_about.yview)
        
        # 承载文字和图片的容器
        about_container = tk.Frame(self.canvas_about)

        # 绑定尺寸变化，自动更新滚动区域
        about_container.bind(
            "<Configure>",
            lambda e: self.canvas_about.configure(scrollregion=self.canvas_about.bbox("all"))
        )
        # 改为左上角对齐 (nw) 并设置较小的 X 轴边距，完美解决英文超长被挤出边界的问题
        self.canvas_about.create_window((15, 10), window=about_container, anchor="nw")
        self.canvas_about.configure(yscrollcommand=self.scrollbar_about.set)

        # 布局滑动区域
        self.canvas_about.place(x=5, y=5, width=560, height=250)
        self.scrollbar_about.place(x=565, y=5, height=250)

        # 绑定鼠标滚轮 (复用高级设置里的滚轮事件逻辑)
        self.canvas_about.bind('<Enter>', lambda e: self.canvas_about.bind_all("<MouseWheel>", lambda event: self.canvas_about.yview_scroll(int(-1*(event.delta/120)), "units")))
        self.canvas_about.bind('<Leave>', lambda e: self.canvas_about.unbind_all("<MouseWheel>"))

        # --- 左侧：软件说明文字 ---
        about_text = get_text('about_desc')
        
        # 判断当前真正生效的语言
        active_lang = self.config.get("language", "auto")
        if active_lang == "auto":
            active_lang = LANG

        # 创建一个左侧容器来垂直排列文字和链接
        left_container = tk.Frame(about_container)
        left_container.pack(side="left", padx=(0, 30), pady=10, fill="y")
        self.about_left_container = left_container # <-- 新增：保存容器引用，方便后续跨函数插入更新提示
        
        text_label = tk.Label(left_container, text=about_text, justify="left", fg="#333", font=("Microsoft YaHei", 10))
        text_label.pack(anchor="w")

        # --- 新增：可点击的 GitHub 超链接 ---
        github_link = tk.Label(left_container, text=get_text('about_github'), 
                               fg="#2196F3", font=("Microsoft YaHei", 9, "underline"), cursor="hand2")
        github_link.pack(anchor="w", pady=(5, 0))
        # 绑定鼠标左键点击事件，调用默认浏览器打开网页
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Nanobanana-AI/M-Fetch"))
        
        # 顺便把你的官方网站也加个链接背书
        website_link = tk.Label(left_container, text=get_text('about_site'), 
                               fg="#2196F3", font=("Microsoft YaHei", 9, "underline"), cursor="hand2")
        website_link.pack(anchor="w", pady=(5, 0))
        website_link.bind("<Button-1>", lambda e: webbrowser.open("https://okqiyi.com/m-fetch/"))

        # ==========================================
        # --- 动态排版：中文显示赞赏码，英文隐藏图片并显示 PayPal ---
        # ==========================================
        if active_lang == "zh_CN":
            try:
                self.qr_image = tk.PhotoImage(file=resource_path("donate.png"))
                img_label = tk.Label(about_container, image=self.qr_image)
                img_label.pack(side="left")
            except Exception:
                tk.Label(about_container, text=get_text('about_qr_fail'), fg="gray").pack(side="left")
        else:
            # 英文环境下，不加载图片，在左侧容器直接追加一个加粗的橘色 PayPal 专属超链接
            paypal_link = tk.Label(left_container, text="☕ Support via PayPal", 
                                   fg="#FF9800", font=("Microsoft YaHei", 9, "underline", "bold"), cursor="hand2")
            paypal_link.pack(anchor="w", pady=(5, 0))
            paypal_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.paypal.com/paypalme/Okqiyi"))
            
    def start_all_waiting(self):
        """一键把列表中所有 '等待中' 或 '已暂停' 的任务推入下载队列"""
        items = self.tree_dl.get_children()
        for iid in items:
            vals = self.tree_dl.item(iid, 'values')
            if vals[4] in (get_text('status_wait'), get_text('status_paused')):  
                self.resume_task(vals[0])

    def pause_all_active(self):
        """一键暂停所有正在干活的任务"""
        items = self.tree_dl.get_children()
        for iid in items:
            vals = self.tree_dl.item(iid, 'values')
            if vals[4] in (get_text('status_dl'), get_text('status_resume')):
                self.pause_task(vals[0])

    def pause_task(self, task_id):
        """物理超度底层进程，实现纯净暂停"""
        task_id = int(task_id)
        if task_id in self.active_processes:
            self.paused_tasks.add(task_id) # 打上被手动终结的标记
            try:
                self.active_processes[task_id].kill() # 拔掉网线，直接杀进程
            except: 
                pass     
            
    def choose_dir(self):
        """弹出选择文件夹对话框"""
        current_path = self.dir_var.get().strip()
        # 弹出系统原生的文件夹选择窗口
        selected_dir = filedialog.askdirectory(initialdir=current_path, title=get_text('dialog_sel_dir'))
        
        if selected_dir:
            # 将路径转换为 Windows 友好的绝对路径并写回输入框
            self.dir_var.set(os.path.abspath(selected_dir))

    def open_current_dir(self):
        """一键打开当前设定的保存目录，若不存在则自动新建"""
        target_path = self.dir_var.get().strip()
        if not target_path:
            return
            
        try:
            # 自动新建不存在的目录
            if not os.path.exists(target_path):
                os.makedirs(target_path, exist_ok=True)
            # 调用 Windows 资源管理器打开该路径
            os.startfile(target_path)
        except Exception as e:
            messagebox.showerror(get_text('msg_open_fail'), f"{get_text('msg_open_fail_detail')}{e}")       


    def create_treeview(self, parent, columns, headings, widths):
        """封装创建表格列表的方法"""
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        for col, head, width in zip(columns, headings, widths):
            tree.heading(col, text=head)
            tree.column(col, width=width, anchor="center" if col != "name" else "w")
        tree.place(x=5, y=35, width=575, height=220)
        return tree

    def monitor_clipboard(self):
        """剪贴板监听，支持多行批量捕获与并发下载"""
        try:
            current_clipboard = self.root.clipboard_get().strip()
            if current_clipboard != self.last_clipboard:
                
                # --- 暴力清洗与提取引擎 (正则强化版) ---
                valid_urls = []
                # 核心黑科技：直接用正则无视任何 JSON、引号或尖括号包裹，强行抠出所有 m3u8 链接
                raw_urls = re.findall(r"https?://[^\s\"'<>]+?\.m3u8[^\s\"'<>]*", current_clipboard)
                
                # 顺手做个列表内去重，防止嗅探插件重复复制
                for item in raw_urls:
                    if item not in valid_urls:
                        valid_urls.append(item)
                # -------------------------
                
                if valid_urls:
                    self.last_clipboard = current_clipboard # 记录当前剪贴板，防止重复触发
                    
                    if self.auto_dl_var.get():
                        # 批量模式：瞬间把所有链接丢进并发队列
                        spath = self.dir_var.get().strip()
                        base_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        for i, u in enumerate(valid_urls):
                            fname = f"{base_time}_{i+1:03d}" 
                            
                            # 随机下载延迟 (400ms - 800ms 动态错峰)
                            # i=0 时立即执行，后续任务累加随机抖动
                            delay = 0 if i == 0 else i * random.randint(400, 800)
                            
                            # lambda 函数绑定局部变量防穿透
                            self.root.after(delay, lambda url=u, name=fname, path=spath: 
                                            self.add_new_task(input_url=url, input_fname=name, input_spath=path))

                
                                       
                    else:
                        # --- 批量排队模式：全部静默入库为"等待中" ---
                        spath = self.dir_var.get().strip()
                        base_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                        for i, u in enumerate(valid_urls):
                            fname = f"{base_time}_{i+1:03d}" 
                            # 不自动执行，所以无需错峰延迟，直接瞬间入库展示
                            self.add_new_task(input_url=u, input_fname=fname, input_spath=spath, auto_start=False)
                        
        except:
            pass
        self.root.after(1000, self.monitor_clipboard)

    def load_tasks_from_db(self):
        """程序启动时读取数据库，分类渲染任务"""
        self.cursor.execute("SELECT * FROM tasks")
        for row in self.cursor.fetchall():
            task_id, url, fname, spath, status, size, prog, speed = row
            if status == 0:  # 等待中
                self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", get_text('status_wait')))
            elif status == 4:  # 新增：已暂停
                self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, prog, "-", get_text('status_paused')))
            elif status == 2:  # 完成
                
                self.tree_ok.insert('', 'end', iid=task_id, values=(task_id, fname, size))
            elif status == 3:  # 失败
                self.tree_fail.insert('', 'end', iid=task_id, values=(task_id, fname, get_text('status_fail')))

    def add_new_task(self, input_url=None, input_fname=None, input_spath=None, auto_start=True):
        """点击下载按钮触发或剪贴板批量触发：入库并调度"""
        url = input_url if input_url else self.url_var.get().strip()
        fname = input_fname if input_fname else self.name_var.get().strip()
        spath = input_spath if input_spath else self.dir_var.get().strip()
        
        if not url or not fname or not spath:
            if not input_url:  
                messagebox.showwarning(get_text('msg_tips'), get_text('msg_incomplete'))
            return

        # --- 核心修复：截取真正的 M3U8 主干路径，忽略 token 等动态参数 ---
        clean_url = url.split('?')[0] 
        
        # 使用 LIKE 模糊匹配，只要数据库里存的链接主干和现在的长得一样，一律按重复处理
        self.cursor.execute("SELECT id FROM tasks WHERE url LIKE ? AND status IN (0, 1, 2)", (clean_url + '%',))
        
        if self.cursor.fetchone():
            self.cursor.execute("INSERT INTO tasks (url, filename, save_path, status, size, progress, speed) VALUES (?, ?, ?, 3, '', '0%', '0KB/s')", 
                                (url, fname, spath))
            self.conn.commit()
            task_id = self.cursor.lastrowid
            self.tree_fail.insert('', 0, iid=task_id, values=(task_id, fname, get_text('status_repeat')))
            if not input_url: 
                self.url_var.set("")
                self.name_var.set("")
            return

        # 核心：根据是否自动开始，赋予初始状态 1(下载中) 或 0(等待中)
        init_status = 1 if auto_start else 0
        self.cursor.execute("INSERT INTO tasks (url, filename, save_path, status, size, progress, speed) VALUES (?, ?, ?, ?, '', '0%', '0KB/s')", 
                            (url, fname, spath, init_status))
        self.conn.commit()
        task_id = self.cursor.lastrowid

        if auto_start:
            # 加入 UI 并在后台启动
            self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", get_text('status_dl')))
            self.executor.submit(self.download_worker, task_id, url, fname, spath)
        else:
            # 仅加入 UI，不提交给线程池
            self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", get_text('status_wait')))

        if not input_url:
            self.url_var.set("")
            self.name_var.set("")

    def download_worker(self, task_id, url, filename, save_dir):
        """核心后台下载引擎"""
        cmd = [
            r"./tools/N_m3u8DL-RE.exe", url,
            "--save-name", filename, "--save-dir", save_dir, "--tmp-dir", save_dir,
            "--thread-count", str(self.config.get("thread_count", 4)),
            "--http-request-timeout", str(self.config.get("timeout", 30)),
            "--download-retry-count", str(self.config.get("retry_count", 3)),
            "--del-after-done", "True",
            "--mp4-real-time-decryption", "True", "--decryption-engine", "FFMPEG",
            "--decryption-binary-path", r"./tools/ffmpeg.exe",
            "--no-ansi-color" ,
            "--auto-select"  # 遇到多画质菜单时，自动选择最高画质，不要等待人工确认
        ]
        
        # --- 新增：全局网络限速 ---
        max_speed = self.config.get("max_speed", 0)
        if max_speed > 0:
            cmd.extend(["--max-speed", f"{max_speed}M"])
            
        # --- 新增：如果开启了代理，强制引擎走自定义代理 ---
        if self.config.get("use_proxy") and self.config.get("proxy_url"):
            cmd.extend(["--custom-proxy", self.config.get("proxy_url")])
            
        # ==========================================
        # 核心升级：外挂式“影子规则库” (静默容错版 + 绝对路径防坑)
        # ==========================================
        import os
        import sys
        import json
        import urllib.parse
        
        matched = False
        
        # 只有在高级设置里打勾了，才会去尝试读取
        if self.config.get("enable_rules", False):
            # 🔥 终极防坑1：获取软件真正所在的绝对路径，防止工作目录漂移
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable) # 打包后 exe 所在目录
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__)) # py 脚本所在目录
                
            rules_path = os.path.join(app_dir, "rules.json")
            
            if os.path.exists(rules_path):
                try:
                    # 🔥 终极防坑2：使用 utf-8-sig 完美兼容 Windows 记事本带 BOM 的 UTF-8
                    with open(rules_path, "r", encoding="utf-8-sig") as f:
                        external_rules = json.load(f)
                    
                    # 遍历字典进行匹配
                    for keyword, headers in external_rules.items():
                        if keyword in url:
                            matched = True
                            for key, value in headers.items():
                                cmd.extend(["-H", f"{key}: {value}"])
                            #print(f"[DEBUG] 成功命中外部规则文件！特征词: {keyword}") # 后台提示
                            break
                except Exception as e:
                    #print(f"[DEBUG] 读取 rules.json 失败啦: {e}") # 方便在控制台排错
                    pass 

        # 1. 万能浏览器伪装 (无论匹配与否都要带)
        cmd.extend(["-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"])

        # 2. 如果没触发外挂规则（没勾选、没文件、格式错、或者没匹配上该网址），老老实实执行自动提取兜底
        if not matched:
            parsed_url = urllib.parse.urlparse(url)
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            cmd.extend(["-H", f"Origin: {base_domain}"])
            cmd.extend(["-H", f"Referer: {base_domain}"])
        # ==========================================
            
        # --- 新增：智能多行表头解析引擎 ---
        # 如果用户在界面填了自定义表头，引擎会追加进去。
        # 命令行工具遇到重复的 Header，通常以后面追加的为准，实现完美覆盖。
        custom_headers = self.config.get("custom_header", "").strip()
        if custom_headers:
            # splitlines() 会自动按回车换行符把多行文本切成一个列表
            for line in custom_headers.splitlines():
                clean_line = line.strip()
                if clean_line: # 防止用户输入空行导致报错
                    cmd.extend(["-H", clean_line])
            
        # --- 新增：如果勾选了不合并，则向引擎发送跳过指令 ---
        if self.config.get("skip_merge"):
            cmd.extend(["--skip-merge"])
        # --- 新增：广告分片正则拦截引擎 ---
        ad_filter_rule = self.config.get("ad_filter", "").strip()
        if ad_filter_rule:
            # 直接调用底层引擎的关键字过滤参数，支持正则
            cmd.extend(["--ad-keyword", ad_filter_rule])    
        
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo,
                universal_newlines=True # 处理 \r 更新进度
            )

            # --- 新增：把活着的进程句柄存起来 ---
            self.active_processes[task_id] = process

           # --- 终极黑科技：放弃按行读取，改用“碎肉机”按块读取，完美粉碎新版的死锁缓冲 ---
            buffer = ""
            while True:
                # 每次强行抓取 32 个字符，不依赖任何换行符，只要有输出就立刻截获
                chunk = process.stdout.read(32)
                if not chunk:
                    break
                
                buffer += chunk
                
                # 使用 findall 提取缓冲池里【最新】的所有进度和速度
                prog_matches = re.findall(r'(\d+(?:\.\d+)?%)', buffer)
                speed_matches = re.findall(r'([\d.]+[kKmMgG]?[bB]ps)', buffer, re.IGNORECASE)
                
                # 永远只取数组里的最后一个（即最新鲜的进度数据）
                prog = prog_matches[-1] if prog_matches else None
                speed = speed_matches[-1] if speed_matches else None
                
                if prog or speed:
                    # 瞬间推送到 UI 界面
                    self.root.after(0, self.update_tree_ui, task_id, prog, speed)
                    # 核心细节：保留最后 20 个字符（防止把 13.5MBps 从中间切断漏判），其他的直接丢弃清空内存
                    buffer = buffer[-20:]

            process.wait()

            if process.returncode == 0:
                self.root.after(0, self.task_finished, task_id, filename, save_dir, True)
            else:
                self.root.after(0, self.task_finished, task_id, filename, save_dir, False)

        except Exception as e:
            self.root.after(0, self.task_finished, task_id, filename, save_dir, False)

    def update_tree_ui(self, task_id, prog, speed):
        """安全更新界面进度条数字和速度"""
        try:
            if self.tree_dl.exists(task_id):
                item_values = list(self.tree_dl.item(task_id, 'values'))
                if prog: item_values[2] = prog
                if speed: item_values[3] = speed
                self.tree_dl.item(task_id, values=item_values)
                
            # --- 新增：顺便刷新任务栏进度条 ---
            self.update_taskbar_progress()
        except:
            pass
     
    def update_taskbar_progress(self):
        """核心黑科技：实时汇总多任务平均进度，映射到 Windows 任务栏，并动态更新右下角托盘悬浮文字"""
        try:
            items = self.tree_dl.get_children()
            valid_tasks = 0
            total_prog = 0.0

            if items:
                for iid in items:
                    vals = self.tree_dl.item(iid, 'values')
                    status = vals[4]
                    # 只统计正在下载或正在恢复的活跃任务
                    if status in (get_text('status_dl'), get_text('status_resume')):
                        prog_str = vals[2].replace('%', '').strip()
                        try:
                            total_prog += float(prog_str)
                            valid_tasks += 1
                        except ValueError:
                            pass

            # ==========================================
            # 1. 动态更新右下角“系统托盘”的鼠标悬浮文字
            # ==========================================
            if hasattr(self, 'tray_icon') and self.tray_icon:
                if valid_tasks > 0:
                    # 如果有任务，鼠标放上去会显示具体有几个任务在干活
                    self.tray_icon.title = f"M-Fetch: {valid_tasks} 个任务正在下载..."
                else:
                    # 空闲时恢复默认提示
                    self.tray_icon.title = get_text('tray_hover')

            # ==========================================
            # 2. 映射大窗口的“任务栏”进度条 (修复卡死BUG)
            # ==========================================
            if TASKBAR_AVAILABLE and self.hwnd:
                if valid_tasks > 0:
                    avg_prog = int(total_prog / valid_tasks)
                    taskbar.SetProgressState(self.hwnd, TBPF_NORMAL)
                    taskbar.SetProgressValue(self.hwnd, avg_prog, 100)
                else:
                    # 【连招修复】：彻底治好 Windows 任务栏的重绘“懒癌”
                    taskbar.SetProgressState(self.hwnd, TBPF_NORMAL)     # 1. 先唤醒它
                    taskbar.SetProgressValue(self.hwnd, 0, 100)          # 2. 彻底抽干绿条
                    taskbar.SetProgressState(self.hwnd, TBPF_NOPROGRESS) # 3. 彻底熄灭状态
                    
                    # 4. 踹系统一脚，强制刷新底层消息队列，立马生效不用等点击
                    if hasattr(self, 'root'):
                        self.root.update_idletasks()

        except Exception:
            pass
         
    def task_finished(self, task_id, filename, save_dir, is_success):
        """任务结束状态分发器 (引入终极物理验货机制，拒绝假成功)"""
        # 清理已死亡的进程记录
        self.active_processes.pop(task_id, None)

        # ==========================================
        # 新增拦截器：如果它是被我们手动杀掉的，就地转为暂停状态，不走失败逻辑
        # ==========================================
        if task_id in self.paused_tasks:
            self.paused_tasks.remove(task_id)
            self.cursor.execute("UPDATE tasks SET status=4 WHERE id=?", (task_id,)) # 数据库 4 代表暂停
            self.conn.commit()
            
            if self.tree_dl.exists(task_id):
                item_values = list(self.tree_dl.item(task_id, 'values'))
                item_values[3] = "-" # 速度清零
                item_values[4] = get_text('status_paused') # 状态变更为已暂停
                self.tree_dl.item(task_id, values=item_values)
            
            self.update_taskbar_progress()
            return # 核心：直接 return，阻止它被移到失败列表
            
        try:
            if self.tree_dl.exists(task_id):
                self.tree_dl.delete(task_id) # 从下载队列移除
        except: pass

        # ==========================================
        # 核心修复：物理验货逻辑 (Physical File Verification)
        # 即使底层报告成功，也要亲自去硬盘上确认目标文件是否存在
        # ==========================================
        actual_success = is_success
        final_size = get_text('status_unknown')
        
        if actual_success:
            # 1. 如果用户【没有】勾选不合并 -> 必须得有完整的 .mp4 才能算真成功
            if not self.config.get("skip_merge"):
                target_file = os.path.join(save_dir, f"{filename}.mp4")
                if os.path.exists(target_file):
                    size_mb = os.path.getsize(target_file) / (1024 * 1024)
                    final_size = f"{size_mb:.2f} MB"
                else:
                    actual_success = False # 假成功被识破，打回失败！
                    
            # 2. 如果用户【勾选了】不合并 -> 只要同名缓存文件夹存在且有内容就算成功
            else:
                target_folder = os.path.join(save_dir, filename)
                if os.path.exists(target_folder):
                    final_size = get_text('status_kept')
                else:
                    actual_success = False

        # --- 根据最终的严苛判定来更新 UI 和 数据库 ---
        if actual_success:
            # 更新数据库状态 = 2
            self.cursor.execute("UPDATE tasks SET status=2, size=? WHERE id=?", (final_size, task_id))
            self.conn.commit()
            # 添加到完成列表
            self.tree_ok.insert('', 0, iid=task_id, values=(task_id, filename, final_size))
        else:
            # 更新数据库状态 = 3
            self.cursor.execute("UPDATE tasks SET status=3 WHERE id=?", (task_id,))
            self.conn.commit()
            # 添加到失败列表 (用户可在该列表右键断点续传)
            self.tree_fail.insert('', 0, iid=task_id, values=(task_id, filename, get_text('status_verify_fail')))
            # --- 新增：任务完成后重新计算任务栏总进度 ---
        self.update_taskbar_progress()

    def clear_records(self, status):
        """独立清理指定的视图列表与数据库记录（坚决不删本地实际文件）"""
        target_tree = self.tree_ok if status == 2 else self.tree_fail
        items = target_tree.get_children()
        
        if not items:
            return
            
        if messagebox.askyesno(get_text('msg_clear_confirm'), get_text('msg_clear_desc')):
            # 1. 删数据库
            self.cursor.execute("DELETE FROM tasks WHERE status=?", (status,))
            self.conn.commit()
            # 2. 删 UI
            for iid in items:
                target_tree.delete(iid)
                
           # --- 新增：点清空时顺手物理消灭 Logs 文件夹 ---
            
            try:
                shutil.rmtree(os.path.abspath("./tools/Logs"), ignore_errors=True)
            except:
                pass     
                
    def delete_selected_item(self, tree):
        """按 Del 键触发：仅从数据库和当前视图中删除选中的任务，不碰本地文件"""
        selected_items = tree.selection()
        if not selected_items:
            return
            
        for iid in selected_items:
            # 获取当前选中项的 task_id
            task_id = tree.item(iid, 'values')[0]
            
            # 1. 斩草除根：从数据库中直接抹除该记录
            self.cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            self.conn.commit()
            
            # 2. 视觉清理：从当前 UI 列表中移除它
            tree.delete(iid)         
            # --- 新增：如果你删除了下载中的任务，顺便刷新任务栏 ---
        if tree == self.tree_dl:
            self.update_taskbar_progress()

    def show_context_menu(self, event, tree, tree_type):
        """超级实用的右键菜单调度"""
        iid = tree.identify_row(event.y)
        if not iid: return
        tree.selection_set(iid)
        
        menu = tk.Menu(self.root, tearoff=0)
        item_values = tree.item(iid, 'values')
        task_id = item_values[0]

        if tree_type == "dl":
            status = item_values[4]
            # 如果是等待或暂停，显示【开始】
            if status in (get_text('status_wait'), get_text('status_paused')):
                menu.add_command(label=get_text('menu_start'), command=lambda: self.resume_task(task_id))
            # 如果是正在下载或恢复中，显示【暂停】
            elif status in (get_text('status_dl'), get_text('status_resume')):
                menu.add_command(label=get_text('menu_pause'), command=lambda: self.pause_task(task_id))
            
        elif tree_type == "fail":
            menu.add_command(label=get_text('menu_re_dl'), command=lambda: self.resume_task(task_id))

        menu.post(event.x_root, event.y_root)

    def resume_all_failed(self):
        """无提示，一键将所有失败任务重新加入下载队列"""
        items = self.tree_fail.get_children()
        if not items:
            return
            
        for iid in items:
            # 提取每一个失败任务的 task_id
            task_id = self.tree_fail.item(iid, 'values')[0]
            # 直接复用单任务的续传逻辑
            self.resume_task(task_id)

    def resume_task(self, task_id):
        """恢复/重新下载指定任务"""
        # --- 核心修复：强制将 UI 传来的字符串 ID 转回整数，防止字典 Key 错乱 ---
        task_id = int(task_id)
        
        # 取出任务参数
        self.cursor.execute("SELECT url, filename, save_path FROM tasks WHERE id=?", (task_id,))
        row = self.cursor.fetchone()
        if not row: return
        url, fname, spath = row

        # 更新数据库状态为 1
        self.cursor.execute("UPDATE tasks SET status=1 WHERE id=?", (task_id,))
        self.conn.commit()

        # 整理 UI：从失败中移除（如果在），更新/加回下载中
        try:
            if self.tree_fail.exists(task_id): 
                self.tree_fail.delete(task_id)
        except: pass
        
        if self.tree_dl.exists(task_id):
            # 如果它本来就在下载列表里（比如已暂停状态），原地复活
            item_values = list(self.tree_dl.item(task_id, 'values'))
            item_values[4] = get_text('status_resume')
            self.tree_dl.item(task_id, values=item_values)
        else:
            # 否则从头新建一行
            self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", get_text('status_resume')))
        
        # 抛入线程池
        self.executor.submit(self.download_worker, task_id, url, fname, spath)
        
    def open_folder(self, task_id):
        """安全打开 Windows 文件管理器并定位到该目录"""
        self.cursor.execute("SELECT save_path FROM tasks WHERE id=?", (task_id,))
        row = self.cursor.fetchone()
        if row and os.path.exists(row[0]):
            os.startfile(row[0])
     
    def merge_external_ts(self):
        """核心组件：合并任意外部 TS 文件夹，支持自然排序算法防乱序"""
        # 1. 弹出系统选择框
        target_dir = filedialog.askdirectory(title=get_text('dialog_sel_ts'))
        if not target_dir: 
            return

        # 2. 扫盘检索所有 .ts 文件
        ts_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.ts')]
        if not ts_files:
            messagebox.showwarning(get_text('msg_tips'), get_text('msg_merge_none'), parent=self.root)
            return

        # 3. 引入自然排序算法 (Natural Sort)
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]
        ts_files.sort(key=natural_sort_key)

        # 4. 生成 FFmpeg 专用的 concat 索引清单
        concat_file = os.path.join(target_dir, 'mfetch_concat_tmp.txt')
        try:
            with open(concat_file, 'w', encoding='utf-8') as f:
                for ts in ts_files:
                    f.write(f"file '{ts}'\n")
        except Exception as e:
            messagebox.showerror(get_text('msg_error'), str(e), parent=self.root)
            return

        folder_name = os.path.basename(target_dir)
        if not folder_name: 
            folder_name = "Merged_Video"
        output_mp4 = os.path.join(target_dir, f"{folder_name}.mp4")

        # --- 增加 UI 视觉反馈：变灰并提示合并中 ---
        self.btn_merge_ui.config(text="⏳ 合并中...", state="disabled")
        self.root.update()

        # 5. 放入独立线程执行后台静默缝合
        def process():
            ffmpeg_path = resource_path(r"tools\ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"

            cmd = [
                ffmpeg_path,
                "-y",                   
                "-f", "concat",         
                "-safe", "0",           
                "-i", concat_file,      
                "-c", "copy",           
                output_mp4
            ]
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            try:
                # 【核心修复】：必须指定 cwd 为目标文件夹，否则 ffmpeg 找不到分片
                subprocess.run(cmd, startupinfo=startupinfo, check=True, cwd=target_dir)
                os.remove(concat_file) 
                
                # 恢复按钮状态并弹窗 (加入 parent 防止被挡住)
                self.root.after(0, lambda: [
                    self.btn_merge_ui.config(text=get_text('btn_merge_ts'), state="normal"),
                    messagebox.showinfo(get_text('msg_success'), get_text('msg_merge_ok') + f"{folder_name}.mp4", parent=self.root)
                ])
            except Exception as e:
                self.root.after(0, lambda: [
                    self.btn_merge_ui.config(text=get_text('btn_merge_ts'), state="normal"),
                    messagebox.showerror(get_text('msg_error'), get_text('msg_merge_fail') + str(e), parent=self.root)
                ])

        threading.Thread(target=process, daemon=True).start()
     
    def check_for_updates(self):
        """后台静默检测 GitHub 最新版本"""
        def _check():
            try:
                # 零成本白嫖 GitHub 的 API
                req = urllib.request.Request("https://api.github.com/repos/Nanobanana-AI/M-Fetch/releases/latest")
                req.add_header('User-Agent', 'M-Fetch-App')
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    latest_version = data.get("tag_name", "")
                    
                    if latest_version:
                        import re
                        # 将字符串版本号转化为整数列表，例如 "V1.4.0" -> [1, 3, 0]
                        def parse_version(v_str):
                            return [int(x) for x in re.findall(r'\d+', v_str)]
                            
                        # 真正的版本号大小判定：只有线上版本 大于 当前版本时，才触发提示
                        if parse_version(latest_version) > parse_version(self.current_version):
                            # 涉及修改 UI，必须通过 self.root.after 丢给主线程执行
                            self.root.after(0, self.show_update_notification, latest_version)
            except Exception:
                # 如果用户没联网或者 API 访问受限，默默当作无事发生，绝不报错卡死
                pass 

        threading.Thread(target=_check, daemon=True).start()

    def show_update_notification(self, latest_version):
        """后台检测到更新：点亮彩色灯泡并在左侧插入超链接"""
        active_lang = self.config.get("language", "auto")
        if active_lang == "auto":
            active_lang = LANG
            
        # 1. 尝试加载点亮的灯泡 (bulb_on.png) 并替换 Tab 图标
        try:
            self.bulb_on_icon = tk.PhotoImage(file=resource_path("bulb_on.png"))
            clean_tab_text = " 关于 " if active_lang == "zh_CN" else " About "
            self.notebook.tab(self.frame_about, text=clean_tab_text, image=self.bulb_on_icon, compound="left")
        except Exception:
            pass # 如果没图片，保持现状，不报错
        
        # 2. 动态分配提示文案与目标跳转网址 (多语言路由)
        if active_lang == "zh_CN":
            tips_text = f"🚀 发现最新版本 {latest_version}，点击前往获取！"
            target_url = "https://okqiyi.com/m-fetch/"  # 中文导向中文官网
        else:
            tips_text = f"🚀 New version {latest_version} available! Click to update."
            target_url = "https://github.com/Nanobanana-AI/M-Fetch/releases/latest"  # 英文直接导向 GitHub 最新发布页
        
        update_label = tk.Label(self.about_left_container, 
                                text=tips_text, 
                                fg="#E91E63", 
                                font=("Microsoft YaHei", 9, "bold", "underline"), 
                                cursor="hand2")
                                
        update_label.pack(anchor="w", pady=(10, 0))
        # 绑定点击事件，打开分配好的专属 URL
        update_label.bind("<Button-1>", lambda e: webbrowser.open(target_url))
        
    def apply_settings(self):
        """保存设置选项卡中的配置"""
        try:
            for key, var in self.setting_vars.items():
                self.config[key] = int(var.get())
            
            # 新增：单独保存代理设置
            self.config["use_proxy"] = self.use_proxy_var.get()
            self.config["proxy_url"] = self.proxy_url_var.get().strip()
            self.config["skip_merge"] = self.skip_merge_var.get() 
            
            # 👇 加上这一行！将 UI 的勾选状态真正写入配置字典
            self.config["enable_rules"] = self.enable_rules_var.get()
            
            # 读取多行文本框里的内容
            self.config["custom_header"] = self.header_text.get("1.0", tk.END).strip()
            # 保存广告过滤正则
            self.config["ad_filter"] = self.ad_filter_var.get().strip()
            
            # --- 新增：保存语言设置，并判断是否需要提示重启 ---
            old_lang = self.config.get("language", "auto")
            new_lang = self.lang_map.get(self.lang_display_var.get(), "auto")
            self.config["language"] = new_lang
            
            self.save_config()
            
            if old_lang != new_lang:
                messagebox.showinfo(get_text('msg_success'), get_text('msg_restart'))
            else:
                messagebox.showinfo(get_text('msg_success'), get_text('msg_save_ok'))
                
        except ValueError:
            messagebox.showerror(get_text('msg_error'), get_text('msg_number_err'))

if __name__ == "__main__":
    root = tk.Tk()
    app = M3U8TaskApp(root)
    root.mainloop()
