#!/usr/bin/env python3
"""
Document Processing Pipeline: PDF to Markdown using DeepSeek Vision via LM Studio

SETUP REQUIREMENTS:
-------------------
1. Install poppler on macOS (required for pdf2image):
   brew install poppler

2. Install Python dependencies:
   pip install -r requirements.txt

3. Ensure LM Studio is running with the DeepSeek Vision model loaded,
   with the local server enabled (typically at http://localhost:1234/v1)
"""

import os
import sys
import base64
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable,  Union
import json
from datetime import datetime




from pdf2image import convert_from_path
from PIL import Image
from openai import OpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError

# ============================================================================
# Configuration
# ============================================================================

# LM Studio local server configuration
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"  # Dummy key, LM Studio doesn't require auth

# Model name (update this to match your loaded model in LM Studio)
MODEL_NAME = "deepseek-ocr"

# Directory configuration
INPUT_DIR = Path("./input")
OUTPUT_DIR = Path("./output")
HISTORY_FILE = Path("processed_history.json")


# PDF to image conversion settings
DPI = 300  # High resolution for small text
IMAGE_FORMAT = "PNG"

# Concurrency settings
MAX_WORKERS = 4  # Number of parallel page processing threads
# Set to 1 for sequential processing if your Mac struggles with parallel requests

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("pipeline.log")
        ]
    )

logger = logging.getLogger(__name__)


# ============================================================================
# System Prompt for Document Transcription
# ============================================================================

SYSTEM_PROMPT = """You are a document transcription agent. Convert the image provided into strict Markdown.

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

# ============================================================================
# Helper Functions
# ============================================================================


def ensure_directories(input_dir: Path, output_dir: Path):
    """Create input and output directories if they don't exist."""
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Input directory: {input_dir.absolute()}")
    logger.info(f"Output directory: {output_dir.absolute()}")


def image_to_base64(image: Image.Image) -> str:
    """Convert a PIL Image to a base64-encoded string."""
    import io
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def create_client() -> OpenAI:
    """Create an OpenAI client configured for LM Studio."""
    return OpenAI(
        base_url=LM_STUDIO_BASE_URL,
        api_key=LM_STUDIO_API_KEY,
        timeout=120.0  # Increase timeout for vision model processing
    )


def load_processed_history() -> dict:
    """
    Load the list of already processed files from history.
    Returns a dictionary mapping filename to metadata.
    """
    if not HISTORY_FILE.exists():
        return {}
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Migration: If it's a list (old format), convert to dict
        if isinstance(data, list):
            logger.info("Migrating history file to new format with timestamps...")
            new_data = {}
            for filename in data:
                new_data[filename] = {"processed_at": "unknown", "status": "legacy"}
            
            # Save immediately
            try:
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save migrated history: {e}")
                
            return new_data
            
        return data
    except Exception as e:
        logger.error(f"Failed to load history file: {e}")
        return {}


def mark_file_as_processed(filename: str):
    """Add a filename to the processed history with timestamp."""
    history = load_processed_history()
    timestamp = datetime.now().isoformat()
    
    history[filename] = {
        "processed_at": timestamp,
        "status": "success"
    }
    
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        logger.info(f"Recorded to history at {timestamp}")
    except Exception as e:
        logger.error(f"Failed to update history file: {e}")


def process_image_with_vision(
    client: OpenAI,
    image: Image.Image,
    page_num: int,
    total_pages: int
) -> Optional[str]:
    """
    Send an image to the DeepSeek Vision model and get Markdown output.
    
    Args:
        client: OpenAI client instance
        image: PIL Image to process
        page_num: Current page number (for logging)
        total_pages: Total number of pages (for logging)
    
    Returns:
        Markdown string or None if processing failed
    """
    image_base64 = image_to_base64(image)
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Processing page {page_num}/{total_pages} (attempt {attempt}/{MAX_RETRIES})")
            
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "Transcribe this document page to Markdown."
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1  # Low temperature for consistent transcription
            )
            
            result = response.choices[0].message.content
            logger.info(f"Successfully processed page {page_num}/{total_pages}")
            return result
            
        except APIConnectionError as e:
            logger.error(f"Connection error on page {page_num}: {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to process page {page_num} after {MAX_RETRIES} attempts")
                return None
                
        except APITimeoutError as e:
            logger.error(f"Timeout error on page {page_num}: {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to process page {page_num} after {MAX_RETRIES} attempts")
                return None
                
        except RateLimitError as e:
            logger.error(f"Rate limit error on page {page_num}: {e}")
            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to process page {page_num} after {MAX_RETRIES} attempts")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error on page {page_num}: {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to process page {page_num} after {MAX_RETRIES} attempts")
                return None
    
    return None


