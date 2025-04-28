import os
import subprocess
import shutil
import json
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import psutil
import pyautogui
import keyboard
import win32gui
import win32con
import win32clipboard

# Paths
APP_DATA_FOLDER = os.path.join(os.environ['APPDATA'], 'TFDLoader')
SETTINGS_FILE = os.path.join(APP_DATA_FOLDER, 'settings.json')

# Utilities
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_settings(settings):
    os.makedirs(APP_DATA_FOLDER, exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def copy_files(src, dst):
    try:
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        update_status("Copy complete.")
    except Exception as e:
        error_message(f"Failed to copy files: {e}")
        return False
    return True

def unblock_file(path):
    try:
        subprocess.run(["powershell", "-Command", f"Unblock-File '{path}'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        error_message(f"Failed to unblock file: {e}")
        return False
    return True

def set_clipboard(text):
    try:
        subprocess.run(["powershell", "-Command", f"Set-Clipboard -Value '{text}'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        error_message(f"Failed to set clipboard: {e}")
        return False
    return True

def bring_cmd_window_to_front(window_title_contains):
    def enum_windows_callback(hwnd, lParam):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if window_title_contains.lower() in title.lower():
                lParam.append(hwnd)

    hwnds = []
    win32gui.EnumWindows(enum_windows_callback, hwnds)
    if hwnds:
        hwnd = hwnds[0]
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    return False

def get_clipboard_text():
    win32clipboard.OpenClipboard()
    data = win32clipboard.GetClipboardData()
    win32clipboard.CloseClipboard()
    return data

def paste_key_and_enter():
    key = get_clipboard_text()
    update_status(f"Pasting key: {key}")
    pyautogui.typewrite(key)
    keyboard.press_and_release('enter')

def launch_loader_and_wait_for_key(bat_path):
    update_status("Launching loader...")
    if not os.path.exists(bat_path):
        error_message(f"{bat_path} does not exist!")
        return False

    try:
        subprocess.Popen(f'cmd.exe /c start "" "{bat_path}"', shell=True)
    except Exception as e:
        error_message(f"Failed to launch loader: {e}")
        return False

    root.after(2000, try_bring_cmd_front)
    return True

def try_bring_cmd_front():
    if bring_cmd_window_to_front("rundll32.exe") or bring_cmd_window_to_front("cmd.exe"):
        update_status("CMD window found and brought to front.")
        root.after(5000, paste_key_and_enter)
    else:
        error_message("Could not find CMD window.")

def is_process_running(name):
    return any(name.lower() in proc.info['name'].lower() for proc in psutil.process_iter(['name']) if proc.info['name'])

def kill_process(name):
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.info['name'] and name.lower() in proc.info['name'].lower():
            try:
                proc.kill()
                return True
            except Exception as e:
                update_status(f"Error killing process {name}: {e}")
    return False

def kill_open_windows():
    for proc_name in ["cmd.exe", "rundll32.exe", "TFD.bat"]:
        if is_process_running(proc_name):
            update_status(f"Killing {proc_name}...")
            kill_process(proc_name)

# GUI Functions
def update_status(message):
    status_label.config(text=message)
    status_label.update_idletasks()

def error_message(message):
    update_status(f"Error: {message}")
    messagebox.showerror("Error", message)

def countdown(seconds, callback=None):
    if seconds >= 0:
        update_status(f"Countdown: {seconds} seconds remaining...")
        root.after(1000, countdown, seconds - 1, callback)
    else:
        if callback:
            callback()

def start_process_flow():
    src, dst, key_value = src_entry.get(), dst_entry.get(), key_entry.get()
    if not os.path.exists(src):
        error_message(f"Source path {src} does not exist!")
        return

    save_settings({"source_path": src, "destination_path": dst, "key_value": key_value})
    progress_bar.start()
    update_status("Starting operations...")

    if not (copy_files(src, dst) and unblock_file(os.path.join(dst, "TFD.bat")) and set_clipboard(key_value)):
        progress_bar.stop()
        return

    if launch_loader_and_wait_for_key(os.path.join(dst, "TFD.bat")):
        countdown(10, after_loader)
    else:
        update_status("Failed to launch loader.")
        progress_bar.stop()

def after_loader():
    subprocess.run(["start", "steam://run/2074920"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_blackcipher()

def wait_for_blackcipher():
    if is_process_running("BlackCipher64.aes"):
        update_status("BlackCipher detected. Waiting 20 seconds...")
        countdown(20, kill_blackcipher)
    else:
        update_status("BlackCipher not found, retrying...")
        root.after(3000, wait_for_blackcipher)

def kill_blackcipher():
    if kill_process("BlackCipher64.aes"):
        update_status("Attempting to kill BlackCipher...")
        root.after(3000, check_blackcipher_killed)
    else:
        update_status("Retrying kill...")
        root.after(3000, kill_blackcipher)

def check_blackcipher_killed():
    if not is_process_running("BlackCipher64.aes"):
        update_status("BlackCipher killed successfully.")
        kill_open_windows()
        progress_bar.stop()
        messagebox.showinfo("Success", "Process completed successfully!")
        countdown(5, root.destroy)
    else:
        kill_process("BlackCipher64.aes")
        root.after(3000, check_blackcipher_killed)

def on_start_button_click():
    root.after(100, start_process_flow)

def on_settings_button_click():
    settings = load_settings()
    src_entry.delete(0, tk.END)
    dst_entry.delete(0, tk.END)
    key_entry.delete(0, tk.END)
    if settings:
        src_entry.insert(0, settings.get("source_path", ""))
        dst_entry.insert(0, settings.get("destination_path", ""))
        key_entry.insert(0, settings.get("key_value", ""))

def browse_folder(entry_field):
    path = filedialog.askdirectory(title="Select Folder")
    if path:
        entry_field.delete(0, tk.END)
        entry_field.insert(0, path)

def on_f1_press(event=None):
    update_status("F1 pressed: Loading settings...")
    on_settings_button_click()

# GUI Setup
root = tk.Tk()
root.title("TFD Loader")
root.geometry("500x550")
root.configure(bg="#1e1e1e")
root.bind('<F1>', on_f1_press)

style = ttk.Style()
style.theme_use('clam')
style.configure(".", background="#1e1e1e", foreground="#c7c7c7", font=("Segoe UI", 10))
style.configure("TButton", background="#333333", foreground="#c7c7c7", font=("Segoe UI", 10), relief="flat")
style.map("TButton", background=[('active', '#555555')])
style.configure("TFrame", background="#1e1e1e")
style.configure("TProgressbar", background="#007acc", troughcolor="#2a2a2a")

frame = ttk.Frame(root, padding=20)
frame.pack(fill="both", expand=True)

def create_label(text):
    return ttk.Label(frame, text=text)

def create_entry():
    return tk.Entry(frame, bg="#2a2d2e", fg="#ffffff", insertbackground="#ffffff", font=("Consolas", 10))

def create_button(text, command):
    return ttk.Button(frame, text=text, command=command)

src_entry = create_entry()
dst_entry = create_entry()
key_entry = create_entry()

widgets = [
    ("Source Path", src_entry, lambda: browse_folder(src_entry)),
    ("Destination Path", dst_entry, lambda: browse_folder(dst_entry)),
    ("Key Value", key_entry, None)
]

for label_text, entry_widget, button_command in widgets:
    create_label(label_text).pack(anchor="w", pady=(10, 2))
    entry_widget.pack(pady=2, fill="x")
    if button_command:
        create_button("Browse", button_command).pack(pady=2)

create_button("Start Process", on_start_button_click).pack(pady=15, fill="x")
create_button("Load Settings", on_settings_button_click).pack(pady=5, fill="x")

progress_bar = ttk.Progressbar(frame, orient="horizontal", length=400, mode="indeterminate")
progress_bar.pack(pady=20)

status_label = ttk.Label(frame, text="Status: Waiting for user input...", anchor="center", width=60, wraplength=400)
status_label.pack(pady=10)

on_settings_button_click()
root.mainloop()
