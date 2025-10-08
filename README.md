# Telegram Chat Exporter

A simple, user-friendly GUI tool to export your Telegram chat history into readable `.txt` or `.json` files.

## 📸 Screenshots
Here's a look at the two available interfaces.


**Modern** (`PyQt6`)                       and                           	**Classic** (`Tkinter`)

![PyQt6](https://github.com/Purple-Palm/Telethon-Chat-Dumper/blob/6dba5b8e138f4ff67219a3d0b34c7d4a68106dca/assets/images/python_OXixIzD0xd.png)![Tkinter](https://github.com/Purple-Palm/Telethon-Chat-Dumper/blob/6dba5b8e138f4ff67219a3d0b34c7d4a68106dca/assets/images/python_S2uDkJ35jT.png)

## ✨ Features
* **Easy to Use:** A clean graphical interface means no command-line knowledge is required.

* **Flexible Export Formats:** Save your chat history as a plain text file (`.txt`) or a structured JSON file (`.json`).

* **Secure & Local:** Your session and API credentials are saved securely on your own computer and are never sent anywhere else.

* **Standalone Executable:** No need to install Python or any libraries. Just download and run the .exe from the releases page.

* **Two UI Flavors:** Choose between a classic, lightweight interface (Tkinter) or a modern, stylish one (PyQt6).

## 🚀 Getting Started
There are two ways to use this application.

#### Option 1: Use the Pre-compiled Version (The Easy Way)
For most users, the simplest way is to download the ready-to-use application.

1. Go to the Releases Page of this repository.

2. Download the .exe file for either the PyQt6 or Tkinter version.

3. Run the downloaded file. That's it!

**A Note on Security:** The executables provided in the releases are compiled directly from the public source code in this repository. They are provided for your convenience and contain **no backdoors, viruses, or malicious code.**

#### Option 2: Run from the Python Source Code
If you are a developer and prefer to run the script directly, follow these steps.

1. **Clone the Repository:**

```
git clone https://github.com/Purple-Palm/Telethon-Chat-Dumper.git

cd YOUR_REPOSITORY
```

2. **Create and Activate a Virtual Environment:**<br/>
It's highly recommended to use a virtual environment to keep dependencies isolated.
```
# For Windows
python -m venv .venv
.\.venv\Scripts\activate

# For macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```
3. **Install the Required Libraries:**<br/>
The necessary libraries are listed in the requirements.txt file.
```
pip install -r requirements.txt
```
(This will install `telethon` and `pyqt6`)

4. **Run the Application:**<br/>
Choose which version of the app you want to run.
```
# To run the modern PyQt6 version
python telegram_dumper_pyqt6.py

# To run the classic Tkinter version
python telegram_dumper_tkinter.py
```
## 🛠️ Compiling Your Own Executable
If you've made changes to the code or simply want to compile the application yourself, you can do so using PyInstaller.

**Step 1: Install PyInstaller**<br/>
First, you need to install PyInstaller. Open your command prompt or terminal and run the following command:
```
pip install pyinstaller
```
**Step 2: The Compilation Command**<br/>
Navigate to the directory where your Python script is located. For a GUI application, it's best to use the `--onefile` and `--windowed` options.

Run the command for the script you wish to compile:
```
# For the PyQt6 version
pyinstaller --onefile --windowed telegram_dumper_pyqt6.py

# For the Tkinter version
pyinstaller --onefile --windowed telegram_dumper_tkinter.py
```
After the process completes, you will find your standalone `.exe` file inside the newly created `dist` folder.

>  **Note:** If you encounter issues with the executable crashing, you may need to specify hidden imports for Telethon. See the [PyInstaller documentation](https://pyinstaller.org/en/stable/usage.html) for more details.

## ⚠️ Disclaimer
This tool is intended for personal use to back up your own chat data. This tool is not affiliated with Telegram in **ANY** way. Please respect the privacy of others and use this tool responsibly. You will need your own Telegram **API ID** and **API Hash** to log in, which you can obtain from [my.telegram.org](https://my.telegram.org/auth).

## 🤝 Contributing
Contributions are welcome! If you have suggestions for improvements or find a bug, please feel free to open an issue or submit a pull request.

## License
This project is licensed under the MIT License. See the [LICENSE](https://github.com/Purple-Palm/Telethon-Chat-Dumper/blob/7ab0df5948bbd4674eac4c976340504287d1dab3/LICENSE) file for details.
