#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================================
Project     : M-Fetch (极简 M3U8 下载器)
Version     : 1.0.0
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
import urllib.request
from datetime import datetime
import concurrent.futures

def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境与 PyInstaller 打包后的单文件环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class M3U8TaskApp:
    def __init__(self, root):
        self.root = root
        self.root.title("M-Fetch | 极简 M3U8 下载器 V1.0.0")
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
        self.tree_dl = self.create_treeview(self.frame_dl, columns=("id", "name", "progress", "speed"), 
                                            headings=("ID", "文件名", "进度", "速度"), widths=(40, 280, 100, 120))
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
            
        # --- 真实的代理与网络设置 ---
        ttk.Separator(self.scrollable_frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky="ew", pady=10, padx=10)
        tk.Label(self.scrollable_frame, text="代理设置 ", fg="#2196F3", font=("", 9, "bold")).grid(row=5, column=0, columnspan=2, sticky="w", padx=15, pady=5)

        tk.Label(self.scrollable_frame, text="本地代理地址:", fg="#333").grid(row=6, column=0, padx=20, pady=8, sticky="w")
        
        # 使用 Frame 将开关和输入框横向排列
        proxy_frame = tk.Frame(self.scrollable_frame)
        proxy_frame.grid(row=6, column=1, padx=10, pady=8, sticky="w")

        # 代理开关 (Tkinter 原生 Checkbutton，简约稳定)
        self.use_proxy_var = tk.BooleanVar(value=self.config.get("use_proxy", False))
        ttk.Checkbutton(proxy_frame, text="启用", variable=self.use_proxy_var).pack(side="left")

        # 代理地址输入框
        self.proxy_url_var = tk.StringVar(value=self.config.get("proxy_url", "http://127.0.0.1:7890"))
        tk.Entry(proxy_frame, textvariable=self.proxy_url_var, width=20).pack(side="left", padx=10)
        

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
            "【最佳工作流推荐】\n"
            "建议配合 Chrome 浏览器的「猫爪」等嗅探插件使用：\n"
            "1. 网页端嗅探到目标视频，点击复制 m3u8 链接。\n"
            "2. 本软件自动后台捕获，并立即加入下载队列。\n"
            "3. 自动多线程下载、解密并合并为 MP4，全程无感。\n\n"
            "如果您觉得这款工具为您节省了宝贵的时间，\n"
            "欢迎扫码请开发者喝杯咖啡 ☕ \n"
             "2026年5月20日"
        )
        text_label = tk.Label(about_container, text=about_text, justify="left", fg="#333", font=("Microsoft YaHei", 10))
        text_label.pack(side="left", padx=(0, 30), pady=10)

        # --- 右侧：加载二维码图片 (使用 resource_path 完美兼容 exe) ---
        try:
            self.qr_image = tk.PhotoImage(file=resource_path("donate.png"))
            img_label = tk.Label(about_container, image=self.qr_image)
            img_label.pack(side="left")
        except Exception:
            tk.Label(about_container, text="[请放置 donate.png]", fg="gray").pack(side="left")
            
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
        """剪贴板监听，就绪即解锁下载按钮"""
        try:
            current_clipboard = self.root.clipboard_get().strip()
            if current_clipboard != self.last_clipboard and current_clipboard.startswith("http") and ".m3u8" in current_clipboard:
                if current_clipboard != self.url_var.get():
                    self.last_clipboard = current_clipboard
                    self.url_var.set(current_clipboard)
                    self.name_var.set(datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-4])
                    # 变绿就绪
                    self.download_btn.config(state=tk.NORMAL, bg="#4CAF50")
                    
                    # --- 新增：判断是否开启了自动下载 ---
                    if self.auto_dl_var.get():
                        self.add_new_task()
        except:
            pass
        self.root.after(1000, self.monitor_clipboard)

    def load_tasks_from_db(self):
        """程序启动时读取数据库，分类渲染任务"""
        self.cursor.execute("SELECT * FROM tasks")
        for row in self.cursor.fetchall():
            task_id, url, fname, spath, status, size, prog, speed = row
            if status == 0:  # 等待中
                self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "等待中...", "-"))
            elif status == 2:  # 完成
                self.tree_ok.insert('', 'end', iid=task_id, values=(task_id, fname, size))
            elif status == 3:  # 失败
                self.tree_fail.insert('', 'end', iid=task_id, values=(task_id, fname, "失败"))

    def add_new_task(self):
        """点击下载按钮触发：入库并启动"""
        url, fname, spath = self.url_var.get().strip(), self.name_var.get().strip(), self.dir_var.get().strip()
        if not url or not fname or not spath:
            messagebox.showwarning("提示", "信息不完整！")
            return

        # --- 新增：核心查重逻辑 ---
        # 检查数据库中是否已存在相同的 URL，且状态为 0(等待), 1(下载中) 或 2(完成)
        self.cursor.execute("SELECT id FROM tasks WHERE url=? AND status IN (0, 1, 2)", (url,))
        existing_task = self.cursor.fetchone()

        if existing_task:
            # 如果存在，直接将其作为“失败任务”入库
            self.cursor.execute("INSERT INTO tasks (url, filename, save_path, status, size, progress, speed) VALUES (?, ?, ?, 3, '', '0%', '0KB/s')", 
                                (url, fname, spath))
            self.conn.commit()
            task_id = self.cursor.lastrowid
            
            # UI 层面：直接插入到下载失败 Tab，并明确标注原因
            self.tree_fail.insert('', 0, iid=task_id, values=(task_id, fname, "重复下载 (已拦截)"))
            
            # 重置界面状态，不往下投递给线程池
            self.url_var.set("")
            self.name_var.set("")
            self.download_btn.config(bg="#9E9E9E")
            return
        # --- 查重逻辑结束 ---

        # 1. 写入数据库，状态为 1(下载中)
        self.cursor.execute("INSERT INTO tasks (url, filename, save_path, status, size, progress, speed) VALUES (?, ?, ?, 1, '', '0%', '0KB/s')", 
                            (url, fname, spath))
        self.conn.commit()
        task_id = self.cursor.lastrowid

        # 2. 插入正在下载视图
        self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "正在解析...", "-"))
        
        # 3. 提交线程池，无阻塞后台运行
        self.executor.submit(self.download_worker, task_id, url, fname, spath)

        # 清空输入框，准备下一次粘贴
        self.url_var.set("")
        self.name_var.set("")
        self.download_btn.config(bg="#9E9E9E")

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
            "--auto-select"  # <--- 新增这行：遇到多画质菜单时，自动选择最高画质，不要等待人工确认
        ]
        
        # --- 新增：如果开启了代理，强制引擎走自定义代理 ---
        if self.config.get("use_proxy") and self.config.get("proxy_url"):
            cmd.extend(["--custom-proxy", self.config.get("proxy_url")])
        
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
                # 把下面这行原来的 speed_match 替换掉
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

        if tree_type == "dl" and item_values[2] == "等待中...":
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
        
        self.tree_dl.insert('', 'end', iid=task_id, values=(task_id, fname, "正在恢复...", "-"))
        
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
            
            self.save_config()
            messagebox.showinfo("成功", "设置已保存！\n(部分设置将在下一次任务生效)")
        except ValueError:
            messagebox.showerror("错误", "请确保并发、线程、超时等输入均为有效数字！")

            


if __name__ == "__main__":
    root = tk.Tk()
    app = M3U8TaskApp(root)
    root.mainloop()