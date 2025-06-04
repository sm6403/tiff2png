# TIFF to PNG Converter

A Python application for converting TIFF images to PNG format with advanced options for image processing and optimization.

## Features

- Single file and batch conversion modes
- Resolution scaling and standard resolution presets
- Fill mode for exact resolution matching
- PNG optimization options
- Advanced color and compression settings
- Real-time file size estimation
- Image preview with crop visualization
- Progress tracking for batch conversion
- Customizable output naming for batch processing

## Requirements

- Python 3.6 or higher
- Pillow library

## Installation

1. Clone or download this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python src/main.py
   ```

2. Choose conversion mode:
   - Single File: Convert one TIFF file at a time
   - Batch Convert: Convert all TIFF files in a folder

3. Select input file/folder and output location

4. Configure conversion settings:
   - Basic settings:
     - Resolution scale (10-100%)
     - Standard resolution presets
     - Fill mode for exact resolution matching
     - PNG optimization
   - Advanced settings:
     - Color mode
     - Dithering method
     - Filter method
     - Chunk optimization
     - Interlacing

5. Click "Convert" to start the conversion process

## File Information

The application displays the following information for each file:
- Input file size and resolution
- Estimated output size
- Compression ratio

## Batch Processing

For batch conversion:
1. Select an input folder containing TIFF files
2. Choose an output folder
3. Set a root name for the output files (e.g., "Batch_01" will create files like "Batch_01_01.png")
4. Configure conversion settings
5. Click "Convert" to process all files

## Error Handling

- The application provides detailed error messages for failed conversions
- Batch processing continues even if individual files fail
- A summary of successful and failed conversions is shown at the end

## License

This project is licensed under the MIT License - see the LICENSE file for details. 