def convert_pdf_to_images(pdf_path: Path) -> list[Image.Image]:
    """
    Convert all pages of a PDF to high-resolution images.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        List of PIL Images, one per page
    """
    logger.info(f"Converting PDF to images: {pdf_path.name}")
    
    try:
        images = convert_from_path(
            pdf_path,
            dpi=DPI,
            fmt=IMAGE_FORMAT.lower()
        )
        logger.info(f"Converted {len(images)} pages from {pdf_path.name}")
        return images
    except Exception as e:
        logger.error(f"Failed to convert PDF {pdf_path.name}: {e}")
        raise


def process_page_task(args: tuple) -> tuple[int, Optional[str]]:
    """
    Worker function for parallel page processing.
    
    Args:
        args: Tuple of (client, image, page_num, total_pages)
    
    Returns:
        Tuple of (page_num, markdown_content or None)
    """
    client, image, page_num, total_pages = args
    result = process_image_with_vision(client, image, page_num, total_pages)
    return (page_num, result)


def process_pdf(pdf_path: Path, output_dir: Path, client: OpenAI) -> bool:
    """
    Process a single PDF file: convert pages to images, send to vision model,
    and save the combined Markdown output.
    
    Args:
        pdf_path: Path to the PDF file
        client: OpenAI client instance
    
    Returns:
        True if processing succeeded, False otherwise
    """
    logger.info(f"{'=' * 60}")
    logger.info(f"Processing: {pdf_path.name}")
    logger.info(f"{'=' * 60}")
    
    try:
        # Convert PDF to images
        images = convert_pdf_to_images(pdf_path)
        total_pages = len(images)
        
        if total_pages == 0:
            logger.warning(f"No pages found in {pdf_path.name}")
            return False
        
        # Process pages (parallel or sequential based on MAX_WORKERS)
        page_results: dict[int, str] = {}
        
        if MAX_WORKERS > 1:
            # Parallel processing
            logger.info(f"Processing {total_pages} pages in parallel (max {MAX_WORKERS} workers)")
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Prepare tasks
                tasks = [
                    (client, img, i + 1, total_pages)
                    for i, img in enumerate(images)
                ]
                
                # Submit all tasks
                futures = {
                    executor.submit(process_page_task, task): task[2]  # task[2] is page_num
                    for task in tasks
                }
                
                # Collect results
                for future in as_completed(futures):
                    page_num = futures[future]
                    try:
                        result_page_num, markdown = future.result()
                        if markdown:
                            page_results[result_page_num] = markdown
                    except Exception as e:
                        logger.error(f"Error processing page {page_num}: {e}")
        else:
            # Sequential processing
            logger.info(f"Processing {total_pages} pages sequentially")
            
            for i, image in enumerate(images):
                page_num = i + 1
                markdown = process_image_with_vision(client, image, page_num, total_pages)
                if markdown:
                    page_results[page_num] = markdown
        
        # Combine results in page order
        if not page_results:
            logger.error(f"No pages were successfully processed for {pdf_path.name}")
            return False
        
        combined_markdown = []
        for page_num in sorted(page_results.keys()):
            combined_markdown.append(f"<!-- Page {page_num} -->\n")
            combined_markdown.append(page_results[page_num])
            combined_markdown.append("\n\n---\n\n")  # Page separator
        
        # Remove trailing separator
        if combined_markdown:
            combined_markdown = combined_markdown[:-1]
        
        # Write output file
        output_filename = pdf_path.stem + ".md"
        output_path = output_dir / output_filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("".join(combined_markdown))
        
        logger.info(f"Successfully saved: {output_path}")
        logger.info(f"Processed {len(page_results)}/{total_pages} pages")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to process {pdf_path.name}: {e}")
        return False


