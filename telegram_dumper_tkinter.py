import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import asyncio
import threading
import queue
import json
import os
import platform
import subprocess
import time
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import DocumentAttributeSticker, DocumentAttributeFilename
from telethon.errors.rpcerrorlist import SessionPasswordNeededError

CONFIG_FILE = "config.json"

class TelegramExporterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Telegram Chat Exporter")
        self.geometry("450x380")
        self.overrideredirect(True)

        self.client = None
        self.session_name = "my_session"
        self.input_queue = queue.Queue()
        self.input_response = None
        
        self.loop = asyncio.new_event_loop()
        self.network_thread = threading.Thread(target=self._start_network_loop, daemon=True)
        self.network_thread.start()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel", padding=5, font=("Helvetica", 10))
        style.configure("TButton", padding=5, font=("Helvetica", 10, "bold"))
        style.configure("TEntry", padding=5, font=("Helvetica", 10))
        style.configure("TCombobox", padding=5, font=("Helvetica", 10))

        self.top_bar_frame = ttk.Frame(self)
        self.top_bar_frame.pack(side="top", fill="x", padx=10, pady=(10, 0))
        
        ttk.Button(self.top_bar_frame, text="Quit", command=self._on_closing).pack(side="right")
        self.logout_button = ttk.Button(self.top_bar_frame, text="Logout", command=self.logout)
        
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        self.login_frame = self._create_login_frame()
        self.exporter_frame = self._create_exporter_frame()
        self.loading_frame = self._create_loading_frame()

        self.show_frame(self.loading_frame)
        self.check_initial_login()

    def _start_network_loop(self):
        """Runs the asyncio event loop in the background thread."""
        print("[LOG] Network thread started.")
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        print("[LOG] Network thread finished.")

    def _on_closing(self):
        """Shut down the event loop and client when closing the window."""
        print("[LOG] Closing application...")

        async def shutdown_sequence():
            if self.client and self.client.is_connected():
                print("[LOG] Disconnecting client...")
                await self.client.disconnect()
            print("[LOG] Stopping network loop...")
            self.loop.stop()

        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(shutdown_sequence(), self.loop)
            self.after(200, self.destroy)
        else:
            self.destroy()

    def show_frame(self, frame_to_show):
        """Hides all frames and shows the requested one. Also manages button visibility."""
        for frame in [self.login_frame, self.exporter_frame, self.loading_frame]:
            frame.grid_remove()
        
        if frame_to_show == self.exporter_frame:
            self.logout_button.pack(side="right", padx=5)
        else:
            self.logout_button.pack_forget()

        frame_to_show.grid(row=0, column=0, sticky="nsew")

    def _create_loading_frame(self):
        frame = ttk.Frame(self.container)
        ttk.Label(frame, text="Loading...", font=("Helvetica", 14)).pack(pady=20)
        self.loading_progress = ttk.Progressbar(frame, mode='indeterminate')
        self.loading_progress.pack(pady=10, padx=20, fill="x")
        self.loading_progress.start()
        return frame

    def _create_login_frame(self):
        frame = ttk.Frame(self.container)
        ttk.Label(frame, text="Telegram Login", font=("Helvetica", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        
        ttk.Label(frame, text="API ID:").grid(row=1, column=0, sticky="w")
        self.api_id_entry = ttk.Entry(frame, width=40)
        self.api_id_entry.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="API Hash:").grid(row=2, column=0, sticky="w")
        self.api_hash_entry = ttk.Entry(frame, width=40)
        self.api_hash_entry.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Phone Number:").grid(row=3, column=0, sticky="w")
        self.phone_entry = ttk.Entry(frame, width=40)
        self.phone_entry.grid(row=3, column=1, pady=5)

        ttk.Button(frame, text="Login", command=self.start_login).grid(row=4, column=0, columnspan=2, pady=20)
        self.login_status_label = ttk.Label(frame, text="")
        self.login_status_label.grid(row=5, column=0, columnspan=2)
        return frame

    def _create_exporter_frame(self):
        frame = ttk.Frame(self.container)
        ttk.Label(frame, text="Export Settings", font=("Helvetica", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        
        ttk.Label(frame, text="Target Username:").grid(row=1, column=0, sticky="w")
        self.target_user_entry = ttk.Entry(frame, width=30)
        self.target_user_entry.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Output File:").grid(row=2, column=0, sticky="w")
        self.output_file_entry = ttk.Entry(frame, width=30)
        self.output_file_entry.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Format:").grid(row=3, column=0, sticky="w")
        self.format_combo = ttk.Combobox(frame, values=["txt", "json"], state="readonly")
        self.format_combo.grid(row=3, column=1, pady=5)
        self.format_combo.set("txt")

        ttk.Button(frame, text="Export Chat", command=self.start_export).grid(row=4, column=0, columnspan=2, pady=20)
        self.export_status_label = ttk.Label(frame, text="Ready to export.")
        self.export_status_label.grid(row=5, column=0, columnspan=2)
        return frame

    def update_status(self, label, text):
        """Thread-safe way to update a label's text."""
        self.after(0, lambda: label.config(text=text))

    def check_initial_login(self):
        """Checks for an existing session file on startup."""
        print("[LOG] Checking for existing session file...")
        asyncio.run_coroutine_threadsafe(self._async_check_login(), self.loop)

    async def _async_check_login(self):
        config = self._load_config()
        self.api_id_entry.insert(0, config.get("api_id", ""))
        self.api_hash_entry.insert(0, config.get("api_hash", ""))
        
        if not os.path.exists(f"{self.session_name}.session") or not config:
            print("[LOG] No session or config found. Showing login page.")
            self.update_status(self.login_status_label, "No active session found. Please log in.")
            self.show_frame(self.login_frame)
            return

        print("[LOG] Session and config found. Attempting to connect...")
        try:
            self.client = TelegramClient(self.session_name, int(config['api_id']), config['api_hash'], loop=self.loop)
            await self.client.connect()
            if await self.client.is_user_authorized():
                print("[LOG] Connection successful. User is authorized.")
                self.show_frame(self.exporter_frame)
            else:
                print("[LOG] Session is invalid or expired.")
                self.show_frame(self.login_frame)
        except Exception as e:
            print(f"[ERROR] Failed to check session: {e}")
            self.update_status(self.login_status_label, f"Session invalid. Please log in again.")
            self.show_frame(self.login_frame)

    def start_login(self):
        api_id = self.api_id_entry.get()
        api_hash = self.api_hash_entry.get()
        phone = self.phone_entry.get()
        if not all([api_id, api_hash, phone]):
            messagebox.showerror("Error", "All fields are required.")
            return
        asyncio.run_coroutine_threadsafe(self._async_login(api_id, api_hash, phone), self.loop)

    def _prompt_for_input(self, title, prompt, is_password=False):
        """Thread-safe way to ask for user input from a background thread."""
        self.input_queue.put((title, prompt, is_password))
        def show_dialog():
            try:
                title, prompt, is_password = self.input_queue.get_nowait()
                show_char = '' if not is_password else '*'
                self.input_response = simpledialog.askstring(title, prompt, parent=self, show=show_char)
            except queue.Empty: pass
        self.after(0, show_dialog)
        while self.input_response is None: time.sleep(0.1)
        response, self.input_response = self.input_response, None
        return response

    async def _async_login(self, api_id, api_hash, phone):
        print("[LOG] Starting login logic in network thread.")
        try:
            self.client = TelegramClient(self.session_name, int(api_id), api_hash, loop=self.loop)
            await self.client.connect()
            self.update_status(self.login_status_label, "Sending login code...")
            sent_code = await self.client.send_code_request(phone)
            
            code = self._prompt_for_input("Login Code", "Enter the code you received in Telegram:")
            if not code:
                self.update_status(self.login_status_label, "Login cancelled.")
                await self.client.disconnect()
                return

            try:
                await self.client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
            except SessionPasswordNeededError:
                self.update_status(self.login_status_label, "Password required.")
                password = self._prompt_for_input("Password", "Enter your 2FA password:", is_password=True)
                if not password:
                    self.update_status(self.login_status_label, "Login cancelled.")
                    await self.client.disconnect()
                    return
                await self.client.sign_in(password=password)
            
            self._save_config(api_id, api_hash)
            self.update_status(self.login_status_label, "Login successful!")
            print("[LOG] Login with password successful!")
            self.show_frame(self.exporter_frame)

        except Exception as e:
            self.update_status(self.login_status_label, f"Error: {str(e)}")
            print(f"[ERROR] An exception occurred during login: {e}")
            if self.client and self.client.is_connected():
                await self.client.disconnect()

    def start_export(self):
        target_user = self.target_user_entry.get()
        output_file = self.output_file_entry.get()
        format_choice = self.format_combo.get()
        if not all([target_user, output_file]):
            messagebox.showerror("Error", "Target username and output file are required.")
            return
        asyncio.run_coroutine_threadsafe(self._async_export(target_user, output_file, format_choice), self.loop)
    
    async def _async_export(self, target_username, base_filename, format_choice):
        final_filename = base_filename
        if not final_filename.lower().endswith(('.txt', '.json')):
            final_filename = f"{base_filename}.{format_choice}"

        print(f"[LOG] Starting export for '{target_username}' to '{final_filename}'.")
        try:
            self.update_status(self.export_status_label, f"Finding user '{target_username}'...")
            target_entity = await self.client.get_entity(target_username)
            print(f"[LOG] Found entity: {target_entity.first_name}")
            
            all_messages_data = []
            total_fetched = 0
            self.update_status(self.export_status_label, "Starting message export...")

            async for message in self.client.iter_messages(target_entity):
                content = get_message_content(message)
                if not content: continue
                
                all_messages_data.append({
                    "timestamp": message.date.strftime('%Y-%m-%d %H:%M:%S'),
                    "sender": "You" if message.out else target_entity.first_name or target_username,
                    "content": content
                })
                total_fetched += 1
                if total_fetched % 100 == 0:
                    self.update_status(self.export_status_label, f"Fetched {total_fetched} messages so far...")

            all_messages_data.reverse()

            print(f"[LOG] Total messages fetched: {len(all_messages_data)}. Writing to file.")
            with open(final_filename, 'w', encoding='utf-8') as f:
                if format_choice == 'json':
                    json.dump(all_messages_data, f, ensure_ascii=False, indent=4)
                else: 
                    for msg in all_messages_data:
                        f.write(f"[{msg['timestamp']}] {msg['sender']}: {msg['content']}\n")
            
            self.update_status(self.export_status_label, f"Success! Exported {len(all_messages_data)} messages.")
            print("[LOG] Export complete. Opening file.")
            self.open_file(final_filename)

        except Exception as e:
            self.update_status(self.export_status_label, f"Error: {e}")
            print(f"[ERROR] An exception occurred during export: {e}")
        
    def open_file(self, filepath):
        """Opens a file with the default system application."""
        try:
            if platform.system() == 'Darwin':       # macOS
                subprocess.call(('open', filepath))
            elif platform.system() == 'Windows':    # Windows
                os.startfile(os.path.realpath(filepath))
            else:                                   # Linux
                subprocess.call(('xdg-open', filepath))
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not open file automatically: {e}")

    def _save_config(self, api_id, api_hash):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'api_id': api_id, 'api_hash': api_hash}, f)
        print(f"[LOG] Saved credentials to {CONFIG_FILE}")

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                print(f"[LOG] Loaded credentials from {CONFIG_FILE}")
                return json.load(f)
        return {}


    def logout(self):
        """Asks for confirmation and logs the user out."""
        confirmed = messagebox.askyesno(
            "Confirm Logout",
            "Are you sure you want to logout? After pressing yes, all your login information will be permanently deleted from your PC."
        )
        if confirmed:
            asyncio.run_coroutine_threadsafe(self._async_logout(), self.loop)

    async def _async_logout(self):
        """Handles the client disconnection and file deletion."""
        print("[LOG] Logging out...")
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        self.client = None

        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            print(f"[LOG] Deleted {CONFIG_FILE}")
        if os.path.exists(self.session_name + ".session"):
            os.remove(self.session_name + ".session")
            print(f"[LOG] Deleted {self.session_name}.session")

        self.after(0, self._show_login_after_logout)

    def _show_login_after_logout(self):
        """Clears fields and switches to the login frame on the main thread."""
        self.api_id_entry.delete(0, tk.END)
        self.api_hash_entry.delete(0, tk.END)
        self.phone_entry.delete(0, tk.END)
        self.update_status(self.login_status_label, "Successfully logged out.")
        self.show_frame(self.login_frame)


def get_message_content(message):
    """Analyzes a message object and returns its content as a string."""
    content_parts = []
    media_tag = None
    if message.photo: media_tag = "[Photo]"
    elif message.video: media_tag = "[Video]"
    elif message.voice: media_tag = "[Voice Message]"
    elif message.sticker:
        emoji = next((attr.alt for attr in message.sticker.attributes if isinstance(attr, DocumentAttributeSticker)), "")
        media_tag = f"[Sticker {emoji}]".strip()
    elif message.document:
        filename = next((attr.file_name for attr in message.document.attributes if isinstance(attr, DocumentAttributeFilename)), "file")
        media_tag = f"[File: {filename}]"
    if media_tag: content_parts.append(media_tag)
    if message.raw_text: content_parts.append(message.raw_text)
    return " ".join(content_parts) if content_parts else None

if __name__ == "__main__":
    app = TelegramExporterApp()
    app.mainloop()

