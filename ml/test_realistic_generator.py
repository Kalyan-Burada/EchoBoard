"""
ml/test_realistic_generator.py
Advanced realistic classroom board handwriting synthesizer:
- Uses real classroom chalkboard & whiteboard backgrounds extracted from actual dataset
- Applies natural handwriting irregularities: baseline drift, per-letter slant/jitter, stroke pressure variations
- Replicates authentic chalk grain, dust wiping smudges, and room lighting gradients
"""

import os
import glob
import random
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_ROOT, "synthetic_samples_v2")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATASET_IMG_DIR = os.path.join(REPO_ROOT, "dataset_cache", "images")

# Best human-like handwriting fonts on Windows
FONT_PATHS = [
    f for f in glob.glob("C:/Windows/Fonts/*.ttf")
    if any(k in f.lower() for k in [
        'inkfree', 'lhandw', 'segoesc', 'segoepr', 'mistral', 
        'mvboli', 'brushsci', 'freescpt', 'rage', 'scriptbl'
    ])
]


def extract_real_background_patch(target_w=512, target_h=120, board_type="green_chalkboard"):
    """Extracts or clones real texture from actual classroom photos in dataset."""
    real_images = glob.glob(os.path.join(DATASET_IMG_DIR, "*.*"))
    if not real_images:
        # Fallback realistic green board synthesis
        bg = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        bg[:, :, 0] = random.randint(35, 55)   # B
        bg[:, :, 1] = random.randint(65, 95)   # G
        bg[:, :, 2] = random.randint(45, 70)   # R
        noise = np.random.normal(0, 5, bg.shape).astype(np.float32)
        return np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # Filter for green chalkboard or whiteboard
    chosen_file = None
    if board_type == "green_chalkboard":
        green_candidates = [f for f in real_images if any(k in f for k in ["IMG0001", "IMG0002", "IMG0005", "IMG0007", "IMG0010"])]
        chosen_file = random.choice(green_candidates) if green_candidates else random.choice(real_images)
    else:
        white_candidates = [f for f in real_images if any(k in f for k in ["IMG0057", "IMG0058", "IMG0059"])]
        chosen_file = random.choice(white_candidates) if white_candidates else random.choice(real_images)

    img = cv2.imread(chosen_file)
    if img is None:
        img = np.full((target_h, target_w, 3), 70, dtype=np.uint8)

    h, w = img.shape[:2]
    # Crop a clean background patch with chalk dust / texture
    if h > target_h and w > target_w:
        y1 = random.randint(0, h - target_h)
        x1 = random.randint(0, w - target_w)
        patch = img[y1:y1+target_h, x1:x1+target_w].copy()
    else:
        patch = cv2.resize(img, (target_w, target_h))

    # Apply subtle illumination gradient across the board
    gradient = np.linspace(random.uniform(0.85, 1.0), random.uniform(1.0, 1.15), target_w)
    patch = np.clip(patch.astype(np.float32) * gradient[np.newaxis, :, np.newaxis], 0, 255).astype(np.uint8)
    return patch