def scan_and_process(input_dir: Path = INPUT_DIR, output_dir: Path = OUTPUT_DIR, progress_callback: Optional[Callable[[int, int], None]] = None):
    """
    Scan the input directory for PDF files and process them.
    """
    ensure_directories(input_dir, output_dir)
    
    # Find all PDF files in input directory
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        logger.info("No PDF files found in input directory.")
        logger.info(f"Place PDF files in: {input_dir.absolute()}")
        return
    
    total_files = len(pdf_files)
    logger.info(f"Found {total_files} PDF file(s) to process")
    
    # Initial status update
    if progress_callback:
        progress_callback(0, total_files)
    
    # Create client
    client = create_client()
    
    # Test connection to LM Studio
    try:
        logger.info("Testing connection to LM Studio...")
        client.models.list()
        logger.info("Successfully connected to LM Studio")
    except Exception as e:
        logger.error(f"Failed to connect to LM Studio at {LM_STUDIO_BASE_URL}")
        logger.error(f"Error: {e}")
        logger.error("Please ensure LM Studio is running with the local server enabled.")
        sys.exit(1)
    
    
    # Process each PDF
    results = {"success": [], "failed": [], "skipped": []}
    
    # Load history
    processed_history = load_processed_history()
    
    processed_count = 0
    
    for pdf_path in pdf_files:
        processed_count += 1
        
        if progress_callback:
            progress_callback(processed_count, total_files)

        if pdf_path.name in processed_history:
            logger.info(f"Skipping already processed file: {pdf_path.name}")
            results["skipped"].append(pdf_path.name)
            continue

        success = process_pdf(pdf_path, output_dir, client)
        if success:
            results["success"].append(pdf_path.name)
            mark_file_as_processed(pdf_path.name)
        else:
            results["failed"].append(pdf_path.name)
    
    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("PROCESSING COMPLETE")
    logger.info(f"{'=' * 60}")
    logger.info(f"Successful: {len(results['success'])}")
    logger.info(f"Skipped: {len(results['skipped'])}")
    logger.info(f"Failed: {len(results['failed'])}")
    
    if results["failed"]:
        logger.warning(f"Failed files: {', '.join(results['failed'])}")


def watch_folder(input_dir: Path = INPUT_DIR, output_dir: Path = OUTPUT_DIR, stop_event=None):
    """
    Continuously watch the input folder for new PDF files.
    Processes files and then moves them to a 'processed' subfolder.
    """
    ensure_directories(input_dir, output_dir)
    processed_dir = input_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    
    logger.info(f"Watching folder: {input_dir.absolute()}")
    logger.info("Press Ctrl+C to stop")
    
    client = create_client()
    
    # Test connection
    try:
        client.models.list()
        logger.info("Connected to LM Studio")
    except Exception as e:
        logger.error(f"Failed to connect to LM Studio: {e}")
        sys.exit(1)
    
    processed_files = set()
    # Pre-populate with existing history to avoid re-processing if items were moved back manually
    # load_processed_history returns a dict now, checking 'in' works for keys
    processed_files.update(load_processed_history().keys())
    
    try:
        while True:
            if stop_event and stop_event.is_set():
                logger.info("Stopping watch mode...")
                break
                
            pdf_files = list(input_dir.glob("*.pdf"))
            
            for pdf_path in pdf_files:
                if stop_event and stop_event.is_set():
                    break
                    
                if pdf_path.name not in processed_files:
                    success = process_pdf(pdf_path, output_dir, client)
                    
                    if success:
                        # Move to processed folder
                        new_path = processed_dir / pdf_path.name
                        pdf_path.rename(new_path)
                        logger.info(f"Moved {pdf_path.name} to processed folder")
                        
                        # Also add to persistent history
                        mark_file_as_processed(pdf_path.name)
                    
                    processed_files.add(pdf_path.name)
            
            # Wait before next scan
            time.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("\nStopping folder watch...")


def main():
    """
    Main entry point.
    
    Usage:
        python main.py          # Process all PDFs in input folder once
        python main.py --watch  # Continuously watch for new PDFs
    """
    global MAX_WORKERS  # Declare global before any usage
    
    import argparse
    
    default_workers = MAX_WORKERS  # Store default before argparse uses it
    
    parser = argparse.ArgumentParser(
        description="PDF to Markdown converter using DeepSeek Vision"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously watch the input folder for new PDFs"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers,
        help=f"Number of parallel workers (default: {default_workers})"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Process pages sequentially (overrides --workers)"
    )
    
    args = parser.parse_args()
    
    # Update global config based on args
    if args.sequential:
        MAX_WORKERS = 1
    else:
        MAX_WORKERS = args.workers
        
    # Setup logging if running as main
    setup_logging()
    
    if args.watch:
        watch_folder(INPUT_DIR, OUTPUT_DIR)
    else:
        scan_and_process(INPUT_DIR, OUTPUT_DIR)


if __name__ == "__main__":
    main()
