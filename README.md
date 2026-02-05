# BuildingCanada OCR V2

A local, privacy-focused document processing pipeline that converts PDF documents into clean Markdown. It uses **DeepSeek Vision** (via LM Studio) to perform high-quality OCR and layout analysis, preserving tables and structure.

## Features
- **Privacy-First**: Runs entirely on your local machine using LM Studio.
- **High Accuracy**: Uses DeepSeek Vision for state-of-the-art text and table extraction.
- **Header & Table Preservation**: correctly formats complex document structures into Markdown.
- **GUI & Watch Mode**: Simple graphical interface with a "Watch Mode" to automatically process new files dropped into the input folder.

## Prerequisites

Before running the application, you need to set up the following:

### 1. LM Studio (Required)
This application handles the AI processing.
1. Download [LM Studio](https://lmstudio.ai/).
2. Open LM Studio and search for/download a vision-capable model (e.g., `deepseek-vl-1.3b-chat` or similar).
3. Go to the **Local Server** tab (double-headed arrow icon).
4. **Start Server** on port `1234`.
5. Ensure the model is loaded.

### 2. Poppler (Required)
This is a system utility used to convert PDF pages into images.

- **macOS** (Homebrew):
  ```bash
  brew install poppler
  ```
- **Windows**:
  1. Download the latest binary from [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases).
  2. Extract the zip file.
  3. Add the `bin` folder to your System PATH environment variable.
- **Linux** (Debian/Ubuntu):
  ```bash
  sudo apt-get install poppler-utils
  ```

### 3. Python 3.10+
Ensure you have Python installed.

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/BuildingCanada_OCR_V2.git
   cd BuildingCanada_OCR_V2
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Graphical Interface (Recommended)
Run the GUI to easily select folders and monitor progress.

```bash
python gui.py
```

- **Select Input**: Choose the folder containing your PDFs.
- **Select Output**: Choose where you want the Markdown files to be saved.
- **Start Processing**: Processes all files currently in the folder.
- **Watch Mode**: Checks the folder every 5 seconds for new files and processes them automatically.

### Command Line
You can also run the pipeline purely from the terminal:

```bash
python main.py
```
Options:
- `--watch`: Enable continuous monitoring.
- `--workers N`: Set number of parallel threads (default: 4).
- `--sequential`: Force sequential processing (use if low on RAM).

## Troubleshooting

- **"Poppler not found"**: Ensure you installed Poppler and added it to your PATH (Windows) or installed via brew (Mac).
- **"Connection Error"**: Make sure LM Studio's server is running on port 1234.
