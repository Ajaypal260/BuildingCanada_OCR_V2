import json
import logging
from pathlib import Path

CONFIG_FILE = Path("config.json")
DEFAULT_CONFIG = {
    "server_url": "http://localhost:1234/v1",
    "model_name": "deepseek-ocr",
    "input_dir": "",
    "output_dir": "",
    "max_workers": 4,
    "system_prompt": """You are a document transcription agent. Convert the image provided into strict Markdown.

Rules:
- Transcribe ALL text content exactly as it appears in the document.
- Represent tables using Markdown table syntax with proper column alignment.
- Preserve headings, subheadings, and hierarchical structure using appropriate Markdown heading levels (#, ##, ###, etc.).
- Maintain paragraph breaks and logical text flow.
- For lists, use proper Markdown list syntax (- or 1. 2. 3.).
- If there are images or figures, describe them briefly in [brackets].
- Do not add conversational filler, commentary, or explanations.
- Do not add any content that is not present in the original document.
- Output ONLY the Markdown transcription."""
}

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load_config()

    def load_config(self):
        """Load configuration from file, falling back to defaults."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for key, value in loaded.items():
                        if key in self.config:
                            self.config[key] = value
                logger.info("Configuration loaded from config.json")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        else:
            logger.info("No config file found, using defaults")

    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            logger.info("Configuration saved to config.json")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key):
        return self.config.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
