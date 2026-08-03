#!/usr/bin/env python3
"""Render docs/demo.gif from tools/demo_animation.html.

The source is plain HTML/CSS and the only build tools are Chrome and FFmpeg.
No animation dependency is shipped with the application.
"""

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tools" / "demo_animation.html"
OUTPUT = ROOT / "docs" / "demo.gif"
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
)


def executable(explicit, candidates):
    if explicit:
        return explicit
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit("required executable not found: %s" % ", ".join(candidates))


def run(command):
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise SystemExit(completed.stderr[-2000:] or "command failed")


def main():
    parser = argparse.ArgumentParser(description="Render the README demo GIF")
    parser.add_argument("--chrome")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--review-frames", action="store_true",
                        help="keep first, quarter and middle PNGs beside the GIF")
    args = parser.parse_args()
    if args.frames < 2 or args.fps < 1:
        parser.error("--frames must be at least 2 and --fps must be positive")

    chrome = executable(args.chrome, CHROME_CANDIDATES)
    ffmpeg = executable(args.ffmpeg, ("ffmpeg",))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tlt-demo-animation-") as tmp_name:
        tmp = Path(tmp_name)
        for frame in range(args.frames):
            shot = tmp / ("frame-%03d.png" % frame)
            url = SOURCE.resolve().as_uri() + "?frame=%d&frames=%d" % (frame, args.frames)
            run([
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--disable-background-networking", "--disable-component-update",
                "--no-first-run", "--disable-default-apps", "--hide-scrollbars",
                "--force-device-scale-factor=1", "--window-size=960,540",
                "--virtual-time-budget=800", "--screenshot=" + str(shot), url,
            ])

        pending = output.with_name(output.stem + ".new" + output.suffix)
        run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(args.fps), "-i", str(tmp / "frame-%03d.png"),
            "-filter_complex",
            "[0:v]split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];"
            "[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
            "-loop", "0", str(pending),
        ])
        os.replace(pending, output)

        if args.review_frames:
            for index, suffix in ((0, "first"), (args.frames // 4, "quarter"),
                                  (args.frames // 2, "middle")):
                shutil.copyfile(tmp / ("frame-%03d.png" % index),
                                output.with_name(output.stem + "-" + suffix + ".png"))

    print("wrote %s (%d bytes, %.1f seconds)" % (
        output, output.stat().st_size, args.frames / args.fps))


if __name__ == "__main__":
    main()
