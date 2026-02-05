
import main
import json
from pathlib import Path

# Print original file content
print("Original content:")
with open("processed_history.json", "r") as f:
    print(f.read())

# Trigger migration
print("\nLoading history (triggering migration)...")
history = main.load_processed_history()
print(f"Loaded type: {type(history)}")
print(f"Loaded content: {history}")

# Print new file content
print("\nNew content:")
with open("processed_history.json", "r") as f:
    print(f.read())
