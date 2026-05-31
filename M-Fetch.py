#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================================
Project     : M-Fetch (极简 M3U8 下载器)
Version     : 1.1.0
Description : A minimalist, ad-free, high-performance M3U8 & Streaming downloader 
              GUI based on N_m3u8DL-RE and FFmpeg.
Author      : Okqiyi (https://okqiyi.com/m-fetch/)
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

def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境与 PyInstaller 打包后的单文件环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class M3U8TaskApp:
    def __init__(self, root):
        self.root = root
        self.root.title("M-Fetch | 极简 M3U8 下载器 V1.1.0")
        self.root.geometry("620x500")
        self.root.resizable(False, False)
        # --- 新增：设置窗口左上角的 Logo ---
        try:
            self.root.iconbitmap(resource_path("logo.ico"))
        except:
            pass # 如果没找到图标就不显示，防止报错

        # --- 新增：加载配置文件 ---
        self.load_config()
        
        # 核心设置：改由配置文件接管
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.config.get("max_workers", 10))
        
        self.last_clipboard = ""
        
        # 初始化目录和数据库
        self.init_env()
        
        # UI 构建
        self.setup_ui()
        
        # 加载数据库历史记录
        self.load_tasks_from_db()
        
        # 启动剪贴板监听
        self.monitor_clipboard()
        
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
        
    def load_config(self):
        """加载配置文件，如果为空或不存在则使用默认值"""
        self.config_file = "config.json"
        self.default_config = {
            "max_workers": 10,           # 最大同时下载任务数
            "thread_count": 4,           # 单任务底层下载线程数
            "timeout": 30,               # 超时时间(秒)
            "retry_count": 3,             # 失败重试次数
            "custom_header": "",        # <--- 新增：自定义请求头
            "skip_merge": False,    # <--- 新增：默认不跳过，也就是默认会合并成 MP4
            "enable_rules": False,       # 👇 加上这行：给规则文件一个默认不开启的初始状态
            "use_proxy": False,                          # 新增：代理开关
            "proxy_url": self.get_system_proxy_url()         # 新增：默认代理地址
            
        }
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                self.config = json.loads(content) if content else self.default_config
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = self.default_config.copy()
            self.save_config() # 初始化一个干净的 json

    def save_config(self):
        """保存当前配置到 JSON"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def restore_settings(self):
        """恢复默认设置并更新 UI"""
        if messagebox.askyesno("确认", "确定要恢复到默认设置吗？\n(包含高级设置与默认下载路径)"):
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
        tk.Label(self.root, text="下载地址:").place(x=15, y=15)
        self.url_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.url_var, width=65).place(x=80, y=15)

        tk.Label(self.root, text="保存文件:").place(x=15, y=55)
        self.name_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.name_var, width=65).place(x=80, y=55)

        # --- 新版：保存路径区域 ---
        tk.Label(self.root, text="保存路径:").place(x=15, y=95)
        
        # 1. 自动获取当前目录下 Downloads 的绝对路径，并确保目录存在
        abs_download_path = os.path.abspath("Downloads")
        os.makedirs(abs_download_path, exist_ok=True)
        self.dir_var = tk.StringVar(value=abs_download_path)
        
        # 缩短输入框宽度，为右侧按钮留出位置
        tk.Entry(self.root, textvariable=self.dir_var, width=48).place(x=80, y=95)
        
        # 2. “选择”按钮
        tk.Button(self.root, text="选择", cursor="hand2", command=self.choose_dir).place(x=435, y=91, width=50, height=25)
        
        # 3. “打开”按钮
        tk.Button(self.root, text="打开", cursor="hand2", command=self.open_current_dir).place(x=495, y=91, width=50, height=25)

        self.download_btn = tk.Button(self.root, text="立即下载", bg="#4CAF50", fg="white", 
                                      font=("Microsoft YaHei", 10, "bold"), command=self.add_new_task)
        self.download_btn.place(x=250, y=135, width=120, height=35)
        
        # --- 新增：自动下载复选框 ---
        self.auto_dl_var = tk.BooleanVar(value=True) # 默认值为 True（开启）
        tk.Checkbutton(self.root, text="监听到链接后自动开始", variable=self.auto_dl_var).place(x=390, y=140)

        # --- 底部任务管理器 (Tab) ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.place(x=15, y=190, width=590, height=290)

        # 1. 正在下载 Tab
        self.frame_dl = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_dl, text=" 正在下载 ")
        # 调整了宽度，新增了 "status" (状态) 列
        self.tree_dl = self.create_treeview(self.frame_dl, columns=("id", "name", "progress", "speed", "status"), 
                                            headings=("ID", "文件名", "进度", "速度", "状态"), widths=(40, 220, 80, 100, 80))
        # 新增：全部开始按钮 (挂在表格上方)
        tk.Button(self.frame_dl, text="全部开始 ", command=self.start_all_waiting).place(x=460, y=5, width=110, height=25)
        # 绑定右键菜单：手动开始等待中的任务
        self.tree_dl.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_dl, "dl"))
        # --- 新增：为下载列表绑定 Del 键 ---
        self.tree_dl.bind("<Delete>", lambda e: self.delete_selected_item(self.tree_dl))

        # 2. 下载完成 Tab
        self.frame_ok = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_ok, text=" 下载完成 ")
        self.tree_ok = self.create_treeview(self.frame_ok, columns=("id", "name", "size"), 
                                            headings=("ID", "文件名", "文件大小"), widths=(40, 360, 140))
        tk.Button(self.frame_ok, text="清空完成记录", command=lambda: self.clear_records(2)).place(x=480, y=5, width=90, height=25)
        self.tree_ok.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_ok, "ok"))

        # 3. 下载失败 Tab
        self.frame_fail = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_fail, text=" 下载失败 ")
        self.tree_fail = self.create_treeview(self.frame_fail, columns=("id", "name", "status"), 
                                              headings=("ID", "文件名", "状态"), widths=(40, 360, 140))
        # --- 新增：为失败列表绑定 Del 键 ---
        self.tree_fail.bind("<Delete>", lambda e: self.delete_selected_item(self.tree_fail))
                                              
        # --- 新增：全部断点续传按钮（放在清空按钮左侧） ---
        tk.Button(self.frame_fail, text="全部断点续传", command=self.resume_all_failed).place(x=380, y=5, width=90, height=25)                                               
        tk.Button(self.frame_fail, text="清空失败记录", command=lambda: self.clear_records(3)).place(x=480, y=5, width=90, height=25)
        self.tree_fail.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_fail, "fail"))
        
        
        # 4. 高级设置 Tab
        self.frame_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_settings, text=" ⚙️ 高级设置 ")
        

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

        # 动态生成输入框并保存引用
        self.setting_vars = {}
        labels = {"max_workers": "最大并发任务数:", "thread_count": "单任务下载线程:", 
                  "timeout": "网络超时阀值(秒):", "retry_count": "失败重试次数:"}
        
        for i, (key, label_text) in enumerate(labels.items()):
            tk.Label(self.scrollable_frame, text=label_text).grid(row=i, column=0, padx=20, pady=12, sticky="w")
            var = tk.StringVar(value=str(self.config.get(key, self.default_config[key])))
            tk.Entry(self.scrollable_frame, textvariable=var, width=20).grid(row=i, column=1, padx=10, pady=12)
            self.setting_vars[key] = var
        
        # --- 文件处理选项  ---
        ttk.Separator(self.scrollable_frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky="ew", pady=10, padx=10)
        tk.Label(self.scrollable_frame, text="文件处理 ", fg="#2196F3", font=("", 9, "bold")).grid(row=5, column=0, columnspan=2, sticky="w", padx=15, pady=5)
        
        self.skip_merge_var = tk.BooleanVar(value=self.config.get("skip_merge", False))
        ttk.Checkbutton(self.scrollable_frame, text="下载后保留原始 TS 分片 (不合并 MP4)", 
                        variable=self.skip_merge_var).grid(row=6, column=0, columnspan=2, padx=20, pady=5, sticky="w")

        # --- 网络与请求设置  ---
        ttk.Separator(self.scrollable_frame, orient='horizontal').grid(row=7, column=0, columnspan=2, sticky="ew", pady=10, padx=10)
        tk.Label(self.scrollable_frame, text="网络与请求 ", fg="#2196F3", font=("", 9, "bold")).grid(row=8, column=0, columnspan=2, sticky="w", padx=15, pady=5)

        # 1. 自定义表头 (Headers) - 升级为多行支持
        # 注意这里的 sticky 改成了 "nw"，让文字跟文本框顶部对齐
        tk.Label(self.scrollable_frame, text="自定义请求头:", fg="#333").grid(row=9, column=0, padx=20, pady=8, sticky="nw")
        
        # 使用 Text 控件代替 Entry，height=3 表示默认显示 3 行高度
        self.header_text = tk.Text(self.scrollable_frame, width=40, height=3, font=("Microsoft YaHei", 9))
        self.header_text.grid(row=9, column=1, padx=10, pady=8, sticky="w")
        # Text 控件没有 textvariable，需要手动插入初始值
        self.header_text.insert("1.0", self.config.get("custom_header", "")) 
        
        # 升级提示语，展示多行示例
        tk.Label(self.scrollable_frame, text="(支持多行，User-Agent: iOS  Cookie: mycookie )", 
                 fg="gray", font=("", 8), justify="left").grid(row=10, column=1, sticky="nw", padx=10, pady=(0, 5))
                 
                 
        # 3. 外部规则文件
        self.enable_rules_var = tk.BooleanVar(value=self.config.get("enable_rules", False))
        ttk.Checkbutton(self.scrollable_frame, text="启用同目录下的规则文件 (rules.json)", 
                        variable=self.enable_rules_var).grid(row=12, column=0, columnspan=2, padx=20, pady=(5, 0), sticky="w")
        
        # --- 新增：灰色的规则文件格式说明 (改为可复制的 Text 控件) ---
        rules_hint = (
            '//进阶玩法: 请在软件同级目录自行新建 rules.json。\n'
            '//格式如下 (可直接复制修改):\n'
            '{\n'
            '    "网址1": {\n'
            '        "Origin": "https://www.网址1.com",\n'
            '        "Referer": "https://www.网址1.com/"\n'
            '    }\n'
            '}'
        )
        
        # 使用 Text 控件替代 Label，去掉边框 (bd=0)，背景色设为与窗口一致的浅灰色
        hint_box = tk.Text(self.scrollable_frame, height=7, width=65, bg="#f0f0f0", bd=0, fg="gray", font=("", 8))
        hint_box.grid(row=13, column=0, columnspan=2, sticky="w", padx=40, pady=(0, 10))
        hint_box.insert("1.0", rules_hint)
        
        # 核心黑科技：拦截除了 Ctrl+C (复制) 之外的所有键盘输入，实现“只读可复制”
        hint_box.bind("<Key>", lambda e: "break" if not (e.state & 4 and e.keysym.lower() == 'c') else None)   

        # 2. 代理设置
        tk.Label(self.scrollable_frame, text="本地代理地址:", fg="#333").grid(row=11, column=0, padx=20, pady=8, sticky="w")
        
        proxy_frame = tk.Frame(self.scrollable_frame)
        proxy_frame.grid(row=11, column=1, padx=10, pady=8, sticky="w")
        
        self.use_proxy_var = tk.BooleanVar(value=self.config.get("use_proxy", False))
        ttk.Checkbutton(proxy_frame, text="启用", variable=self.use_proxy_var).pack(side="left")
        
        
        self.proxy_url_var = tk.StringVar(value=self.config.get("proxy_url", ""))
        tk.Entry(proxy_frame, textvariable=self.proxy_url_var, width=32).pack(side="left", padx=10)
        

        # 底部两个功能按钮 (固定在 Tab 最下方，不随内容滑动)
        tk.Button(self.frame_settings, text="恢复默认", command=self.restore_settings).place(x=340, y=225, width=100, height=30)
        tk.Button(self.frame_settings, text="保存设置", bg="#2196F3", fg="white", command=self.apply_settings).place(x=460, y=225, width=100, height=30)

       # 5. 关于与赞赏 Tab
        self.frame_about = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_about, text=" 💡 关于 ")

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
        # 将容器放入 Canvas，并使其水平居中 (X=280)
        self.canvas_about.create_window((280, 10), window=about_container, anchor="n")
        self.canvas_about.configure(yscrollcommand=self.scrollbar_about.set)

        # 布局滑动区域
        self.canvas_about.place(x=5, y=5, width=560, height=250)
        self.scrollbar_about.place(x=565, y=5, height=250)

        # 绑定鼠标滚轮 (复用高级设置里的滚轮事件逻辑)
        self.canvas_about.bind('<Enter>', lambda e: self.canvas_about.bind_all("<MouseWheel>", lambda event: self.canvas_about.yview_scroll(int(-1*(event.delta/120)), "units")))
        self.canvas_about.bind('<Leave>', lambda e: self.canvas_about.unbind_all("<MouseWheel>"))

        # --- 左侧：软件说明文字 ---
        about_text = (
            "本软件为纯粹的效率工具，基于 N_m3u8DL-RE 强力内核构建。\n"
            "主打极简、秒开、无感后台运行与批量断点续传。\n"
            "【V1.1.0 核心升级】\n"
            "支持多行链接批量排队，新增自定义请求头和规则与错峰引擎。\n\n"
            "如果您觉得这款工具为您节省了宝贵的时间，\n"
            "欢迎扫码请开发者喝杯咖啡 ☕ \n"
             "2026年6月1日"
        )
        
        # 创建一个左侧容器来垂直排列文字和链接
        left_container = tk.Frame(about_container)
        left_container.pack(side="left", padx=(0, 30), pady=10, fill="y")
        
        text_label = tk.Label(left_container, text=about_text, justify="left", fg="#333", font=("Microsoft YaHei", 10))
        text_label.pack(anchor="w")

        # --- 新增：可点击的 GitHub 超链接 ---
        github_link = tk.Label(left_container, text="👉 访问 GitHub 获取最新源码与完整更新日志", 
                               fg="#2196F3", font=("Microsoft YaHei", 9, "underline"), cursor="hand2")
        github_link.pack(anchor="w", pady=(5, 0))
        # 绑定鼠标左键点击事件，调用默认浏览器打开网页
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Nanobanana-AI/M-Fetch"))
        
        # 顺便把你的官方网站也加个链接背书
        website_link = tk.Label(left_container, text="🌐 访问作者官网：okqiyi.com", 
                               fg="#2196F3", font=("Microsoft YaHei", 9, "underline"), cursor="hand2")
        website_link.pack(anchor="w", pady=(5, 0))
        website_link.bind("<Button-1>", lambda e: webbrowser.open("https://okqiyi.com/m-fetch/"))

        # --- 右侧：加载二维码图片 (保持不变) ---
        try:
            self.qr_image = tk.PhotoImage(file=resource_path("donate.png"))
            img_label = tk.Label(about_container, image=self.qr_image)
            img_label.pack(side="left")
        except Exception:
            tk.Label(about_container, text="[请放置 donate.png]", fg="gray").pack(side="left")
            
    def start_all_waiting(self):
        """一键把列表中所有 '等待中' 的任务推入下载队列"""
        items = self.tree_dl.get_children()
        for iid in items:
            vals = self.tree_dl.item(iid, 'values')
            # 判断第5列(索引4)是否为等待中
            if vals[4] == "等待中":  
                self.resume_task(vals[0])        
            
    def choose_dir(self):
        """弹出选择文件夹对话框"""
        current_path = self.dir_var.get().strip()
        # 弹出系统原生的文件夹选择窗口
        selected_dir = filedialog.askdirectory(initialdir=current_path, title="选择默认保存目录")
        
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
            messagebox.showerror("打开失败", f"无法打开该目录:\n{e}")       


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
                
                # --- 暴力清洗与提取引擎 ---
                valid_urls = []
                # 使用 split() 代替 splitlines()，无视空格、换行、Tab等一切干扰符
                for item in current_clipboard.split():
                    item = item.strip()
                    if item.startswith("http") and ".m3u8" in item:
                        # 顺手做个列表内去重，防止嗅探插件重复复制
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
                self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", "等待中"))
            elif status == 2:  # 完成
                self.tree_ok.insert('', 'end', iid=task_id, values=(task_id, fname, size))
            elif status == 3:  # 失败
                self.tree_fail.insert('', 'end', iid=task_id, values=(task_id, fname, "失败"))

    def add_new_task(self, input_url=None, input_fname=None, input_spath=None, auto_start=True):
        """点击下载按钮触发或剪贴板批量触发：入库并调度"""
        url = input_url if input_url else self.url_var.get().strip()
        fname = input_fname if input_fname else self.name_var.get().strip()
        spath = input_spath if input_spath else self.dir_var.get().strip()
        
        if not url or not fname or not spath:
            if not input_url:  
                messagebox.showwarning("提示", "信息不完整！")
            return

        self.cursor.execute("SELECT id FROM tasks WHERE url=? AND status IN (0, 1, 2)", (url,))
        if self.cursor.fetchone():
            self.cursor.execute("INSERT INTO tasks (url, filename, save_path, status, size, progress, speed) VALUES (?, ?, ?, 3, '', '0%', '0KB/s')", 
                                (url, fname, spath))
            self.conn.commit()
            task_id = self.cursor.lastrowid
            self.tree_fail.insert('', 0, iid=task_id, values=(task_id, fname, "重复拦截"))
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
            self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", "下载中"))
            self.executor.submit(self.download_worker, task_id, url, fname, spath)
        else:
            # 仅加入 UI，不提交给线程池
            self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", "等待中"))

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

           # 解析实时进度和速度
            for line in process.stdout:
                prog_match = re.search(r'(\d+(?:\.\d+)?%)', line)
                speed_match = re.search(r'([\d.]+\s*[kKmMgG][bB](?:/s|ps))', line)
                
                prog = prog_match.group(1) if prog_match else None
                speed = speed_match.group(1) if speed_match else None

                if prog or speed:
                    # 使用 root.after 确保 UI 线程安全更新
                    self.root.after(0, self.update_tree_ui, task_id, prog, speed)

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
        except:
            pass
            
         
    def task_finished(self, task_id, filename, save_dir, is_success):
        """任务结束状态分发器"""
        try:
            if self.tree_dl.exists(task_id):
                self.tree_dl.delete(task_id) # 从下载队列移除
        except: pass

        if is_success:
            # 尝试计算真实文件大小
            final_size = "未知"
            target_file = os.path.join(save_dir, f"{filename}.mp4")
            if os.path.exists(target_file):
                size_mb = os.path.getsize(target_file) / (1024 * 1024)
                final_size = f"{size_mb:.2f} MB"

            # 更新数据库状态 = 2
            self.cursor.execute("UPDATE tasks SET status=2, size=? WHERE id=?", (final_size, task_id))
            self.conn.commit()
            
            # 添加到完成列表
            self.tree_ok.insert('', 0, iid=task_id, values=(task_id, filename, final_size))
        else:
            # 更新数据库状态 = 3
            self.cursor.execute("UPDATE tasks SET status=3 WHERE id=?", (task_id,))
            self.conn.commit()
            
            # 添加到失败列表
            self.tree_fail.insert('', 0, iid=task_id, values=(task_id, filename, "下载失败"))

    def clear_records(self, status):
        """独立清理指定的视图列表与数据库记录（坚决不删本地实际文件）"""
        target_tree = self.tree_ok if status == 2 else self.tree_fail
        items = target_tree.get_children()
        
        if not items:
            return
            
        if messagebox.askyesno("清理确认", "确定要清除列表记录吗？\n(仅清理软件记录，硬盘上的文件不会被删除)"):
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

    def show_context_menu(self, event, tree, tree_type):
        """超级实用的右键菜单调度"""
        iid = tree.identify_row(event.y)
        if not iid: return
        tree.selection_set(iid)
        
        menu = tk.Menu(self.root, tearoff=0)
        item_values = tree.item(iid, 'values')
        task_id = item_values[0]

        if tree_type == "dl" and item_values[4] == "等待中":
            menu.add_command(label="▶ 开始/继续下载", command=lambda: self.resume_task(task_id))
            
        elif tree_type == "ok":
            menu.add_command(label="📂 打开所在文件夹", command=lambda: self.open_folder(task_id))
            
        elif tree_type == "fail":
            menu.add_command(label="🔄 重新下载 (断点续传)", command=lambda: self.resume_task(task_id))

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
        # 取出任务参数
        self.cursor.execute("SELECT url, filename, save_path FROM tasks WHERE id=?", (task_id,))
        row = self.cursor.fetchone()
        if not row: return
        url, fname, spath = row

        # 更新数据库状态为 1
        self.cursor.execute("UPDATE tasks SET status=1 WHERE id=?", (task_id,))
        self.conn.commit()

        # 整理 UI：从失败中移除（如果在），加回下载中
        try:
            if self.tree_fail.exists(task_id): self.tree_fail.delete(task_id)
            if self.tree_dl.exists(task_id): self.tree_dl.delete(task_id)
        except: pass
        
        self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "0%", "-", "正在恢复"))
        
        # 抛入线程池
        self.executor.submit(self.download_worker, task_id, url, fname, spath)
        
    def open_folder(self, task_id):
        """安全打开 Windows 文件管理器并定位到该目录"""
        self.cursor.execute("SELECT save_path FROM tasks WHERE id=?", (task_id,))
        row = self.cursor.fetchone()
        if row and os.path.exists(row[0]):
            os.startfile(row[0])
            
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
            
            # 读取多行文本框里的内容 (从第1行第0个字符到结尾)
            self.config["custom_header"] = self.header_text.get("1.0", tk.END).strip()
            
            self.save_config()
            messagebox.showinfo("成功", "设置已保存！\n(部分设置将在下一次任务生效)")
        except ValueError:
            messagebox.showerror("错误", "请确保并发、线程、超时等输入均为有效数字！")

            


if __name__ == "__main__":
    root = tk.Tk()
    app = M3U8TaskApp(root)
    root.mainloop()