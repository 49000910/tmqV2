import time
import winsound
import threading
import os
import sys
import tkinter as tk
from tkinter import messagebox
from pynput import keyboard
from pynput.keyboard import Controller, Key

# --- 资源路径处理 ---
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 配置 ---
HISTORY_FILE = "barcode_history.txt"
BARCODE_HISTORY = set()
SCAN_BUFFER = []
LAST_KEY_TIME = 0
SCAN_SPEED_THRESHOLD = 0.05 
kb_controller = Controller()

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        BARCODE_HISTORY = set(line.strip() for line in f if line.strip())

class PullBackUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("智能拉回显示版 v2.331")
        self.root.geometry("480x450+100+100") 
        self.root.attributes("-topmost", True, "-alpha", 0.95)
        self.root.overrideredirect(True)

        # --- 自定义标题栏 ---
        self.title_bar = tk.Frame(self.root, bg="#1a252f", height=30)
        self.title_bar.pack(fill=tk.X)
        self.title_label = tk.Label(self.title_bar, text=" 🛡️ 重复拦截器 (大字提醒模式)", font=("微软雅黑", 9), fg="#bdc3c7", bg="#1a252f")
        self.title_label.pack(side=tk.LEFT, padx=5)
        self.min_btn = tk.Button(self.title_bar, text=" — ", bg="#1a252f", fg="white", bd=0, command=self.minimize_window)
        self.min_btn.pack(side=tk.RIGHT, padx=5)

        # --- 主内容区 ---
        self.main_frame = tk.Frame(self.root, bg="#2c3e50", bd=1)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 1. 顶部状态文字
        self.status_label = tk.Label(self.main_frame, text="等待扫描...", font=("微软雅黑", 11, "bold"), fg="white", bg="#34495e")
        self.status_label.pack(fill=tk.X)

        # 2. 【新增】当前条码巨型提示区
        self.current_code_frame = tk.Frame(self.main_frame, bg="#1c2833", pady=10)
        self.current_code_frame.pack(fill=tk.X)
        self.current_code_label = tk.Label(self.current_code_frame, text="---", 
                                           font=("Consolas", 24, "bold"), # 巨型字体
                                           fg="#2ecc71", bg="#1c2833", wraplength=450)
        self.current_code_label.pack()
        
        # 3. 历史记录容器 (滚动)
        self.log_container = tk.Frame(self.main_frame, bg="#2c3e50")
        self.log_container.pack(fill=tk.BOTH, expand=True, pady=5)

        self.scrollbar = tk.Scrollbar(self.log_container)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(self.log_container, font=("微软雅黑", 10), fg="#ecf0f1", bg="#2c3e50",
                                bd=0, padx=10, pady=5, cursor="hand2", state=tk.DISABLED, 
                                spacing1=2, yscrollcommand=self.scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.log_text.yview)

        self.log_text.tag_config("duplicate", foreground="#f1c40f", background="#c0392b") 
        self.log_text.bind("<Button-1>", self.copy_last_code)
        
        # 4. 底部统计
        self.bottom_bar = tk.Frame(self.main_frame, bg="#2c3e50")
        self.bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.count_lbl = tk.Label(self.bottom_bar, text=f"累计存入: {len(BARCODE_HISTORY)}", font=("微软雅黑", 9), fg="#95a5a6", bg="#2c3e50")
        self.count_lbl.pack(side=tk.LEFT, padx=10)

        # 基础绑定
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        self.grip = tk.Label(self.root, text="◢", cursor="size_nw_se", fg="#7f8c8d", bg="#2c3e50")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<B1-Motion>", self.do_resize)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="🗑️ 清空历史", command=self.clear_history)
        self.menu.add_command(label="❌ 退出程序", command=self.safe_exit)
        self.root.bind("<Button-3>", lambda e: self.menu.post(e.x_root, e.y_root))
        
        self.last_scanned_code = ""

    def flash_alarm(self, count=6):
        if count <= 0:
            self.current_code_frame.config(bg="#1c2833")
            self.current_code_label.config(bg="#1c2833")
            return
        curr = self.current_code_frame.cget("bg")
        nxt = "#c0392b" if curr == "#1c2833" else "#1c2833"
        self.current_code_frame.config(bg=nxt)
        self.current_code_label.config(bg=nxt)
        self.root.after(150, lambda: self.flash_alarm(count - 1))

    def update_ui(self, code, is_duplicate):
        self.last_scanned_code = code
        ts = time.strftime("%H:%M:%S")
        
        # 更新顶部状态和巨型显示
        if is_duplicate:
            self.status_label.config(text="⚠️ 重复拦截：该条码已存在！", bg="#e74c3c")
            self.current_code_label.config(text=code, fg="#f1c40f") # 重复显示黄色
            self.flash_alarm()
            winsound.Beep(1200, 600)
        else:
            self.status_label.config(text="✅ 扫描成功：已存入记录", bg="#27ae60")
            self.current_code_label.config(text=code, fg="#2ecc71") # 正常显示绿色

        self.count_lbl.config(text=f"累计存入: {len(BARCODE_HISTORY)}")

        # 更新滚动日志
        self.log_text.config(state=tk.NORMAL)
        if "已清空" in code: 
            self.log_text.delete('1.0', tk.END)
            self.current_code_label.config(text="---", fg="#2ecc71")
        else:
            log_entry = f"[{ts}] {code}\n"
            self.log_text.insert(tk.END, log_entry)
            line_count = int(self.log_text.index('end-1c').split('.'))
            if is_duplicate:
                self.log_text.tag_add("duplicate", f"{line_count}.0", f"{line_count}.end")
            
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        if not is_duplicate and "已清空" not in code:
            with open(HISTORY_FILE, "a", encoding="utf-8") as f: f.write(f"{code}\n")

    def minimize_window(self):
        self.root.overrideredirect(False); self.root.iconify()
        self.root.bind("<FocusIn>", lambda e: [self.root.overrideredirect(True), self.root.unbind("<FocusIn>")] )

    def start_move(self, event): self.x, self.y = event.x, event.y
    def do_move(self, event): self.root.geometry(f"+{self.root.winfo_x()+event.x-self.x}+{self.root.winfo_y()+event.y-self.y}")
    def do_resize(self, event): self.root.geometry(f"{max(350, event.x_root-self.root.winfo_x())}x{max(300, event.y_root-self.root.winfo_y())}")
    
    def copy_last_code(self, event):
        if self.last_scanned_code:
            self.root.clipboard_clear(); self.root.clipboard_append(self.last_scanned_code)
            self.status_label.config(text=f"📋 已复制最后条码: {self.last_scanned_code}")

    def clear_history(self):
        if messagebox.askyesno("确认", "是否要清空所有历史数据？"):
            BARCODE_HISTORY.clear()
            if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
            self.update_ui("已清空历史", False)

    def safe_exit(self):
        self.root.quit()
        os._exit(0)

# --- 拦截逻辑 ---
def pull_back_and_select():
    with kb_controller.pressed(Key.shift): kb_controller.press(Key.tab); kb_controller.release(Key.tab)
    time.sleep(0.1)
    with kb_controller.pressed(Key.ctrl): kb_controller.press('a'); kb_controller.release('a')

def on_press(key):
    global LAST_KEY_TIME, SCAN_BUFFER
    now = time.time(); interval = now - LAST_KEY_TIME; LAST_KEY_TIME = now
    try:
        if key == Key.enter:
            barcode = "".join(SCAN_BUFFER).strip()
            if barcode:
                is_dup = barcode in BARCODE_HISTORY
                if is_dup: pull_back_and_select()
                else: BARCODE_HISTORY.add(barcode)
                ui.root.after(0, ui.update_ui, barcode, is_dup)
            SCAN_BUFFER = []
        elif hasattr(key, 'char') and key.char:
            if interval > SCAN_SPEED_THRESHOLD: SCAN_BUFFER = []
            SCAN_BUFFER.append(key.char)
    except: pass

if __name__ == "__main__":
    ui = PullBackUI()
    threading.Thread(target=lambda: keyboard.Listener(on_press=on_press).start(), daemon=True).start()
    ui.root.mainloop()