def draw_realistic_handwriting(text, font_path, font_size=42, width=540, height=120, board_type="green_chalkboard"):
    """
    Renders handwriting with authentic human imperfections:
    - Character-by-character baseline wobble & spacing variations
    - Pressure variance across letters
    - Realistic chalk grain / marker bleed
    """
    bg = extract_real_background_patch(target_w=width, target_h=height, board_type=board_type)
    font = ImageFont.truetype(font_path, font_size)

    # Render character-by-character with natural human jitter
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    # Initial cursor position
    curr_x = random.randint(25, 45)
    base_y = height // 2 - font_size // 2 + random.randint(-4, 4)

    # Baseline slope (-2 to +2 degrees slope across line)
    slope = random.uniform(-0.03, 0.03)

    for i, char in enumerate(text):
        if char == " ":
            curr_x += int(font_size * random.uniform(0.35, 0.55))
            continue

        # Character vertical jitter
        char_y = int(base_y + (curr_x * slope) + random.uniform(-2.5, 2.5))
        
        # Individual character mask
        c_mask = Image.new("L", (font_size * 2, font_size * 2), 0)
        c_draw = ImageDraw.Draw(c_mask)
        c_draw.text((5, 5), char, font=font, fill=255)
        
        # Slight rotation for natural human letter slant (-4 to +4 deg)
        rot_angle = random.uniform(-4.0, 4.0)
        c_mask = c_mask.rotate(rot_angle, resample=Image.BICUBIC)
        
        # Paste onto line mask
        mask.paste(c_mask, (curr_x, char_y - 5), c_mask)

        # Advance cursor with slight kerning randomness
        bbox = draw.textbbox((0, 0), char, font=font)
        char_w = max(10, bbox[2] - bbox[0])
        curr_x += int(char_w + random.uniform(2, 6))

        if curr_x > width - 40:
            break

    mask_np = np.array(mask)

    if board_type == "green_chalkboard":
        # Authentic yellow or off-white classroom chalk
        chalk_color = random.choice([
            (160, 230, 245),  # Pale yellow-white chalk (typical on Indian school boards)
            (210, 235, 245),  # Soft white chalk
            (175, 215, 240),  # Warm chalk
        ])

        # Realistic chalk texture & pressure variations
        grain = np.random.uniform(0.65, 1.0, (height, width))
        chalk_dust = np.random.normal(0, 18, (height, width))
        chalk_alpha = np.clip((mask_np.astype(np.float32) / 255.0) * grain + (chalk_dust / 255.0), 0.0, 1.0)
        
        # Soft chalk bloom / dust around strokes
        bloom = cv2.GaussianBlur(chalk_alpha, (5, 5), 1.2) * 0.25
        total_alpha = np.clip(chalk_alpha + bloom, 0.0, 1.0)[:, :, np.newaxis]

        chalk_layer = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            chalk_layer[:, :, c] = chalk_color[c]

        result = (bg.astype(np.float32) * (1.0 - total_alpha) + chalk_layer * total_alpha).astype(np.uint8)

    else:
        # Whiteboard marker with ink pooling
        marker_color = random.choice([
            (40, 35, 30),     # Black marker
            (150, 60, 30),    # Blue marker
            (35, 30, 160),    # Red marker
        ])
        marker_alpha = (cv2.GaussianBlur(mask_np, (3, 3), 0.8).astype(np.float32) / 255.0)[:, :, np.newaxis]
        marker_layer = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            marker_layer[:, :, c] = marker_color[c]
        result = (bg.astype(np.float32) * (1.0 - marker_alpha) + marker_layer * marker_alpha).astype(np.uint8)

    # Slight camera lens blur (realistic phone camera capture)
    result = cv2.GaussianBlur(result, (3, 3), 0.3)
    return result


def generate_v2_samples():
    sample_tests = [
        ("Lohith went to washroom", "green_chalkboard"),
        ("Ramesh weds Vishnu", "green_chalkboard"),
        ("F = m * a (Newton)", "green_chalkboard"),
        ("SATVIC", "green_chalkboard"),
        ("Eshwar did not come", "green_chalkboard"),
        ("Posteriori Testing: Program", "whiteboard"),
    ]

    print("Generating ultra-realistic review samples...")
    out_files = []
    for idx, (text, b_type) in enumerate(sample_tests, start=1):
        font_p = random.choice(FONT_PATHS)
        font_n = os.path.splitext(os.path.basename(font_p))[0]
        img = draw_realistic_handwriting(text, font_p, font_size=38, width=540, height=120, board_type=b_type)
        fname = f"real_sample_{idx:02d}_{font_n}.png"
        fpath = os.path.join(OUTPUT_DIR, fname)
        cv2.imwrite(fpath, img)
        out_files.append((fpath, text, font_n))
        print(f"  [{idx}] Saved: {fname} | Label: \"{text}\"")

    print(f"\nGenerated in: {OUTPUT_DIR}")
    return out_files


if __name__ == "__main__":
    generate_v2_samples()
