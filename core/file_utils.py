"""
Memory-efficient file operations and JSON handling for TTScraper
"""
import json
import os
import gzip
import tempfile
from typing import Any, Dict, List, Iterator, Optional, Union
from pathlib import Path
import logging
from contextlib import contextmanager


class MemoryEfficientJSONHandler:
    """Handle large JSON files efficiently to prevent memory issues."""
    
    def __init__(self, max_file_size_mb: int = 50, use_compression: bool = True):
        self.max_file_size_mb = max_file_size_mb
        self.use_compression = use_compression
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def save_json(self, data: Any, filepath: Union[str, Path], compress: Optional[bool] = None) -> str:
        """
        Save JSON data efficiently, with optional compression for large files.
        
        Args:
            data: Data to save
            filepath: Output file path
            compress: Whether to compress (None = auto-decide based on size)
            
        Returns:
            Final filepath (may have .gz extension if compressed)
        """
        filepath = Path(filepath)
        
        # First, check estimated size
        temp_data = json.dumps(data, ensure_ascii=False)
        estimated_size_mb = len(temp_data.encode('utf-8')) / (1024 * 1024)
        
        # Decide compression
        should_compress = compress if compress is not None else (
            self.use_compression and estimated_size_mb > self.max_file_size_mb
        )
        
        if should_compress:
            final_path = filepath.with_suffix(filepath.suffix + '.gz')
            with gzip.open(final_path, 'wt', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved compressed JSON: {final_path} ({estimated_size_mb:.1f}MB)")
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved JSON: {filepath} ({estimated_size_mb:.1f}MB)")
            final_path = filepath
        
        return str(final_path)
    
    def load_json(self, filepath: Union[str, Path]) -> Any:
        """
        Load JSON data, automatically handling compressed files.
        
        Args:
            filepath: Path to JSON file (with or without .gz extension)
            
        Returns:
            Loaded data
        """
        filepath = Path(filepath)
        
        # Try compressed version first if original doesn't exist
        if not filepath.exists() and not str(filepath).endswith('.gz'):
            compressed_path = filepath.with_suffix(filepath.suffix + '.gz')
            if compressed_path.exists():
                filepath = compressed_path
        
        if str(filepath).endswith('.gz'):
            with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def stream_json_array(self, filepath: Union[str, Path]) -> Iterator[Dict[str, Any]]:
        """
        Stream large JSON arrays without loading everything into memory.
        
        Args:
            filepath: Path to JSON file containing an array
            
        Yields:
            Individual items from the JSON array
        """
        filepath = Path(filepath)
        
        open_func = gzip.open if str(filepath).endswith('.gz') else open
        mode = 'rt' if str(filepath).endswith('.gz') else 'r'
        
        with open_func(filepath, mode, encoding='utf-8') as f:
            # Simple streaming parser for JSON arrays
            buffer = ""
            bracket_count = 0
            in_string = False
            escape_next = False
            item_start = None
            
            content = f.read()
            for char in str(content):  # Ensure char is string
                buffer += char
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if in_string:
                    continue
                
                if char == '{':
                    if bracket_count == 0:
                        item_start = len(buffer) - 1
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0 and item_start is not None:
                        # Extract and parse the complete JSON object
                        item_json = buffer[item_start:]
                        # Find the end of this object
                        end_pos = item_json.find('}') + 1
                        item_json = item_json[:end_pos]
                        
                        try:
                            item = json.loads(item_json)
                            yield item
                        except json.JSONDecodeError:
                            # Skip malformed items
                            pass
                        
                        # Reset for next item
                        buffer = buffer[item_start + end_pos:]
                        item_start = None


class FileManager:
    """Manage temporary and output files efficiently."""
    
    def __init__(self, base_dir: Optional[str] = None, cleanup_on_exit: bool = True):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.cleanup_on_exit = cleanup_on_exit
        self.temp_files: List[Path] = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @contextmanager
    def temp_file(self, suffix: str = '.json', prefix: str = 'ttscraper_'):
        """Context manager for temporary files."""
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w+',
                suffix=suffix,
                prefix=prefix,
                dir=self.base_dir,
                delete=False,
                encoding='utf-8'
            )
            self.temp_files.append(Path(temp_file.name))
            yield temp_file
        finally:
            if temp_file:
                temp_file.close()
    
    def create_output_filename(self, base_name: str, video_id: str, extension: str = '.json') -> Path:
        """Create a standardized output filename."""
        timestamp = int(time.time())
        filename = f"{base_name}_{video_id}_{timestamp}{extension}"
        return self.base_dir / filename
    
    def cleanup_temp_files(self):
        """Clean up temporary files."""
        cleaned = 0
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    cleaned += 1
            except Exception as e:
                self.logger.warning(f"Could not clean up {temp_file}: {e}")
        
        if cleaned > 0:
            self.logger.info(f"Cleaned up {cleaned} temporary files")
        
        self.temp_files.clear()
    
    def __del__(self):
        """Cleanup on deletion."""
        if self.cleanup_on_exit:
            self.cleanup_temp_files()


class ChunkedProcessor:
    """Process large datasets in chunks to manage memory usage."""
    
    def __init__(self, chunk_size: int = 100):
        self.chunk_size = chunk_size
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_in_chunks(self, data: List[Any], processor_func, **kwargs) -> List[Any]:
        """
        Process a large list in chunks.
        
        Args:
            data: List of items to process
            processor_func: Function to process each chunk
            **kwargs: Additional arguments for processor_func
            
        Returns:
            Combined results from all chunks
        """
        results = []
        total_chunks = (len(data) + self.chunk_size - 1) // self.chunk_size
        
        self.logger.info(f"Processing {len(data)} items in {total_chunks} chunks of {self.chunk_size}")
        
        for i in range(0, len(data), self.chunk_size):
            chunk = data[i:i + self.chunk_size]
            chunk_num = (i // self.chunk_size) + 1
            
            self.logger.debug(f"Processing chunk {chunk_num}/{total_chunks}")
            
            try:
                chunk_result = processor_func(chunk, **kwargs)
                if chunk_result:
                    results.extend(chunk_result if isinstance(chunk_result, list) else [chunk_result])
            except Exception as e:
                self.logger.error(f"Error processing chunk {chunk_num}: {e}")
                continue
        
        self.logger.info(f"Completed processing {total_chunks} chunks, got {len(results)} results")
        return results


# Global instances
json_handler = MemoryEfficientJSONHandler()
file_manager = FileManager()

import time
