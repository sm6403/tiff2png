# TIFF to PNG Converter

Convert TIFF images to PNG from a Tkinter GUI or a headless command line, sharing one conversion core.

## Features

- Single-file and batch modes, with batch thumbnails and select/deselect
- Fit within or Fill (crop) to a target size, with a draggable, aspect-locked crop box
  (arrow keys move it, Shift+arrows resize it)
- Standard resolutions plus manual width and height, and percentage scaling
- Resampling filter: nearest, box, bilinear, hamming, bicubic, lanczos
- Colour mode (auto, RGB, RGBA, grey, palette) and Floyd-Steinberg dithering for palette output
- PNG optimize and compression level
- Live preview from a downscaled proxy and a PNG size estimate
- Batch conversion on a background thread with Cancel and a per-file failure summary
- Output naming as Root_NN or the original filename, with an overwrite prompt
  (Yes all / No skip existing / Cancel)
- Export every page of a multi-page TIFF as separate PNGs
- Handles CMYK (ICC managed), 16-bit, float and LAB TIFFs and EXIF orientation;
  ICC profile and DPI are preserved
- Logs tab and the sv-ttk theme

## Requirements

Python 3.12 or newer. Runtime dependencies are Pillow and sv-ttk.

## Install

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

This also installs the `tiff2png` (CLI) and `tiff2png-gui` commands.

## Run

GUI:

```
python -m tiff2png
```

CLI (any arguments select the CLI):

```
tiff2png INPUT... [-o OUT] [--scale PCT] [--fit WxH | --fill WxH] [--crop L,T,R,B]
         [--resample nearest|box|bilinear|hamming|bicubic|lanczos]
         [--colour auto|rgb|rgba|l|p] [--dither none|fs]
         [--no-optimize] [--compress-level N] [--all-pages]
         [--naming root|original] [--root NAME] [--overwrite]
```

INPUT is any mix of TIFF files and folders. `-o` defaults to the first input's folder.
`--root` defaults to `Batch`. `--crop` applies to every page, clamped per page.

Exit codes: 0 all converted, 1 some failed, 2 usage or plan error (including name collisions
and existing outputs without `--overwrite`).

Example:

```
tiff2png scans\ -o out --fill 1920x1080 --resample lanczos --all-pages
```

## Tests

```
python -m pytest
```

## Build the exe

```
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

This creates or reuses `.venv`, installs `.[dev,build]` (PyInstaller goes only into that venv), runs
the tests, cleans `build\` and `dist\`, and produces `dist\tiff2png.exe`. It stops on the first
failing step. `build\` and `dist\` are not committed; uploading a release is manual.

The exe is windowed: with no arguments it opens the GUI; with arguments it runs the CLI and writes
to the console it was launched from. A hidden smoke test converts a generated image without showing
a window:

```
dist\tiff2png.exe --self-test out.png
```

## License

MIT License, see the LICENSE file.
