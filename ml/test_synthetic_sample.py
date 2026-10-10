"""
ml/test_synthetic_sample.py
Generates sample synthetic classroom board handwriting images for review.
Simulates:
- Blackboard with chalk texture, chalk dust, and stroke irregularities
- Whiteboard with dry-erase marker texture, slight glare, and ink variation
"""

import os
import glob
import random
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_ROOT, "synthetic_samples")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Discover system handwriting fonts
FONT_CANDIDATES = [
    f for f in glob.glob("C:/Windows/Fonts/*.ttf")
    if any(k in f.lower() for k in [
        'inkfree', 'lhandw', 'segoesc', 'segoepr', 'mistral', 
        'mvboli', 'brushsci', 'comic', 'freescpt', 'rage', 'script', 'forte'
    ])
]
if not FONT_CANDIDATES:
    FONT_CANDIDATES = ["arial.ttf"]


def create_blackboard_background(width, height):
    """Generate realistic dark blackboard slate texture with subtle chalk haze."""
    # Dark charcoal base (intensity 25-45)
    base_val = random.randint(28, 42)
    bg = np.full((height, width), base_val, dtype=np.uint8)

    # Add slate grain / Perlin-like noise
    noise = np.random.normal(0, 4, (height, width)).astype(np.float32)
    bg = np.clip(bg.astype(np.float32) + noise, 15, 60).astype(np.uint8)

    # Chalk dust / eraser smudges
    for _ in range(random.randint(2, 5)):
        cx, cy = random.randint(0, width), random.randint(0, height)
        rx, ry = random.randint(20, width // 2), random.randint(5, height // 2)
        dust = np.zeros((height, width), dtype=np.float32)
        cv2.ellipse(dust, (cx, cy), (rx, ry), random.randint(0, 180), 0, 360, random.uniform(8, 22), -1)
        dust = cv2.GaussianBlur(dust, (31, 15), 0)
        bg = np.clip(bg.astype(np.float32) + dust, 0, 255).astype(np.uint8)

    return cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)


def create_whiteboard_background(width, height):
    """Generate clean whiteboard texture with subtle room lighting gradient."""
    base_val = random.randint(235, 248)
    bg = np.full((height, width), base_val, dtype=np.uint8)
    # Subtle grain
    noise = np.random.normal(0, 2, (height, width)).astype(np.float32)
    bg = np.clip(bg.astype(np.float32) + noise, 215, 255).astype(np.uint8)
    return cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)


def render_chalk_text(text, font_path, font_size=32, target_height=64, target_width=512, board_type="blackboard"):
    """Renders text with authentic chalk/marker stroke imperfections."""
    font = ImageFont.truetype(font_path, font_size)

    # Create temporary text mask
    mask_img = Image.new("L", (target_width, target_height), 0)
    draw = ImageDraw.Draw(mask_img)

    # Measure text
    bbox = draw.textbbox((0, 0), text, font=font)
    t_w = bbox[2] - bbox[0]
    t_h = bbox[3] - bbox[1]

    # Center with slight jitter
    x_offset = max(10, random.randint(15, max(16, target_width - t_w - 20)))
    y_offset = max(5, (target_height - t_h) // 2 + random.randint(-3, 3))

    draw.text((x_offset, y_offset), text, font=font, fill=255)
    mask_np = np.array(mask_img)

    if board_type == "blackboard":
        bg = create_blackboard_background(target_width, target_height)

        # Chalk stroke texture: granular texture & varied pressure
        chalk_texture = np.random.uniform(0.75, 1.0, (target_height, target_width))
        chalk_noise = np.random.normal(0, 15, (target_height, target_width))
        chalk_intensity = np.clip(mask_np.astype(np.float32) * chalk_texture + chalk_noise, 0, 255)

        # Apply chalk color (soft off-white / light yellow chalk)
        chalk_color = random.choice([
            (235, 240, 242),  # White chalk
            (210, 240, 250),  # Yellowish chalk
            (240, 225, 215),  # Cyan tint chalk
        ])

        alpha = (chalk_intensity / 255.0)[:, :, np.newaxis]
        colored_chalk = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            colored_chalk[:, :, c] = chalk_color[c]

        result = (bg.astype(np.float32) * (1.0 - alpha) + colored_chalk * alpha).astype(np.uint8)

    else:  # Whiteboard
        bg = create_whiteboard_background(target_width, target_height)

        # Marker color (Black, Blue, Dark Red, Dark Green)
        marker_color = random.choice([
            (30, 30, 35),     # Black dry-erase
            (140, 50, 30),    # Blue marker
            (35, 30, 150),    # Red marker
            (40, 110, 30),    # Green marker
        ])

        # Slightly soften edges like dry erase ink
        marker_mask = cv2.GaussianBlur(mask_np, (3, 3), 0.6)
        alpha = (marker_mask / 255.0)[:, :, np.newaxis]

        colored_marker = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            colored_marker[:, :, c] = marker_color[c]

        result = (bg.astype(np.float32) * (1.0 - alpha) + colored_marker * alpha).astype(np.uint8)

    return result


def generate_samples():
    sample_texts = [
        ("Lohith went to lab", "blackboard"),
        ("F = m * a", "blackboard"),
        ("Eshwar completed assignment", "whiteboard"),
        ("E = m * c^2", "whiteboard"),
        ("Newton Second Law", "blackboard"),
        ("Integral of 2x dx = x^2 + C", "whiteboard"),
    ]

    print("Generating review samples...")
    generated_files = []

    for idx, (text, b_type) in enumerate(sample_texts, start=1):
        font_path = random.choice(FONT_CANDIDATES)
        font_name = os.path.splitext(os.path.basename(font_path))[0]
        img = render_chalk_text(text, font_path, font_size=30, target_height=64, target_width=480, board_type=b_type)

        filename = f"sample_{idx:02d}_{b_type}_{font_name}.png"
        out_path = os.path.join(OUTPUT_DIR, filename)
        cv2.imwrite(out_path, img)
        generated_files.append((out_path, text, b_type, font_name))
        print(f"  [{idx}] Saved: {filename} | Text: \"{text}\" | Font: {font_name}")

    print(f"\nAll {len(generated_files)} samples generated in: {OUTPUT_DIR}")
    return generated_files


if __name__ == "__main__":
    generate_samples()
