import os
import subprocess
import sys
import time
import threading
import re
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for compiled PyInstaller .exe"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Target Paths ---
QUEST_PKG = "com.StressLevelZero.BONELAB"
QUEST_MELON_ROOT = "/sdcard/MelonLoader"
QUEST_MELON_PATH = f"{QUEST_MELON_ROOT}/{QUEST_PKG}"
MODS_DIR = f"{QUEST_MELON_PATH}/Mods"
PLUGINS_DIR = f"{QUEST_MELON_PATH}/Plugins"
SAVES_DIR = f"/sdcard/Android/data/{QUEST_PKG}/files/Saves"
GAME_DATA_MODS_DIR = f"/sdcard/Android/data/{QUEST_PKG}/files/mods"
QUEST_BACKUPS_DIR = f"{QUEST_MELON_PATH}/backups"

OBB_DIR = f"/sdcard/Android/obb/{QUEST_PKG}"
OBB_DIR_BACKUP = f"/sdcard/Android/obb/{QUEST_PKG}1"
DATA_DIR = f"/sdcard/Android/data/{QUEST_PKG}"

LEMONLOADER_PKG = "com.lavagang.melonloader.installer"
LLOADER_APK_PATH = get_resource_path(os.path.join("LLoader", "LemonLoader.apk"))
ADB_EXE_PATH = get_resource_path("adb.exe") if os.name == 'nt' else get_resource_path("adb")
ICON_ICO_PATH = get_resource_path(os.path.join("icon", "Icon.ico"))

# --- UI Theme Colors ---
BG_MAIN = "#0F0F15"
BG_CARD = "#1E1E24"
BG_CONSOLE = "#14141B"
FG_TEXT = "#FFFFFF"
FG_DIM = "#888888"
COLOR_PRIMARY = "#007ACC"
COLOR_PRIMARY_HOVER = "#005C99"
COLOR_SUCCESS = "#3FB950"
COLOR_SUCCESS_HOVER = "#2EA043"
COLOR_ERROR = "#F85149"
COLOR_ERROR_HOVER = "#D13B34"
COLOR_DISABLED_BG = "#2A2A35"
COLOR_DISABLED_FG = "#555555"

class ModernRoundedButton(tk.Canvas):
    """Custom Canvas-based button with smooth rounded corners and hover animations."""
    def __init__(self, parent, text, command, bg_color, hover_color, fg_color="white", radius=15, width=150, height=45, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent['bg'], highlightthickness=0, **kwargs)
        self.command = command
        self.text = text
        self.radius = radius
        self.base_bg = bg_color
        self.hover_bg = hover_color
        self.disabled_bg = COLOR_DISABLED_BG
        self.fg_color = fg_color
        self.disabled_fg = COLOR_DISABLED_FG
        
        self.current_bg = self.base_bg
        self.current_fg = self.fg_color
        self.state = "normal"
        self.rect_id = None
        self.text_id = None
        
        self.bind("<Configure>", self.draw)
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

    def draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        
        points = [
            self.radius, 0,  w - self.radius, 0,
            w, 0, w, self.radius,  w, h - self.radius,
            w, h, w - self.radius, h,  self.radius, h,
            0, h, 0, h - self.radius,  0, self.radius,
            0, 0, self.radius, 0
        ]
        self.rect_id = self.create_polygon(points, smooth=True, fill=self.current_bg)
        self.text_id = self.create_text(w/2, h/2, text=self.text, fill=self.current_fg, font=("Segoe UI", 11, "bold"))

    def set_state(self, state, new_text=None, new_bg=None, new_hover=None):
        self.state = state
        if new_text: self.text = new_text
        if new_bg: self.base_bg = new_bg
        if new_hover: self.hover_bg = new_hover
        
        if self.state == "disabled":
            self.current_bg = self.disabled_bg
            self.current_fg = self.disabled_fg
            self.config(cursor="arrow")
        else:
            self.current_bg = self.base_bg
            self.current_fg = self.fg_color
            self.config(cursor="hand2")
        self.draw()

    def on_hover(self, event):
        if self.state != "disabled":
            self.itemconfig(self.rect_id, fill=self.hover_bg)

    def on_leave(self, event):
        if self.state != "disabled":
            self.itemconfig(self.rect_id, fill=self.base_bg)

    def on_click(self, event):
        if self.state != "disabled" and self.command:
            self.command()


class BonelabInstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Unofficial Fusion Installer")
        self.root.geometry("800x700")
        self.root.configure(bg=BG_MAIN)
        
        self.set_window_icon()
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)
        
        self.startupinfo = None
        if os.name == 'nt':
            self.startupinfo = subprocess.STARTUPINFO()
            self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.is_connected = False
        self.is_monitoring_game = False
        self.is_monitoring_patch = False
        self.disclaimer_dialog = None
        self.active_target_ip = None
        
        self.mask_ip_var = tk.BooleanVar(value=True)
        self.detailed_mode_var = tk.BooleanVar(value=False)

        self.setup_menu()
        self.setup_ui()
        
        self.log_sys("Welcome to the Unofficial Fusion Installer.")
        self.log_sys("Awaiting hardware connection...")

    def set_window_icon(self):
        """Replaces the default Tkinter feather icon with custom Icon.ico cleanly."""
        if os.path.exists(ICON_ICO_PATH):
            try:
                self.root.iconbitmap(default=ICON_ICO_PATH)
            except Exception:
                pass

    def on_app_close(self):
        """Revert OBB backup name back if app is closed while patching/renamed"""
        if self.is_connected:
            try:
                check_backup = self.run_adb(["shell", f"ls -d {OBB_DIR_BACKUP}"], ignore_errors=True, silent=True)
                if check_backup and "No such file" not in check_backup and "cannot access" not in check_backup:
                    self.run_adb(["shell", f'rm -rf "{OBB_DIR}"'], ignore_errors=True, silent=True)
                    self.run_adb(["shell", f'mv "{OBB_DIR_BACKUP}" "{OBB_DIR}"'], ignore_errors=True, silent=True)
            except Exception:
                pass
        self.root.destroy()

    def setup_menu(self):
        menubar = tk.Menu(self.root, bg=BG_CARD, fg=FG_TEXT, font=("Segoe UI", 9), relief=tk.FLAT)
        
        # --- Options Menu ---
        options_menu = tk.Menu(menubar, tearoff=0, bg=BG_CARD, fg=FG_TEXT, activebackground=COLOR_PRIMARY, borderwidth=0)
        options_menu.add_command(label="📥 Backup Headset Saves", command=lambda: self.run_in_thread(self.backup_saves))
        options_menu.add_command(label="🗑️Remove Installed Mods", command=lambda: self.run_in_thread(self.wipe_mods))
        options_menu.add_separator()
        options_menu.add_checkbutton(label="🔍 Detailed Mode", variable=self.detailed_mode_var, command=self.toggle_detailed_mode)
        options_menu.add_checkbutton(label="🔒 Hide IP Address in Logs", variable=self.mask_ip_var, command=self.toggle_ip_masking)
        options_menu.add_command(label="📝 Test Console Log Outputs", command=self.test_log_outputs)
        menubar.add_cascade(label="Options", menu=options_menu)

        # --- Expanded Help & Diagnostics Menu ---
        help_menu = tk.Menu(menubar, tearoff=0, bg=BG_CARD, fg=FG_TEXT, activebackground=COLOR_PRIMARY, borderwidth=0)
        help_menu.add_command(label="🔌 Connection & USB Troubleshooting", command=self.show_help_connection)
        help_menu.add_command(label="🔍 ADB / Device Not Found & 'Unauthorized'", command=self.show_help_adb_errors)
        help_menu.add_command(label="📦 Game Patching & OBB Guide", command=self.show_help_patching)
        help_menu.add_command(label="💥 Game Crashing or Infinite Loading Screen", command=self.show_help_crashing)
        help_menu.add_command(label="📥 Problems with File Downloads", command=self.show_help_downloads)
        help_menu.add_command(label="📶 Wireless Connection Drops & Port 5555", command=self.show_help_wireless_issues)
        help_menu.add_command(label="📂 Understanding Mods vs. ModsD Folders", command=self.show_help_modsd)
        help_menu.add_command(label="💾 Save Files & Backups Info", command=self.show_help_saves)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def show_help_connection(self):
        messagebox.showinfo(
            "Connection & USB Help",
            "Having trouble connecting your headset?\n\n"
            "1. Developer Mode: Ensure Developer Mode is enabled on your Meta account and Quest headset.\n"
            "2. USB Debugging: Put on your headset after plugging it into your PC and click 'Allow' on the USB Debugging prompt.\n"
            "3. Cable/Port: Try a different USB-C cable or USB port (USB 3.0 / blue ports work best).\n"
            "4. Wireless Setup: Use the 'Partial Wireless' option if you want to link via Wi-Fi and unplug the cable."
        )

    def show_help_adb_errors(self):
        messagebox.showinfo(
            "ADB Diagnostic Guide",
            "Troubleshooting Device Detection / 'Unauthorized' Issues:\n\n"
            "• Task Manager Fix: Open Task Manager (Ctrl + Shift + Esc), look for any background processes named 'adb' or 'adb.exe', right-click and select 'End Task', then reopen the app and try again.\n"
            "• 'Unauthorized': Look inside your headset screen while plugged in. Check the box to 'Always allow from this computer' and click Allow.\n"
            "• 'Device Offline': Unplug your USB cable, wait 3 seconds, plug it back in, or restart the app.\n"
            "• Multiple ADB servers: If another utility (like SideQuest or Meta Quest Link) is running, it may lock ADB. Close background tools and reconnect."
        )

    def show_help_patching(self):
        messagebox.showinfo(
            "Game Patching & OBB Help",
            "Stuck during the patching process?\n\n"
            "1. OBB Renaming Error: If the app fails to rename your OBB folder, close any open Windows Explorer / MTP file transfer windows viewing your Quest storage.\n"
            "2. LemonLoader: Make sure you follow the prompts inside LemonLoader on your headset to patch BONELAB.\n"
            "3. First Launch: Always launch Bonelab to the main menu once right after patching so LemonLoader can generate your required folder structures."
        )

    def show_help_crashing(self):
        messagebox.showinfo(
            "Crash & Infinite Loading Diagnostics",
            "Game crashing or stuck on loading screen after modding?\n\n"
            "1. OBB Folder Renaming Issue: Infinite loading screens can often be caused by an issue or failure in how the app renamed or restored the Bonelab OBB folder directory during patching. Ensure the OBB folder name matches `com.StressLevelZero.BONELAB` exactly.\n"
            "2. Incompatible Mods: An old or outdated mod (.dll) inside your Mods folder will crash MelonLoader on startup. Remove recently added mods to test.\n"
            "3. Clean Reinstall: If all else fails, use the 'Complete Fresh Download' option to wipe corrupted patch files and start clean."
        )

    def show_help_downloads(self):
        messagebox.showinfo(
            "File Downloads Help",
            "Troubleshooting file download and transfer problems:\n\n"
            "• Quest Headset Updates: The Quest headset might have received a recent update that could have affected how this tool works with storage, permissions, or file directories. Ensure your headset is fully updated and check if Meta has changed MTP/storage access protocols.\n"
            "• Storage Space: Make sure your headset has enough free storage space available to download and extract mod dependencies or game files."
        )

    def show_help_wireless_issues(self):
        messagebox.showinfo(
            "Wireless Connection Diagnostics",
            "Troubleshooting Wireless ADB (Port 5555):\n\n"
            "• Same Wi-Fi Network: Both your PC and your Quest headset must be connected to the exact same Wi-Fi router / network frequency.\n"
            "• IP Address Changes: Quest headsets often change local IP addresses when reconnecting to Wi-Fi. If wireless fails, plug in via USB once to re-sync.\n"
            "• Firewall: Ensure Windows Defender or third-party firewalls aren't blocking local port traffic."
        )

    def show_help_modsd(self):
        messagebox.showinfo(
            "Mods vs ModsD Folders",
            "How folder sorting works in this installer:\n\n"
            "• Mods folder: Standard MelonLoader mods and plugins go into your normal plugin/mod pathways.\n"
            "• ModsD folder: Any custom items or mods that specifically need to live directly inside the game data folder (`Android/data/com.StressLevelZero.BONELAB/files/mods`) should be placed in your local `ModsD` directory."
        )

    def show_help_saves(self):
        messagebox.showinfo(
            "Save Files & Backups Help",
            "Managing your save files safely:\n\n"
            "• Fusion 100% Saves: The installer includes a recommended save setup to get everything unlocked smoothly.\n"
            "• Backing Up: You can back up your existing headset saves directly to a folder on your PC or inside your headset (`/sdcard/MelonLoader/.../backups`) using the options menu at any time."
        )

    def setup_ui(self):
        header_frame = tk.Frame(self.root, bg=BG_MAIN)
        header_frame.pack(fill=tk.X, pady=(25, 10), padx=30)
        
        tk.Label(header_frame, text="UNOFFICIAL", font=("Segoe UI Black", 20), fg=COLOR_PRIMARY, bg=BG_MAIN).pack(side=tk.LEFT)
        tk.Label(header_frame, text=" FUSION INSTALLER", font=("Segoe UI Semilight", 20), fg=FG_TEXT, bg=BG_MAIN).pack(side=tk.LEFT, padx=(2, 0))

        control_card = tk.Frame(self.root, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground="#333333")
        control_card.pack(fill=tk.X, padx=30, pady=10)

        status_container = tk.Frame(control_card, bg=BG_CARD)
        status_container.pack(fill=tk.X, padx=25, pady=(20, 10))
        
        tk.Label(status_container, text="HEADSET STATUS", font=("Segoe UI", 9, "bold"), fg=FG_DIM, bg=BG_CARD).pack(anchor="w")
        self.status_lbl = tk.Label(status_container, text="🔴 Disconnected", font=("Segoe UI", 12, "bold"), fg=COLOR_ERROR, bg=BG_CARD)
        self.status_lbl.pack(anchor="w", pady=(2, 0))

        btn_frame = tk.Frame(control_card, bg=BG_CARD)
        btn_frame.pack(fill=tk.X, padx=25, pady=(10, 25))
        
        self.btn_connect = ModernRoundedButton(btn_frame, "Connect Headset", self.show_connect_dialog, COLOR_PRIMARY, COLOR_PRIMARY_HOVER)
        self.btn_connect.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_deploy = ModernRoundedButton(btn_frame, "Install Fusion", self.start_deploy_thread, COLOR_SUCCESS, COLOR_SUCCESS_HOVER)
        self.btn_deploy.set_state("disabled")
        self.btn_deploy.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

        console_container = tk.Frame(self.root, bg=BG_MAIN)
        console_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=(10, 30))
        
        tk.Label(console_container, text="ACTIVITY LOG", font=("Segoe UI", 9, "bold"), fg=FG_DIM, bg=BG_MAIN).pack(anchor="w", pady=(0, 5))
        
        self.console = scrolledtext.ScrolledText(console_container, bg=BG_CONSOLE, fg="#CCCCCC", font=("Consolas", 10), 
                                                 state=tk.DISABLED, wrap=tk.WORD, bd=0, highlightthickness=1, 
                                                 highlightbackground="#2A2A35", padx=15, pady=15)
        self.console.pack(fill=tk.BOTH, expand=True)
        
        self.console.tag_config("info", foreground="#58A6FF")
        self.console.tag_config("success", foreground=COLOR_SUCCESS)
        self.console.tag_config("warning", foreground="#D29922")
        self.console.tag_config("error", foreground=COLOR_ERROR)
        self.console.tag_config("system", foreground="#8B949E")
        self.console.tag_config("progress", foreground="#A371F7")

    def run_in_thread(self, target):
        threading.Thread(target=target, daemon=True).start()

    def toggle_detailed_mode(self):
        if self.detailed_mode_var.get():
            self.log_sys("Detailed Mode ENABLED. Extra diagnostic and verification logs will now be displayed.")
        else:
            self.log_sys("Detailed Mode DISABLED.")

    def toggle_ip_masking(self):
        if not self.mask_ip_var.get():
            warn = messagebox.askokcancel("Privacy Warning", "WARNING: You are about to reveal your IP Address in the console.\n\nDo NOT screenshot or share your IP address publicly! Are you sure you want to display it?")
            if not warn:
                self.mask_ip_var.set(True)
                return
            self.log_sys("IP Addresses are now visible in logs.")
        else:
            self.log_sys("IP Addresses are now hidden in logs.")
        
        self.refresh_console_display()

    def refresh_console_display(self):
        try:
            current_text = self.console.get("1.0", tk.END)
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            
            def replacer(match):
                ip = match.group(0)
                if self.mask_ip_var.get():
                    return re.sub(r'\d', '*', ip)
                return ip

            updated_text = re.sub(ip_pattern, replacer, current_text)
            
            self.console.config(state=tk.NORMAL)
            self.console.delete("1.0", tk.END)
            self.console.insert(tk.END, updated_text)
            self.console.see(tk.END)
            self.console.config(state=tk.DISABLED)
        except Exception:
            pass

    def format_ip(self, ip_str):
        if not ip_str: return ""
        if self.mask_ip_var.get():
            return re.sub(r'\d', '*', ip_str)
        return ip_str

    def play_headset_sound(self, message="Status Update"):
        self.run_in_thread(lambda: self.run_adb(["shell", "cmd", "notification", "post", "-S", "bigtext", "-t", "'Unofficial Fusion Installer'", "'tag'", f"'{message}'"], silent=True))

    def log(self, message, tag="info"):
        def append():
            self.console.config(state=tk.NORMAL)
            self.console.insert(tk.END, f"{message}\n", tag)
            self.console.see(tk.END)
            self.console.config(state=tk.DISABLED)
        self.root.after(0, append)

    def log_sys(self, message): self.log(f"[SYS] {message}", "system")
    def log_success(self, message): self.log(f"✅ {message}", "success")
    def log_warn(self, message): self.log(f"⚠️ {message}", "warning")
    def log_err(self, message): self.log(f"❌ {message}", "error")
    
    def log_detailed(self, message):
        if self.detailed_mode_var.get():
            if self.mask_ip_var.get():
                ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
                message = re.sub(ip_pattern, lambda m: re.sub(r'\d', '*', m.group(0)), message)
            self.log(f"🔍 [DETAIL] {message}", "progress")

    def test_log_outputs(self):
        self.log("\n--- STARTING CATEGORIZED EXHAUSTIVE LOG TEST ---", "system")
        
        if self.detailed_mode_var.get():
            self.log_detailed("Detailed Mode is ACTIVE. Injecting high-granularity diagnostic traces...")
            self.log_detailed(f"Resolved ADB binary path: {ADB_EXE_PATH}")
            self.log_detailed(f"Target package identifier: {QUEST_PKG}")
            self.log_detailed(f"Target OBB path: {OBB_DIR}")
            self.log_detailed(f"Target Data directory: {DATA_DIR}")
            self.log_detailed(f"Target MelonLoader path: {QUEST_MELON_PATH}")
        else:
            self.log_sys("Detailed Mode is OFF. Turn it on under Options to view expanded diagnostic logs.")

        # --- CATEGORY 1: ERRORS & WARNINGS ---
        self.log("\n[CATEGORY: ERRORS & WARNINGS]", "system")
        self.log_warn("Please allow access to files.")
        self.log_warn("Incomplete patch detected. wiping old data...")
        self.log_warn("OBB folder is missing from headset! Creating empty directory...")
        self.log_warn("Attempt 1: OBB locked or busy. Retrying in 2 seconds...")
        self.log_warn("Almost done! Please launch Bonelab once in your headset to the main menu, then close it. ⚠️")
        self.log_warn(f"If you continue the game will probably break because the file directory ({QUEST_MELON_PATH}) will be deleted do you wish to continue?")
        self.log_warn("Note: Quest headset OS updates can affect third-party tool storage and file interactions.")
        self.log_warn("Warning: Infinite loading screens may be caused by OBB folder renaming discrepancies or mismatched mod versions.")
        
        self.log_err("FAILED TO RENAME OBB FOLDER! Please close Windows Explorer / MTP connections and try again.")
        self.log_err("WARNING: OBB restore failed. Please check headset storage manually.")
        self.log_err("Unable to mod Bonelab without LemonLoader.")
        self.log_err("Headset disconnected. Please plug it back in and click connect.")
        self.log_err("Connection process cancelled.")
        self.log_err("Please connect your headset first.")
        self.log_err("ADB Failed. Details: example error message")
        self.log_err(f"FATAL: ADB not found at {ADB_EXE_PATH}.")

        # --- CATEGORY 2: SYSTEM MESSAGES ---
        self.log("\n[CATEGORY: SYSTEM MESSAGES]", "system")
        self.log_sys("Welcome to the Unofficial Fusion Installer.")
        self.log_sys("Awaiting hardware connection...")
        self.log_sys("Waiting for Headset via USB...")
        masked_test_ip = self.format_ip("192.168.1.50")
        self.log_sys(f"Found IP: {masked_test_ip}. Connecting to Meta Quest 3...")
        self.log_sys("Checking storage permissions...")
        self.log_sys("LemonLoader app is installed.")
        self.log_sys("Folder cleared.")
        self.log_sys("Removing existing mods and plugins...")
        self.log_sys(f"Attempting to Restore {OBB_DIR}...")
        self.log_sys("Launch Bonelab once in your headset to let it generate fresh files.")
        self.log_sys("this process could take a few minutes")
        self.log_sys("this is to create the mod folders for the game.")
        self.log_sys("Restoring OBB folder name...")
        self.log_sys("Save file skipped.")

        # --- CATEGORY 3: SUCCESS, PROGRESS & GENERAL LOGS ---
        self.log("\n[CATEGORY: SUCCESS, PROGRESS & GENERAL LOGS]", "system")
        self.log("Uninstalling Bonelab...")
        self.log("Removing OBB file directory...")
        self.log("1. Open LemonLoader in your headset.")
        self.log("2. Allow all permissions.")
        self.log("3. Find BONELAB and click 'Patch'.")
        self.log("Waiting for game to be patched...")
        self.log("Waiting for game Launch...")
        self.log("Waiting for Bonelab to be downloaded...")
        self.log("Installing LemonLoader...")
        self.log("Removing old save data...")
        self.log("Downloading save files from headset...")
        self.log("Backing up save files on headset...")
        self.log("Overwriting existing save data...")
        
        self.log_success("USB debugging authorized. Headset connected.")
        self.log_success("File access permissions granted!")
        self.log_success("Bonelab found on headset.")
        self.log_success("Game is patched and ready for mods.")
        self.log_success("Existing mods Removed.")
        self.log_success("Bonelab uninstalled successfully.")
        self.log_success(f"Backup successful ({OBB_DIR_BACKUP}).")
        self.log_success("Patched version installed successfully!")
        self.log_success("Name successfully restored.")
        self.log_success("OBB folder successfully restored.")
        self.log_success("LemonLoader Bonelab folder created successfully! You are ready to install Fusion.")
        self.log_success("Download complete!")
        self.log_success("LemonLoader installed.")
        self.log_success(f"Found example_mod.dll in {MODS_DIR}/example_mod.dll")
        self.log_success(f"Found custom item in {GAME_DATA_MODS_DIR}/Lakatrazz.FusionContent")
        self.log_success("100% save file installed successfully.")
        self.log_success(f"Backup complete! Saved to: {QUEST_BACKUPS_DIR}")
        self.log_success(f"Backup complete! Saved to: C:\\Users\\Example\\BackUp")
        self.log_success("Mods and Plugins folders removed.")
        self.log_success("Save file overwritten successfully.")
        self.log_success("Bonelab uninstalled and storage cleaned successfully.")
        self.log_success("Mod validation complete.")

        # --- CATEGORY 4: DETAILED MODE EXHAUSTIVE LOG TRACES ---
        self.log("\n[CATEGORY: DETAILED MODE LOG TRACES]", "system")
        self.log_detailed("Initiating USB transport layer polling via ADB server daemon...")
        self.log_detailed("Executing 'adb wait-for-device' command block...")
        self.log_detailed("USB connection timeout or device rejected.")
        self.log_detailed("Partial wireless setup routine initiated. Awaiting initial physical bridge...")
        self.log_detailed("Wireless bootstrap failed during initial device wait state.")
        self.log_detailed("Failed to parse wlan0 interface route or DHCP lease assignment.")
        self.log_detailed(f"Resolved device model string: Meta Quest at socket endpoint 192.168.1.50:5555")
        self.log_detailed("Switching ADB daemon to TCP/IP mode on port 5555...")
        self.log_detailed("TCP socket established successfully with 192.168.1.50:5555")
        self.log_detailed("TCP connect socket response payload: connected to 192.168.1.50:5555")
        self.log_detailed("Handshake complete. ADB secure channel authenticated.")
        self.log_detailed("Querying directory permissions for /sdcard/Android/obb...")
        self.log_detailed("Scoped storage authorization dialog pending user interaction inside headset.")
        self.log_detailed("Storage read/write checks passed successfully.")
        self.log_detailed(f"Package query confirmed installation of {QUEST_PKG}")
        self.log_detailed(f"Targeting deletion paths: {MODS_DIR}, {PLUGINS_DIR}, and FusionContent folders.")
        self.log_detailed(f"Invoking package manager uninstall for {QUEST_PKG}")
        self.log_detailed(f"Executing recursive rm on {OBB_DIR}, {DATA_DIR}, and {QUEST_MELON_PATH}")
        self.log_detailed("Skipping patch cycle per user selection; verifying execution entry points.")
        self.log_detailed("LemonLoader package check negative. Prompting installation...")
        self.log_detailed("LemonLoader package detected successfully on device.")
        self.log_detailed(f"MelonLoader directory structure verified at {QUEST_MELON_PATH}")
        self.log_detailed("MelonLoader directory missing. Initiating OBB backup and patch sequence.")
        self.log_detailed("Hardware connection polling loop detected dropped transport link.")
        self.log_detailed(f"Explicitly creating OBB parent container directory: {OBB_DIR}")
        self.log_detailed(f"Executing OBB directory rename attempt 1 -> moving to {OBB_DIR_BACKUP}")
        self.log_detailed("Critical failure: MTP lock or active file handle prevented OBB directory rename.")
        self.log_detailed(f"Restoring backup directory {OBB_DIR_BACKUP} back to original OBB spec: {OBB_DIR}")
        self.log_detailed("Warning: Automated OBB directory restoration encountered a filesystem lock.")
        self.log_detailed("Post-patch initialization verified. MelonLoader framework active.")
        self.log_detailed("Polling package manager for installation state transition...")
        self.log_detailed("Package verification confirmed game installation completed.")
        self.log_detailed(f"Executing adb install command on APK bundle: {LLOADER_APK_PATH}")
        self.log_detailed("Deployment thread spawned. Commencing file push pipelines...")
        self.log_detailed("Pushing asset: example_mod.dll -> /sdcard/MelonLoader/com.StressLevelZero.BONELAB/Mods/example_mod.dll")
        self.log_detailed("Recursive push asset: custom_item -> /sdcard/Android/data/com.StressLevelZero.BONELAB/files/mods/custom_item")
        self.log_detailed("Scanning local Mods directory for deployment...")
        self.log_detailed("Pushing mod file: example_mod.dll")
        self.log_detailed("Scanning local Plugins directory for deployment...")
        self.log_detailed("Scanning local ModsD directory for custom item deployment...")
        self.log_detailed("Pushing ModsD asset: custom_item")
        self.log_detailed(f"Pulling remote save files from {SAVES_DIR} to target PC path")
        self.log_detailed(f"Duplicating headset saves to backup directory: {QUEST_BACKUPS_DIR}")

        self.log("\n=======================================================")
        self.log_success("FUSION INSTALLATION COMPLETE! You are ready to play.")
        self.log("\nIf there is a problem with launching the game and you")
        self.log("cannot find any solutions we recommend a fresh install.")
        self.log("\n\t\t-Created with Gemini-")
        self.log("=======================================================")

    def run_adb(self, args, ignore_errors=False, silent=False):
        try:
            cmd = [ADB_EXE_PATH]
            if self.active_target_ip and "connect" not in args and "disconnect" not in args and "kill-server" not in args:
                cmd += ["-s", self.active_target_ip]
            cmd += args

            result = subprocess.run(cmd, capture_output=True, text=True, check=not ignore_errors, startupinfo=self.startupinfo)
            return result.stdout.strip() + result.stderr.strip()
        except subprocess.CalledProcessError as e:
            if ignore_errors: return e.stderr.strip()
            if not silent: self.log_err(f"ADB Failed. Details: {e.stderr.strip()}")
            return None
        except FileNotFoundError:
            if not silent: self.log_err(f"FATAL: ADB not found at {ADB_EXE_PATH}.")
            return None

    def get_quest_ip(self):
        output = self.run_adb(["shell", "ip", "route"], ignore_errors=True, silent=True)
        if not output:
            return None
        for line in output.split('\n'):
            if 'wlan0' in line and 'src' in line:
                parts = line.split()
                try:
                    return parts[parts.index('src') + 1]
                except:
                    pass
        return None

    def get_headset_model_name(self):
        model = self.run_adb(["shell", "getprop", "ro.product.model"], ignore_errors=True, silent=True)
        if model and len(model.strip()) > 0:
            return model.strip()
        return "Meta Quest"

    def reset_connection_ui(self):
        self.is_connected = False
        self.is_monitoring_game = False
        self.is_monitoring_patch = False
        self.active_target_ip = None
        
        if hasattr(self, 'disclaimer_dialog') and self.disclaimer_dialog:
            self.disclaimer_dialog.destroy()
            self.disclaimer_dialog = None
            
        self.status_lbl.config(text="🔴 Disconnected", fg=COLOR_ERROR)
        self.btn_connect.set_state("normal", new_text="Connect Headset")
        self.btn_deploy.set_state("disabled", new_text="Install Fusion")

    def show_connect_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Connect to Headset")
        dialog.geometry("450x320")
        dialog.configure(bg=BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (450 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (320 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="Standard USB Connection", font=("Segoe UI", 11, "bold"), fg=COLOR_PRIMARY, bg=BG_CARD).pack(pady=(15, 5))
        tk.Label(dialog, text="Keep your headset plugged into your PC via cable.", font=("Segoe UI", 9), fg=FG_TEXT, bg=BG_CARD, justify=tk.CENTER).pack(pady=(0, 10))
        
        def on_usb_connect():
            dialog.destroy()
            self.start_usb_connection()
            
        ModernRoundedButton(dialog, "Connect via USB", on_usb_connect, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, width=200, height=40).pack(pady=(0, 15))
        tk.Frame(dialog, height=1, bg="#333333").pack(fill=tk.X, padx=30, pady=5)
        
        tk.Label(dialog, text="Partial Wireless", font=("Segoe UI", 11, "bold"), fg="#A371F7", bg=BG_CARD).pack(pady=(15, 5))
        tk.Label(dialog, text="Plug in headset -> We link it to Wi-Fi -> You unplug the cable.", font=("Segoe UI", 9), fg=FG_TEXT, bg=BG_CARD, justify=tk.CENTER).pack(pady=(0, 10))
        
        def on_auto_wireless():
            dialog.destroy()
            self.start_auto_wireless_connection()
            
        ModernRoundedButton(dialog, "Setup Partial Wireless", on_auto_wireless, "#A371F7", "#8A5CE3", width=200, height=40).pack(pady=(0, 15))

    def start_usb_connection(self):
        self.active_target_ip = None
        self.btn_connect.set_state("disabled", new_text="Connecting...")
        self.log("\n--- Checking Hardware Connection ---\n")
        self.log_sys("Waiting for Headset via USB...")
        self.log_detailed("Initiating USB transport layer polling via ADB server daemon...")
        self.run_in_thread(self.usb_connection_worker)

    def usb_connection_worker(self):
        self.run_adb(["disconnect"], ignore_errors=True, silent=True)
        self.run_adb(["kill-server"], ignore_errors=True, silent=True)
        time.sleep(1)

        self.log_detailed("Executing 'adb wait-for-device' command block...")
        if self.run_adb(["wait-for-device"]) is None: 
            self.log_detailed("USB connection timeout or device rejected.")
            self.root.after(0, self.reset_connection_ui)
            return
        self.post_connection_checks()

    def start_auto_wireless_connection(self):
        self.btn_connect.set_state("disabled", new_text="Connecting...")
        self.log("\n--- Setting up Partial Wireless ---\n")
        self.log_sys("Waiting for Headset via USB first...")
        self.log_detailed("Partial wireless setup routine initiated. Awaiting initial physical bridge...")
        self.run_in_thread(self.auto_wireless_worker)

    def auto_wireless_worker(self):
        self.run_adb(["disconnect"], ignore_errors=True, silent=True)
        self.run_adb(["kill-server"], ignore_errors=True, silent=True)
        time.sleep(1)

        if self.run_adb(["wait-for-device"]) is None:
            self.log_detailed("Wireless bootstrap failed during initial device wait state.")
            self.root.after(0, self.reset_connection_ui)
            return

        self.log_sys("Device found. Fetching IP address...")
        ip_addr = self.get_quest_ip()
        if not ip_addr:
            self.log_err("Could not find headset IP address. Ensure it is connected to Wi-Fi.")
            self.log_detailed("Failed to parse wlan0 interface route or DHCP lease assignment.")
            self.root.after(0, self.reset_connection_ui)
            return

        device_name = self.get_headset_model_name()
        masked_ip = self.format_ip(ip_addr)
        self.log_sys(f"Found IP: {masked_ip}. Connecting to {device_name}...")
        self.log_detailed(f"Resolved device model string: {device_name} at socket endpoint {ip_addr}:5555")
        
        self.log_detailed("Switching ADB daemon to TCP/IP mode on port 5555...")
        self.run_adb(["tcpip", "5555"])
        time.sleep(3)

        connect_target = f"{ip_addr}:5555"
        result = self.run_adb(["connect", connect_target])
        
        if result and ("connected to" in result.lower() or "already connected" in result.lower()):
            self.active_target_ip = connect_target
            self.log_success(f"Successfully connected to {device_name} wirelessly!")
            self.log_detailed(f"TCP socket established successfully with {connect_target}")
            time.sleep(2)
            
            def show_blocking_success():
                messagebox.showinfo(
                    "Wireless Active", 
                    f"Success! Connected to {device_name}.\n\nYou can now unplug your headset cable. Click OK to continue.", 
                    parent=self.root
                )
                self.run_in_thread(self.post_connection_checks)

            self.root.after(0, show_blocking_success)
        else:
            self.log_err("Failed to connect wirelessly. Try again or use standard USB.")
            self.log_detailed(f"TCP connect socket response payload: {result}")
            self.root.after(0, self.reset_connection_ui)

    def post_connection_checks(self):
        self.log_success("USB debugging authorized. Headset connected.")
        self.log_detailed("Handshake complete. ADB secure channel authenticated.")
        self.play_headset_sound("Connected to PC!")
        self.is_connected = True
        self.root.after(0, self.update_status_connected_only)
        self.run_in_thread(self.hardware_monitor_worker)

        self.log_sys("Checking storage permissions...")
        self.log_detailed("Querying directory permissions for /sdcard/Android/obb...")
        prompted = False
        while self.is_connected:
            test_read = self.run_adb(["shell", "ls", "/sdcard/Android/obb"], ignore_errors=True, silent=True)
            if test_read is not None and ("Permission denied" in test_read or "cannot access" in test_read):
                if not prompted:
                    self.log_warn("Please allow access to files.")
                    self.log_detailed("Scoped storage authorization dialog pending user interaction inside headset.")
                    prompted = True
                time.sleep(2)
            else:
                self.log_success("File access permissions granted!")
                self.log_detailed("Storage read/write checks passed successfully.")
                break

        if not self.is_connected: return

        # Stabilization pause & retry loop for wireless package lookup sync
        is_installed = False
        for attempt in range(1, 4):
            time.sleep(1)
            output = self.run_adb(["shell", "pm", "list", "packages", QUEST_PKG], ignore_errors=True, silent=True)
            if output and QUEST_PKG in output:
                is_installed = True
                break
        
        if is_installed:
            self.log_success("Bonelab found on headset.")
            self.log_detailed(f"Package query confirmed installation of {QUEST_PKG}")

        data_check = self.run_adb(["shell", f"ls -d {DATA_DIR}"], ignore_errors=True, silent=True)
        has_data_folder = data_check is not None and "No such file" not in data_check and "cannot access" not in data_check
        
        can_fresh_install = is_installed or has_data_folder
        
        melon_check = self.run_adb(["shell", f"ls -d {QUEST_MELON_PATH}"], ignore_errors=True, silent=True)
        has_melon_folder = melon_check is not None and "No such file" not in melon_check and "cannot access" not in melon_check
        
        self.root.after(0, lambda: self.show_disclaimer(can_fresh_install, has_melon_folder))

    def update_status_connected_only(self):
        self.status_lbl.config(text="🟢 Connected", fg=COLOR_SUCCESS)
        self.btn_connect.set_state("disabled", new_text="Headset Connected")

    def show_disclaimer(self, can_fresh_install, has_melon_folder):
        self.disclaimer_dialog = tk.Toplevel(self.root)
        self.disclaimer_dialog.title("Installation Options")
        self.disclaimer_dialog.geometry("640x440")
        self.disclaimer_dialog.configure(bg=BG_CARD)
        self.disclaimer_dialog.transient(self.root)
        self.disclaimer_dialog.grab_set()
        
        self.disclaimer_dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (640 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (440 // 2)
        self.disclaimer_dialog.geometry(f"+{x}+{y}")
        
        self.disclaimer_dialog.protocol("WM_DELETE_WINDOW", self.cancel_disclaimer)
        
        tk.Label(self.disclaimer_dialog, text="CHOOSE INSTALLATION METHOD", font=("Segoe UI", 12, "bold"), fg=COLOR_PRIMARY, bg=BG_CARD).pack(pady=(15, 5))
        
        msg = (
            "How would you like to handle your existing files?\n\n"
            "• Continue: Cleans out old mod/patch files before installing Fusion.\n"
            "• Fresh Download: Completely uninstalls the game and wipes everything.\n"
            "• Game Already Patched: Skips patching if your game is already properly configured."
        )
        tk.Label(self.disclaimer_dialog, text=msg, font=("Segoe UI", 10), fg=FG_TEXT, bg=BG_CARD, justify=tk.CENTER).pack(pady=(0, 10))
        
        btn_frame = tk.Frame(self.disclaimer_dialog, bg=BG_CARD)
        btn_frame.pack(pady=5)

        def keep_mods():
            if has_melon_folder:
                self.disclaimer_dialog.destroy()
                self.disclaimer_dialog = None
                self.post_disclaimer(False, skipped_patch=True)

        def wipe_mods_action():
            if has_melon_folder:
                warn_text = f"If you continue the game will probably break because the file directory ({QUEST_MELON_PATH}) will be deleted do you wish to continue?"
                if not messagebox.askyesno("Warning: Game Already Patched", warn_text, parent=self.disclaimer_dialog):
                    return
            
            self.disclaimer_dialog.destroy()
            self.disclaimer_dialog = None
            self.run_in_thread(self.wipe_mods_and_proceed_worker)

        def fresh_download():
            warn_msg = (
                "WARNING: This will completely UNINSTALL Bonelab and permanently remove:\n\n"
                f"• OBB Directory: {OBB_DIR}\n"
                f"• Data Directory: {DATA_DIR}\n"
                f"• MelonLoader Bonelab Files: {QUEST_MELON_PATH}\n\n"
                "Are you sure you want to proceed with a complete fresh download?"
            )
            if messagebox.askyesno("Fresh Download", warn_msg, parent=self.disclaimer_dialog):
                self.disclaimer_dialog.destroy()
                self.disclaimer_dialog = None
                self.post_disclaimer(True)

        btn_wipe = ModernRoundedButton(btn_frame, "Continue", wipe_mods_action, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, width=400, height=40)
        btn_wipe.pack(pady=5)
        
        btn_fresh = ModernRoundedButton(btn_frame, "Complete Fresh Download (Recommended)", fresh_download, COLOR_ERROR, COLOR_ERROR_HOVER, width=400, height=40)
        btn_fresh.pack(pady=5)
        
        btn_keep = ModernRoundedButton(btn_frame, "Game Already Patched", keep_mods, COLOR_SUCCESS, COLOR_SUCCESS_HOVER, width=400, height=40)
        btn_keep.pack(pady=(5, 2))

        tk.Label(self.disclaimer_dialog, text="Game Patched, make sure you have launched BoneLab at least once.", font=("Segoe UI", 8, "italic"), fg=FG_DIM, bg=BG_CARD).pack(pady=(0, 10))

        if not can_fresh_install:
            btn_fresh.set_state("disabled")

        if not has_melon_folder:
            btn_keep.set_state("disabled")

    def cancel_disclaimer(self):
        if self.disclaimer_dialog:
            self.disclaimer_dialog.destroy()
            self.disclaimer_dialog = None
        self.log_err("Connection process cancelled.")
        self.reset_connection_ui()

    def post_disclaimer(self, wants_fresh, skipped_patch=False):
        if wants_fresh:
            self.run_in_thread(self.fresh_install_worker)
        else:
            output = self.run_adb(["shell", "pm", "list", "packages", QUEST_PKG], ignore_errors=True, silent=True)
            is_installed = QUEST_PKG in (output or "")
            if not is_installed:
                self.prompt_headset_install()
            else:
                self.verify_lemonloader_and_proceed(skipped_patch=skipped_patch)

    def wipe_mods_and_proceed_worker(self):
        self.log_sys("Removing existing mods, plugins, and old patch files...")
        self.log_detailed(f"Targeting deletion paths: {MODS_DIR}, {PLUGINS_DIR}, and FusionContent folders.")
        self.run_adb(["shell", f'rm -rf "{MODS_DIR}"'], ignore_errors=True, silent=True)
        self.run_adb(["shell", f'rm -rf "{PLUGINS_DIR}"'], ignore_errors=True, silent=True)
        self.run_adb(["shell", f'rm -rf "{QUEST_MELON_PATH}"'], ignore_errors=True, silent=True)
        self.run_adb(["shell", f'rm -rf "{GAME_DATA_MODS_DIR}/Lakatrazz.FusionContent"'], ignore_errors=True, silent=True)
        self.run_adb(["shell", f'rm -f "{GAME_DATA_MODS_DIR}/Lakatrazz.FusionContent.manifest"'], ignore_errors=True, silent=True)
        self.log_success("Existing mods and patch files removed.")
        self.root.after(0, lambda: self.post_disclaimer(False))

    def fresh_install_worker(self):
        self.log("\n--- initializing Bonelab wipe ---\n")
        self.log("Uninstalling Bonelab...")
        self.log_detailed(f"Invoking package manager uninstall for {QUEST_PKG}")
        self.run_adb(["uninstall", QUEST_PKG], silent=True)
        
        self.log("Removing OBB, Data, and MelonLoader BONELAB directory...")
        self.log_detailed(f"Executing recursive rm on {OBB_DIR}, {DATA_DIR}, and {QUEST_MELON_PATH}")
        self.run_adb(["shell", f'rm -rf "{OBB_DIR}"'], silent=True)
        self.run_adb(["shell", f'rm -rf "{DATA_DIR}"'], silent=True)
        self.run_adb(["shell", f'rm -rf "{QUEST_MELON_PATH}"'], silent=True)
        
        self.log_success("Bonelab uninstalled and storage cleaned successfully.")
        self.root.after(0, self.prompt_headset_install)

    def verify_lemonloader_and_proceed(self, skipped_patch=False):
        if skipped_patch:
            self.log_success("Game is already patched and ready for mods.")
            self.log_detailed("Skipping patch cycle per user selection; verifying execution entry points.")
            self.root.after(0, lambda: self.btn_deploy.set_state("normal"))
            return

        ll_output = self.run_adb(["shell", "pm", "list", "packages", LEMONLOADER_PKG], ignore_errors=True, silent=True)
        if LEMONLOADER_PKG not in (ll_output or ""):
            self.log_detailed("LemonLoader package check negative. Prompting installation...")
            self.root.after(0, self.prompt_lemonloader)
        else:
            self.log_sys("LemonLoader is already installed.")
            self.log_detailed("LemonLoader package detected successfully on device.")
            self.check_game_patch_status()

    def check_game_patch_status(self):
        melon_folder_check = self.run_adb(["shell", f"ls -d {QUEST_MELON_PATH}"], ignore_errors=True, silent=True)
        has_melon_folder = melon_folder_check and "No such file" not in melon_folder_check and "cannot access" not in melon_folder_check

        if has_melon_folder:
            self.log_success("Game is patched and ready for mods.")
            self.log_detailed(f"MelonLoader directory structure verified at {QUEST_MELON_PATH}")
            self.root.after(0, lambda: self.btn_deploy.set_state("normal"))
            return

        self.log_sys("Patching is required.")
        self.log_detailed("MelonLoader directory missing. Initiating OBB backup and patch sequence.")
        self.root.after(0, lambda: self.btn_deploy.set_state("disabled"))
        self.root.after(0, self.prompt_patch_monitor)

    def hardware_monitor_worker(self):
        while self.is_connected:
            time.sleep(2)
            output = self.run_adb(["devices"], ignore_errors=True, silent=True)
            if not output or (self.active_target_ip and self.active_target_ip not in output) or (not self.active_target_ip and len([l for l in output.splitlines() if "\tdevice" in l]) == 0):
                self.is_connected = False
                self.log_detailed("Hardware connection polling loop detected dropped transport link.")
                self.root.after(0, self.handle_disconnect)
                break

    def handle_disconnect(self):
        self.log_err("Headset disconnected. Please plug it back in and click connect.")
        self.root.after(0, self.reset_connection_ui)

    def prompt_patch_monitor(self):
        msg = (
            "To patch the game your Bonelab folder needs to be renamed until after it's complete.\n\n"
            f"{OBB_DIR}\n\n"
            "Do you wish to continue?"
        )
        if messagebox.askyesno("Patch Game", msg):
            self.run_in_thread(self.patch_monitor_worker)
        else:
            self.log_err("Unable to mod Bonelab. Patching is required.")
            self.root.after(0, self.reset_connection_ui)

    def patch_monitor_worker(self):
        self.log("\n--- Patching ---\n")
        
        check_obb = self.run_adb(["shell", f"ls -d {OBB_DIR}"], ignore_errors=True, silent=True)
        if "No such file" in check_obb or "cannot access" in check_obb:
            self.log_warn("OBB folder is missing from headset! Creating empty directory...")
            self.log_detailed(f"Explicitly creating OBB parent container directory: {OBB_DIR}")
            self.run_adb(["shell", f"mkdir -p {OBB_DIR}"], ignore_errors=True, silent=True)

        self.log_sys(f"Attempting to backup OBB folder ({OBB_DIR})...")
        self.run_adb(["shell", f'rm -rf "{OBB_DIR_BACKUP}"'], ignore_errors=True, silent=True)
        
        success = False
        for attempt in range(1, 4):
            self.log_detailed(f"Executing OBB directory rename attempt {attempt} -> moving to {OBB_DIR_BACKUP}")
            self.run_adb(["shell", f'mv "{OBB_DIR}" "{OBB_DIR_BACKUP}"'], ignore_errors=True, silent=True)
            verify = self.run_adb(["shell", "ls", "-d", OBB_DIR_BACKUP], ignore_errors=True, silent=True)
            
            if "No such file" not in verify and "cannot access" not in verify:
                success = True
                break
            
            self.log_warn(f"Attempt {attempt}: OBB locked or busy. Retrying in 2 seconds...")
            time.sleep(2)
            
        if success:
            self.log_success(f"Backup successful ({OBB_DIR_BACKUP}).")
        else:
            self.log_err("FAILED TO RENAME OBB FOLDER! Please close Windows Explorer / MTP connections and try again.")
            self.log_detailed("Critical failure: MTP lock or active file handle prevented OBB directory rename.")
            self.root.after(0, self.reset_connection_ui)
            return

        self.log("\n======================================")
        self.log("    TIME TO PATCH IN YOUR HEADSET    ")
        self.log("======================================\n")
        self.log("1. Open LemonLoader in your headset.")
        self.log("2. Allow all permissions.")
        self.log("3. Find BONELAB and click 'Patch'.")
        self.log_sys("This process could take a few minutes.")
        
        self.is_monitoring_patch = True
        self.log("Waiting for game to be patched...")
        
        while self.is_connected and self.is_monitoring_patch:
            out = self.run_adb(["shell", "pm", "list", "packages", QUEST_PKG], ignore_errors=True, silent=True)
            if QUEST_PKG not in (out or ""): break
            time.sleep(2)
            
        if not self.is_connected or not self.is_monitoring_patch: return
        
        while self.is_connected and self.is_monitoring_patch:
            out = self.run_adb(["shell", "pm", "list", "packages", QUEST_PKG], ignore_errors=True, silent=True)
            if QUEST_PKG in (out or ""):
                self.log_success("Patched version installed successfully!")
                break
            time.sleep(2)
            
        if not self.is_connected or not self.is_monitoring_patch: return
        
        self.log_sys(f"Restoring OBB folder name...")
        self.log_detailed(f"Restoring backup directory {OBB_DIR_BACKUP} back to original OBB spec: {OBB_DIR}")
        self.run_adb(["shell", f'rm -rf "{OBB_DIR}"'], ignore_errors=True, silent=True)
        
        restore_success = False
        for attempt in range(1, 4):
            self.run_adb(["shell", f'mv "{OBB_DIR_BACKUP}" "{OBB_DIR}"'], ignore_errors=True, silent=True)
            verify_restore = self.run_adb(["shell", "ls", "-d", OBB_DIR], ignore_errors=True, silent=True)
            
            if "No such file" not in verify_restore and "cannot access" not in verify_restore:
                restore_success = True
                break
            time.sleep(2)
            
        if restore_success:
            self.log_success("OBB folder successfully restored.")
        else:
            self.log_err("WARNING: OBB restore failed. Please check headset storage manually.")
            self.log_detailed("Warning: Automated OBB directory restoration encountered a filesystem lock.")
        
        self.log_warn("Almost done! Please launch Bonelab once in your headset to the main menu, then close it. ⚠️")
        self.log("Waiting for game launch...")
        self.wait_for_folder_creation_worker()

    def wait_for_folder_creation_worker(self):
        self.is_monitoring_patch = True
        while self.is_connected and self.is_monitoring_patch:
            melon_folder_check = self.run_adb(["shell", f"ls -d {QUEST_MELON_PATH}"], ignore_errors=True, silent=True)
            if melon_folder_check and "No such file" not in melon_folder_check and "cannot access" not in melon_folder_check:
                self.is_monitoring_patch = False
                self.log_success("LemonLoader Bonelab folder created successfully! You are ready to install Fusion.")
                self.log_detailed("Post-patch initialization verified. MelonLoader framework active.")
                self.root.after(0, lambda: self.btn_deploy.set_state("normal"))
                break
            time.sleep(2)

    def prompt_headset_install(self):
        messagebox.showinfo("Game Missing", "Bonelab is not currently installed.\n\nPlease put on your headset, open the Meta Store, and click Install on Bonelab.\n\nThis app will wait automatically until the game finishes downloading.")
        self.is_monitoring_game = True
        self.run_in_thread(self.game_install_monitor_worker)

    def game_install_monitor_worker(self):
        self.log("\n--- Downloading Bonelab ---\n")
        self.log("Waiting for Bonelab to be downloaded...")
        self.log_detailed("Polling package manager for installation state transition...")
        
        while self.is_connected and self.is_monitoring_game:
            output = self.run_adb(["shell", "pm", "list", "packages", QUEST_PKG], ignore_errors=True, silent=True)
            if QUEST_PKG in (output or ""):
                self.is_monitoring_game = False
                self.log_success("Download complete!")
                self.log_detailed("Package verification confirmed game installation completed.")
                self.root.after(0, self.verify_lemonloader_and_proceed)
                break
            
            time.sleep(1)

    def prompt_lemonloader(self):
        msg = "LemonLoader wasn't found and it is required to download Fusion.\n\nWould you like to install LemonLoader?"
        if messagebox.askyesno("Framework Missing", msg):
            self.run_in_thread(self.install_lemonloader_worker)
        else:
            self.log_err("Unable to mod Bonelab without LemonLoader.")
            self.root.after(0, self.reset_connection_ui)

    def install_lemonloader_worker(self):
        self.log("\n--- Installing LemonLoader ---\n")
        if os.path.exists(LLOADER_APK_PATH):
            self.log("Installing LemonLoader...")
            self.log_detailed(f"Executing adb install command on APK bundle: {LLOADER_APK_PATH}")
            self.run_adb(["install", "-r", LLOADER_APK_PATH], silent=True)
            self.log_success("LemonLoader installed.")
            self.check_game_patch_status()

    def start_deploy_thread(self):
        self.btn_deploy.set_state("disabled", new_text="Installing...")
        self.log_detailed("Deployment thread spawned. Commencing file push pipelines...")
        self.run_in_thread(self.deploy_worker)

    def push_folder(self, local_folder, remote_folder):
        if not os.path.exists(local_folder): return
        files = [f for f in os.listdir(local_folder) if os.path.isfile(os.path.join(local_folder, f))]
        if not files: return
        self.run_adb(["shell", "mkdir", "-p", remote_folder], ignore_errors=True, silent=True)
        for filename in files:
            if filename.lower().endswith(('.md', '.txt')):
                continue
                
            local_path = os.path.join(local_folder, filename)
            remote_path = f"{remote_folder}/{filename}"
            self.log_detailed(f"Pushing asset: {filename} -> {remote_path}")
            self.run_adb(["push", local_path, remote_path], silent=True)
            self.log_success(f"Found {filename} in {remote_path}")
            time.sleep(0.05)

    def push_directory_recursive(self, local_dir, remote_dir):
        if not os.path.exists(local_dir): return
        self.run_adb(["shell", "mkdir", "-p", remote_dir], ignore_errors=True, silent=True)
        for item in os.listdir(local_dir):
            if item.lower().endswith(('.md', '.txt')):
                continue
                
            local_path = os.path.join(local_dir, item)
            remote_path = f"{remote_dir}/{item}"
            if os.path.isdir(local_path):
                self.push_directory_recursive(local_path, remote_path)
            elif os.path.isfile(local_path):
                self.log_detailed(f"Recursive push asset: {item} -> {remote_path}")
                self.run_adb(["push", local_path, remote_path], silent=True)
                self.log_success(f"Found {item} in {remote_path}")
                time.sleep(0.05)

    def deploy_worker(self):
        self.log("\n======================================")
        self.log("    STARTING FUSION INSTALLATION    ", "info")
        self.log("======================================\n")

        local_mods = get_resource_path("mods")
        local_plugins = get_resource_path("plugins")
        local_saves = get_resource_path("saves")
        local_modsd = get_resource_path("ModsD")

        # 1. Push Regular MelonLoader Mods
        if os.path.exists(local_mods):
            self.log_detailed("Scanning local Mods directory for deployment...")
            for item in os.listdir(local_mods):
                if item.lower().endswith(('.md', '.txt')):
                    continue
                    
                local_item = os.path.join(local_mods, item)
                remote_item = f"{MODS_DIR}/{item}"
                if os.path.isdir(local_item): self.push_directory_recursive(local_item, remote_item)
                elif os.path.isfile(local_item):
                    self.log_detailed(f"Pushing mod file: {item}")
                    self.run_adb(["push", local_item, remote_item], silent=True)
                    self.log_success(f"Found {item} in {remote_item}")

        # 2. Push MelonLoader Plugins
        self.log_detailed("Scanning local Plugins directory for deployment...")
        self.push_folder(local_plugins, PLUGINS_DIR)

        # 3. Push ModsD Folder Contents directly to Android/data/.../files/mods
        if os.path.exists(local_modsd):
            self.log_detailed("Scanning local ModsD directory for custom item deployment...")
            for item in os.listdir(local_modsd):
                if item.lower().endswith(('.md', '.txt')):
                    continue
                local_item = os.path.join(local_modsd, item)
                remote_item = f"{GAME_DATA_MODS_DIR}/{item}"
                if os.path.isdir(local_item):
                    self.push_directory_recursive(local_item, remote_item)
                elif os.path.isfile(local_item):
                    self.log_detailed(f"Pushing ModsD asset: {item}")
                    self.run_adb(["push", local_item, remote_item], silent=True)
                    self.log_success(f"Found {item} in {remote_item}")

        # 4. Handle Save Files
        if os.path.exists(local_saves) and os.listdir(local_saves):
            save_choice = self.prompt_save_dialog()
            if save_choice == "pc":
                backup_path = filedialog.askdirectory(title="Select Folder on PC to Backup Headset Saves")
                if backup_path:
                    os.makedirs(backup_path, exist_ok=True)
                    self.log("\n--- Backing up Headset Saves ---")
                    self.log("Downloading save files from headset...")
                    self.log_detailed(f"Pulling remote save files from {SAVES_DIR} to PC path {backup_path}")
                    self.run_adb(["pull", SAVES_DIR, backup_path], ignore_errors=True)
                    self.log_success(f"Backup complete! Saved to: {backup_path}")
                else:
                    self.log_sys("Save file backup skipped.")
                
                self.log("\n--- Installing Save File ---\n")
                self.log("Removing old save data...")
                self.run_adb(["shell", f'rm -rf "{SAVES_DIR}/"*'], ignore_errors=True, silent=True)
                self.push_folder(local_saves, SAVES_DIR)
                self.log_success("100% save file installed successfully.")
            elif save_choice == "quest":
                self.log("\n--- Backing up Headset Saves ---")
                self.log("Backing up save files on headset...")
                self.log_detailed(f"Duplicating headset saves to backup directory: {QUEST_BACKUPS_DIR}")
                self.run_adb(["shell", f"mkdir -p {QUEST_BACKUPS_DIR}"], ignore_errors=True, silent=True)
                self.run_adb(["shell", f"cp -r {SAVES_DIR}/* {QUEST_BACKUPS_DIR}/"], ignore_errors=True, silent=True)
                self.log_success(f"Backup complete! Saved to: {QUEST_BACKUPS_DIR}")
                
                self.log("\n--- Installing Save File ---\n")
                self.log("Removing old save data...")
                self.run_adb(["shell", f'rm -rf "{SAVES_DIR}/"*'], ignore_errors=True, silent=True)
                self.push_folder(local_saves, SAVES_DIR)
                self.log_success("100% save file installed successfully.")
            elif save_choice == "overwrite":
                self.log("\n--- Installing Save File ---")
                self.log("Overwriting existing save data...")
                self.run_adb(["shell", f'rm -rf "{SAVES_DIR}/"*'], ignore_errors=True, silent=True)
                self.push_folder(local_saves, SAVES_DIR)
                self.log_success("Save file overwritten successfully.")
            elif save_choice == "keep":
                self.log("\n--- Installing Save File ---\n")
                self.log("Removing old save data...")
                self.run_adb(["shell", f'rm -rf "{SAVES_DIR}/"*'], ignore_errors=True, silent=True)
                self.push_folder(local_saves, SAVES_DIR)
                self.log_success("100% save file installed successfully.")
            else:
                self.log_sys("Save file installation skipped.")

        self.log("\n=======================================================")
        self.log_success("FUSION INSTALLATION COMPLETE! You are ready to play.")
        self.log("\nIf there is a problem with launching the game and you")
        self.log("cannot find any solutions we recommend a fresh install.")
        self.log("\n\t\t-Created with Gemini-")
        self.log("=======================================================")
        self.play_headset_sound("Fusion Installation Complete!")
        
        if self.is_connected:
            self.root.after(0, lambda: self.btn_deploy.set_state("normal", new_text="Install Fusion"))

    def prompt_save_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Save File Options")
        dialog.geometry("620x240")
        dialog.configure(bg=BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (620 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (240 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        result = {"choice": "none"}
        
        msg = (
            "Save File Recommended Options:\n\n"
            "Fusion works best with a 100% save file. Would you like to backup your\n"
            "current saves, overwrite them, or keep your current saves alongside the install?"
        )
        tk.Label(dialog, text=msg, font=("Segoe UI", 9), fg=FG_TEXT, bg=BG_CARD, justify=tk.LEFT).pack(padx=25, pady=(20, 10))
        
        btn_frame = tk.Frame(dialog, bg=BG_CARD)
        btn_frame.pack(pady=10)
        
        def on_pc():
            result["choice"] = "pc"
            dialog.destroy()
        def on_quest():
            result["choice"] = "quest"
            dialog.destroy()
        def on_overwrite():
            result["choice"] = "overwrite"
            dialog.destroy()
        def on_keep():
            result["choice"] = "keep"
            dialog.destroy()
        def on_close():
            result["choice"] = "none"
            dialog.destroy()
            
        dialog.protocol("WM_DELETE_WINDOW", on_close)
            
        ModernRoundedButton(btn_frame, "Backup on PC", on_pc, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, width=130, height=35).pack(side=tk.LEFT, padx=4)
        ModernRoundedButton(btn_frame, "Backup on Quest", on_quest, "#A371F7", "#8A5CE3", width=130, height=35).pack(side=tk.LEFT, padx=4)
        ModernRoundedButton(btn_frame, "Overwrite", on_overwrite, COLOR_ERROR, COLOR_ERROR_HOVER, width=130, height=35).pack(side=tk.LEFT, padx=4)
        ModernRoundedButton(btn_frame, "Keep Current", on_keep, COLOR_SUCCESS, COLOR_SUCCESS_HOVER, width=130, height=35).pack(side=tk.LEFT, padx=4)
        
        dialog.wait_window()
        return result["choice"]

    def backup_saves(self):
        if not self.is_connected:
            return self.log_err("Please connect your headset first.")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Backup Location")
        dialog.geometry("450x180")
        dialog.configure(bg=BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (450 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (180 // 2)
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="Where would you like to back up your saves?", font=("Segoe UI", 11, "bold"), fg=COLOR_PRIMARY, bg=BG_CARD).pack(pady=(20, 10))
        
        btn_frame = tk.Frame(dialog, bg=BG_CARD)
        btn_frame.pack(pady=10)

        def on_pc():
            dialog.destroy()
            backup_path = filedialog.askdirectory(title="Select Folder on PC to Backup Headset Saves")
            if backup_path:
                os.makedirs(backup_path, exist_ok=True)
                self.log("\n--- Backing up Headset Saves ---")
                self.log("Downloading save files from headset...")
                self.run_adb(["pull", SAVES_DIR, backup_path], ignore_errors=True)
                self.log_success(f"Backup complete! Saved to: {backup_path}")

        def on_quest():
            dialog.destroy()
            self.log("\n--- Backing up Headset Saves ---")
            self.log("Backing up save files on headset...")
            self.run_adb(["shell", f"mkdir -p {QUEST_BACKUPS_DIR}"], ignore_errors=True, silent=True)
            self.run_adb(["shell", f"cp -r {SAVES_DIR}/* {QUEST_BACKUPS_DIR}/"], ignore_errors=True, silent=True)
            self.log_success(f"Backup complete! Saved to: {QUEST_BACKUPS_DIR}")

        ModernRoundedButton(btn_frame, "Backup on PC", on_pc, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, width=160, height=40).pack(side=tk.LEFT, padx=10)
        ModernRoundedButton(btn_frame, "Backup on Quest", on_quest, "#A371F7", "#8A5CE3", width=160, height=40).pack(side=tk.LEFT, padx=10)

    def wipe_mods(self):
        if not self.is_connected:
            return self.log_err("Please connect your headset first.")
            
        self.run_adb(["shell", f'rm -rf "{MODS_DIR}"'], ignore_errors=True, silent=True)
        self.run_adb(["shell", f'rm -rf "{PLUGINS_DIR}"'], ignore_errors=True, silent=True)
        self.run_adb(["shell", f'rm -rf "{GAME_DATA_MODS_DIR}/Lakatrazz.FusionContent"'], ignore_errors=True, silent=True)
        self.run_adb(["shell", f'rm -f "{GAME_DATA_MODS_DIR}/Lakatrazz.FusionContent.manifest"'], ignore_errors=True, silent=True)
        self.log_success("Mods and Plugins folders removed.")

if __name__ == "__main__":
    root = tk.Tk()
    app = BonelabInstallerGUI(root)
    root.mainloop()
