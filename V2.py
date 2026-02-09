import time
import winsound
import threading
import tkinter as tk
from pynput import keyboard
from pynput.keyboard import Controller, Key

# --- 配置 ---
BARCODE_HISTORY = set()
SCAN_BUFFER = []
LAST_KEY_TIME = 0
SCAN_SPEED_THRESHOLD = 0.05 
kb_controller = Controller()

class PullBackUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("智能拉回版")
        self.root.geometry("320x160+100+100")
        self.root.attributes("-topmost", True, "-alpha", 0.9)
        self.root.overrideredirect(True)

        self.main_frame = tk.Frame(self.root, bg="#2c3e50", bd=2)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.status_label = tk.Label(self.main_frame, text="🛡️ 监听中：重复将强制拉回", 
                                     font=("微软雅黑", 10, "bold"), fg="white", bg="#34495e")
        self.status_label.pack(fill=tk.X)
        
        self.log_area = tk.Label(self.main_frame, text="", font=("Consolas", 9), 
                                 fg="#ecf0f1", bg="#2c3e50", justify="left", anchor="nw")
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.count_lbl = tk.Label(self.main_frame, text="总计: 0", font=("微软雅黑", 8), fg="#95a5a6", bg="#2c3e50")
        self.count_lbl.pack(side=tk.RIGHT, padx=10)

        # 拖动与缩放绑定
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        self.grip = tk.Frame(self.root, width=15, height=15, cursor="size_nw_se", bg="#34495e")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<B1-Motion>", self.do_resize)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="🗑️ 清空历史", command=self.clear_history)
        self.menu.add_command(label="❌ 退出", command=self.root.quit)
        self.root.bind("<Button-3>", lambda e: self.menu.post(e.x_root, e.y_root))
        self.logs = []

    def start_move(self, event): self.x, self.y = event.x, event.y
    def do_move(self, event):
        self.root.geometry(f"+{self.root.winfo_x() + event.x - self.x}+{self.root.winfo_y() + event.y - self.y}")
    def do_resize(self, event):
        self.root.geometry(f"{max(200, event.x_root - self.root.winfo_x())}x{max(100, event.y_root - self.root.winfo_y())}")
    def clear_history(self):
        BARCODE_HISTORY.clear(); self.logs = []; self.update_ui("已清空", False)

    def update_ui(self, code, is_duplicate):
        # 重复变红，正常变绿
        color = "#e74c3c" if is_duplicate else "#27ae60"
        self.status_label.config(text=f"{'⚠️ 重复已锁定' if is_duplicate else '✅ 正常'}: {code}", bg=color)
        self.main_frame.config(bg=color); self.log_area.config(bg=color)
        self.count_lbl.config(bg=color, text=f"总计: {len(BARCODE_HISTORY)}")
        
        ts = time.strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {'[重]' if is_duplicate else '[新]'} {code}")
        if len(self.logs) > 8: self.logs.pop(0)
        self.log_area.config(text="\n".join(self.logs))
        if is_duplicate: winsound.Beep(1200, 600) # 重复时响铃

# --- 核心拦截与“拉回”逻辑 ---
def pull_back_and_select():
    """B方法升级版：回跳并全选，不删除"""
    # 1. 强行回跳：模拟 Shift+Tab 
    with kb_controller.pressed(Key.shift):
        kb_controller.press(Key.tab)
        kb_controller.release(Key.tab)
    
    time.sleep(0.1) # 等待焦点切换完成
    
    # 2. 全选高亮：模拟 Ctrl+A (如果是Mac请改Key.cmd)
    with kb_controller.pressed(Key.ctrl):
        kb_controller.press('a')
        kb_controller.release('a')

def on_press(key):
    global LAST_KEY_TIME, SCAN_BUFFER
    now = time.time()
    interval = now - LAST_KEY_TIME
    LAST_KEY_TIME = now
    try:
        if key == Key.enter:
            barcode = "".join(SCAN_BUFFER).strip()
            if barcode:
                is_dup = barcode in BARCODE_HISTORY
                if is_dup:
                    # 发现重复，执行 B 方法：拉回并全选
                    pull_back_and_select()
                else:
                    BARCODE_HISTORY.add(barcode)
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
