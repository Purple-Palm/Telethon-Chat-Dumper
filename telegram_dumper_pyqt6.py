import sys
import asyncio
import json
import os
import platform
import subprocess
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QFrame, QStackedWidget,
    QMessageBox, QInputDialog, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt
from telethon.sync import TelegramClient
from telethon.tl.types import DocumentAttributeSticker, DocumentAttributeFilename
from telethon.errors.rpcerrorlist import SessionPasswordNeededError

CONFIG_FILE = "config.json"

class AsyncioWorker(QObject):
    """
    Runs the asyncio event loop in a background thread to handle
    all network operations without freezing the GUI.
    """
    finished = pyqtSignal()
    task_started = pyqtSignal(str)
    task_finished = pyqtSignal(str)
    task_error = pyqtSignal(str)
    prompt_for_input = pyqtSignal(str, str, bool)
    show_exporter_frame = pyqtSignal()
    show_login_frame = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.client = None
        self.session_name = "my_session"
        self.input_response = None

    def run(self):
        """Starts the asyncio event loop."""
        print("[LOG] Network thread started.")
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        print("[LOG] Network thread finished.")

    def _submit_async_task(self, coro):
        """Submits coroutine to the running event loop"""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self):
        """Stops the event loop and disconnects the client."""
        async def shutdown_sequence():
            if self.client and self.client.is_connected():
                print("[LOG] Disconnecting client...")
                await self.client.disconnect()
            print("[LOG] Stopping network loop...")
            self.loop.stop()

        if self.loop.is_running():
            self._submit_async_task(shutdown_sequence())
        self.finished.emit()

    def set_input_response(self, response):
        """Receives input from the main thread dialog."""
        self.input_response = response

    def _wait_for_input(self, title, prompt, is_password):
        """Emits a signal to show a dialog and waits for the response."""
        self.input_response = None 
        self.prompt_for_input.emit(title, prompt, is_password)
        while self.input_response is None:
            time.sleep(0.1)
        return self.input_response

    async def _async_check_login(self, config):
        if not os.path.exists(f"{self.session_name}.session") or not config:
            print("[LOG] No session or config found. Showing login page.")
            self.show_login_frame.emit("No active session. Please log in.")
            return

        print("[LOG] Session and config found. Attempting to connect...")
        try:
            self.client = TelegramClient(self.session_name, int(config['api_id']), config['api_hash'], loop=self.loop)
            await self.client.connect()
            if await self.client.is_user_authorized():
                print("[LOG] Connection successful. User is authorized.")
                self.show_exporter_frame.emit()
            else:
                print("[LOG] Session is invalid or expired.")
                self.show_login_frame.emit("Session invalid. Please log in again.")
        except Exception as e:
            print(f"[ERROR] Failed to check session: {e}")
            self.show_login_frame.emit(f"Session invalid. Please log in again.")

    async def _async_login(self, api_id, api_hash, phone):
        print("[LOG] Starting login logic in network thread.")
        self.task_started.emit("Logging in...")
        try:
            self.client = TelegramClient(self.session_name, int(api_id), api_hash, loop=self.loop)
            await self.client.connect()
            self.task_started.emit("Sending login code...")
            sent_code = await self.client.send_code_request(phone)

            code = self._wait_for_input("Login Code", "Enter the code you received in Telegram:", False)
            if not code:
                self.task_error.emit("Login cancelled.")
                await self.client.disconnect()
                return

            try:
                await self.client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
            except SessionPasswordNeededError:
                self.task_started.emit("Password required.")
                password = self._wait_for_input("Password", "Enter your 2FA password:", True)
                if not password:
                    self.task_error.emit("Login cancelled.")
                    await self.client.disconnect()
                    return
                await self.client.sign_in(password=password)

            self.task_finished.emit("Login successful!")
            print("[LOG] Login with password successful!")
            self.show_exporter_frame.emit()

        except Exception as e:
            self.task_error.emit(f"Error: {str(e)}")
            print(f"[ERROR] An exception occurred during login: {e}")
            if self.client and self.client.is_connected():
                await self.client.disconnect()

    async def _async_export(self, target_username, base_filename, format_choice):
        final_filename = base_filename
        if not final_filename.lower().endswith(('.txt', '.json')):
            final_filename = f"{base_filename}.{format_choice}"

        print(f"[LOG] Starting export for '{target_username}' to '{final_filename}'.")
        try:
            self.task_started.emit(f"Finding user '{target_username}'...")
            target_entity = await self.client.get_entity(target_username)
            print(f"[LOG] Found entity: {target_entity.first_name}")

            all_messages_data = []
            total_fetched = 0
            self.task_started.emit("Starting message export...")

            async for message in self.client.iter_messages(target_entity):
                content = self.get_message_content(message)
                if not content: continue

                all_messages_data.append({
                    "timestamp": message.date.strftime('%Y-%m-%d %H:%M:%S'),
                    "sender": "You" if message.out else target_entity.first_name or target_username,
                    "content": content
                })
                total_fetched += 1
                if total_fetched % 100 == 0:
                    self.task_started.emit(f"Fetched {total_fetched} messages so far...")

            all_messages_data.reverse()

            with open(final_filename, 'w', encoding='utf-8') as f:
                if format_choice == 'json':
                    json.dump(all_messages_data, f, ensure_ascii=False, indent=4)
                else:
                    for msg in all_messages_data:
                        f.write(f"[{msg['timestamp']}] {msg['sender']}: {msg['content']}\n")

            self.task_finished.emit(f"Success! Exported {len(all_messages_data)} messages.")
            print("[LOG] Export complete.")
            open_file(final_filename)

        except Exception as e:
            self.task_error.emit(f"Error: {e}")
            print(f"[ERROR] An exception occurred during export: {e}")

    async def _async_logout(self):
        print("[LOG] Logging out...")
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        self.client = None

        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        if os.path.exists(self.session_name + ".session"):
            os.remove(self.session_name + ".session")

        self.show_login_frame.emit("Successfully logged out.")

    def get_message_content(self, message):
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


class TelegramExporterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram Chat Exporter")
        self.setGeometry(100, 100, 450, 400)

        self.setStyleSheet("""
            QWidget {
                font-size: 11pt;
                color: #e0e0e0;
                background-color: #2c3e50;
            }
            QMainWindow {
                background-color: #34495e;
            }
            QLabel {
                padding: 5px;
            }
            QLineEdit, QComboBox {
                padding: 8px;
                border: 1px solid #34495e;
                border-radius: 4px;
                background-color: #34495e;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton#logoutButton {
                background-color: #e74c3c;
            }
            QPushButton#logoutButton:hover {
                background-color: #c0392b;
            }
            QLabel#titleLabel {
                font-size: 16pt;
                font-weight: bold;
                padding-bottom: 10px;
            }
        """)


        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.setCentralWidget(self.main_widget)


        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)


        self.loading_page = self._create_loading_page()
        self.login_page = self._create_login_page()
        self.exporter_page = self._create_exporter_page()

        self.stacked_widget.addWidget(self.loading_page)
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.exporter_page)


        self.setup_worker_thread()

        self.check_initial_login()

    def setup_worker_thread(self):
        self.worker_thread = QThread()
        self.worker = AsyncioWorker()
        self.worker.moveToThread(self.worker_thread)


        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker.task_started.connect(self.update_status)
        self.worker.task_finished.connect(self.on_task_finished)
        self.worker.task_error.connect(self.on_task_error)
        self.worker.prompt_for_input.connect(self.prompt_user_for_input)

        self.worker.show_exporter_frame.connect(self.show_exporter_frame)
        self.worker.show_login_frame.connect(self.show_login_frame)

        self.worker_thread.start()

    def _create_loading_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("Loading..."))
        progress = QProgressBar()
        progress.setRange(0, 0)
        layout.addWidget(progress)
        return page

    def _create_login_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Telegram Login", objectName="titleLabel"), alignment=Qt.AlignmentFlag.AlignCenter)

        self.api_id_entry = QLineEdit()
        self.api_id_entry.setPlaceholderText("API ID")
        layout.addWidget(self.api_id_entry)

        self.api_hash_entry = QLineEdit()
        self.api_hash_entry.setPlaceholderText("API Hash")
        layout.addWidget(self.api_hash_entry)

        self.phone_entry = QLineEdit()
        self.phone_entry.setPlaceholderText("Phone Number (e.g. +1234567890)")
        layout.addWidget(self.phone_entry)

        login_button = QPushButton("Login")
        login_button.clicked.connect(self.start_login)
        layout.addWidget(login_button)

        self.login_status_label = QLabel("")
        self.login_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.login_status_label)
        layout.addStretch()
        return page

    def _create_exporter_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Export Settings", objectName="titleLabel"), alignment=Qt.AlignmentFlag.AlignCenter)
        logout_button = QPushButton("Logout")
        logout_button.setObjectName("logoutButton")
        logout_button.setFixedWidth(100)
        logout_button.clicked.connect(self.logout)
        title_layout.addWidget(logout_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(title_layout)

        self.target_user_entry = QLineEdit()
        self.target_user_entry.setPlaceholderText("Target Username or Phone")
        layout.addWidget(self.target_user_entry)

        self.output_file_entry = QLineEdit()
        self.output_file_entry.setPlaceholderText("Output file name (e.g., chat_history)")
        layout.addWidget(self.output_file_entry)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["txt", "json"])
        layout.addWidget(self.format_combo)

        export_button = QPushButton("Export Chat")
        export_button.clicked.connect(self.start_export)
        layout.addWidget(export_button)

        self.export_status_label = QLabel("Ready to export.")
        self.export_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.export_status_label)
        layout.addStretch()
        return page

    def check_initial_login(self):
        config = self._load_config()
        self.api_id_entry.setText(config.get("api_id", ""))
        self.api_hash_entry.setText(config.get("api_hash", ""))
        self.worker._submit_async_task(self.worker._async_check_login(config))

    def start_login(self):
        api_id = self.api_id_entry.text()
        api_hash = self.api_hash_entry.text()
        phone = self.phone_entry.text()
        if not all([api_id, api_hash, phone]):
            QMessageBox.critical(self, "Error", "All fields are required.")
            return
        self._save_config(api_id, api_hash)
        self.worker._submit_async_task(self.worker._async_login(api_id, api_hash, phone))

    def start_export(self):
        target_user = self.target_user_entry.text()
        output_file = self.output_file_entry.text()
        format_choice = self.format_combo.currentText()
        if not all([target_user, output_file]):
            QMessageBox.critical(self, "Error", "Target username and output file are required.")
            return
        self.worker._submit_async_task(self.worker._async_export(target_user, output_file, format_choice))

    def logout(self):
        reply = QMessageBox.question(self, "Confirm Logout",
                                     "Are you sure you want to logout? This will delete your session file.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.worker._submit_async_task(self.worker._async_logout())


    def update_status(self, text):
        current_page = self.stacked_widget.currentWidget()
        if current_page == self.login_page:
            self.login_status_label.setText(text)
        elif current_page == self.exporter_page:
            self.export_status_label.setText(text)

    def on_task_finished(self, text):
        self.update_status(text)
        QMessageBox.information(self, "Success", text)

    def on_task_error(self, text):
        self.update_status(text)
        QMessageBox.critical(self, "Error", text)

    def prompt_user_for_input(self, title, prompt, is_password):
        """Creates an input dialog in the main thread."""
        if is_password:
            text, ok = QInputDialog.getText(self, title, prompt, QLineEdit.EchoMode.Password)
        else:
            text, ok = QInputDialog.getText(self, title, prompt)

        if ok:
            self.worker.set_input_response(text)
        else:
            self.worker.set_input_response(None)

    def show_login_frame(self, message):
        self.api_id_entry.clear()
        self.api_hash_entry.clear()
        self.phone_entry.clear()
        config = self._load_config()
        self.api_id_entry.setText(config.get("api_id", ""))
        self.api_hash_entry.setText(config.get("api_hash", ""))
        self.login_status_label.setText(message)
        self.stacked_widget.setCurrentWidget(self.login_page)

    def show_exporter_frame(self):
        self.export_status_label.setText("Ready to export.")
        self.stacked_widget.setCurrentWidget(self.exporter_page)

    def _save_config(self, api_id, api_hash):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'api_id': api_id, 'api_hash': api_hash}, f)

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}

    def closeEvent(self, event):
        """Handles the window closing event."""
        print("[LOG] Closing application...")
        self.worker.stop()
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()

def open_file(filepath):
    """Opens a file with the default system application."""
    try:
        if platform.system() == 'Darwin':       # macOS
            subprocess.call(('open', filepath))
        elif platform.system() == 'Windows':    # Windows
            os.startfile(os.path.realpath(filepath))
        else:                                   # Linux
            subprocess.call(('xdg-open', filepath))
    except Exception as e:
        QMessageBox.warning(None, "Warning", f"Could not open file automatically: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TelegramExporterApp()
    window.show()
    sys.exit(app.exec())
