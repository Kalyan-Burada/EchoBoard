"""
ml/generate_general_dataset.py
Universal Multi-Subject Dataset Generator for Board Handwriting:
- Subjects: English, Mathematics, Physics, Chemistry
- Structures: Single words, full sentences, multi-line equations & derivations
- Boards: Green Chalkboard, Black Slate, Whiteboard
- Works seamlessly on both Windows and Google Colab (Linux)
"""

import os
import sys

# Prevent OpenBLAS memory allocation issues on Windows and Linux
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import json
import glob
import random
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(REPO_ROOT, "dataset_cache")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
MANIFEST_PATH = os.path.join(DATASET_DIR, "manifest.json")

os.makedirs(IMAGES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Comprehensive Academic Corpora
# ---------------------------------------------------------------------------

ENGLISH_VOCAB = [
    # Single common words & greetings
    "Hello", "Welcome", "Hi", "Good morning", "Today", "Topic", "Chapter", "Unit",
    "Section", "Exercise", "Problem", "Solution", "Question", "Answer", "Example",
    "Homework", "Assignment", "Page", "Test", "Exam", "Quiz", "Review", "Summary",
    "Note", "Important", "Definition", "Theorem", "Proof", "Diagram", "Figure",
    "Table", "Graph", "Calculate", "Evaluate", "Simplify", "Solve", "Find", "Given",
    "Hence", "Therefore", "Because", "Assume", "Let", "Result", "Total",
    "apple", "water", "school", "college", "teacher", "student", "class", "board",
    "science", "history", "english", "math", "physics", "chemistry", "biology",
    "reading", "writing", "learn", "study", "work", "time", "world", "number",
    "line", "point", "circle", "angle", "triangle", "true", "false", "equal",
    # Full sentences & classroom headings
    "Active Voice and Passive Voice", "Direct and Indirect Speech",
    "Present Continuous Tense", "Subject Verb Agreement",
    "Summary of Chapter 3: The Portrait of a Lady",
    "Identify the figure of speech: Metaphor",
    "Write a formal letter to the editor",
    "Reading Comprehension: Passage 2",
    "Vocabulary: Ephemeral, Resilient, Candid",
    "Action speaks louder than words",
    "Practice makes a person perfect",
    "Notice: Annual Sports Day next week",
    "Grammar Rule: Use of articles A, An, The",
    "Prepositions of Time: At, On, In",
    "Degrees of Comparison: Positive, Comparative, Superlative",
    "Although it was raining, we played",
]

MATH_VOCAB = [
    # Single-line formulas
    "(a + b)^2 = a^2 + 2ab + b^2",
    "(a - b)^2 = a^2 - 2ab + b^2",
    "a^2 - b^2 = (a - b)(a + b)",
    "sin^2(x) + cos^2(x) = 1",
    "1 + tan^2(theta) = sec^2(theta)",
    "tan(theta) = sin(theta) / cos(theta)",
    "sin(2x) = 2 sin(x) cos(x)",
    "dy/dx = 2x + 5",
    "dy/dx of sin(x) = cos(x)",
    "dy/dx of e^x = e^x",
    "Integral of x^n dx = x^(n+1)/(n+1) + C",
    "Integral of 1/x dx = ln|x| + C",
    "lim x->0 (sin x / x) = 1",
    "y = mx + c (Slope Intercept)",
    "Ax + By + C = 0",
    "x = (-b +- sqrt(b^2 - 4ac)) / (2a)",
    "Area of Circle = pi * r^2",
    "Circumference = 2 * pi * r",
    "Volume of Sphere = 4/3 * pi * r^3",
    "det(A) = ad - bc",
    "Pythagoras Theorem: a^2 + b^2 = c^2",
    "log(xy) = log(x) + log(y)",
    "e^(i * pi) + 1 = 0",
    "T_n = a + (n-1)d",
    "2x + 3y = 12",
    "x^2 - 5x + 6 = 0",
    "f(x) = 3x^2 - 4x + 1",
]

PHYSICS_VOCAB = [
    "F = m * a (Newton Second Law)",
    "v = u + a * t",
    "s = u * t + 0.5 * a * t^2",
    "v^2 = u^2 + 2 * a * s",
    "p = m * v (Linear Momentum)",
    "Kinetic Energy = 1/2 * m * v^2",
    "Potential Energy = m * g * h",
    "Work Done W = F * d * cos(theta)",
    "Power P = Work / Time = F * v",
    "F = G * (m1 * m2) / r^2",
    "Acceleration g = 9.8 m/s^2",
    "Ohm's Law: V = I * R",
    "Electrical Power P = V * I = I^2 * R",
    "Series Resistance: R = R1 + R2 + R3",
    "Parallel Resistance: 1/R = 1/R1 + 1/R2",
    "Capacitance C = Q / V",
    "Magnetic Force F = q * (v x B)",
    "Speed of Light c = 3 x 10^8 m/s",
    "Snell's Law: n1 sin(i) = n2 sin(r)",
    "Lens Formula: 1/f = 1/v - 1/u",
    "First Law of Thermodynamics: dQ = dU + dW",
    "Ideal Gas Law: P * V = n * R * T",
    "Wave Speed v = f * lambda",
    "Einstein Mass Energy: E = m * c^2",
    "Planck Equation: E = h * nu",
]

CHEMISTRY_VOCAB = [
    "2 H2 + O2 -> 2 H2O",
    "CH4 + 2 O2 -> CO2 + 2 H2O",
    "HCl + NaOH -> NaCl + H2O",
    "CaCO3 -> CaO + CO2",
    "2 Na + 2 H2O -> 2 NaOH + H2",
    "N2 + 3 H2 -> 2 NH3 (Haber Process)",
    "Photosynthesis: 6 CO2 + 6 H2O -> C6H12O6 + 6 O2",
    "Respiration: C6H12O6 + 6 O2 -> 6 CO2 + 6 H2O",
    "Fe + CuSO4 -> FeSO4 + Cu",
    "Zn + 2 HCl -> ZnCl2 + H2",
    "pH = -log10[H+]",
    "pOH = -log10[OH-]",
    "pH + pOH = 14 at 25 deg C",
    "Avogadro Number N_A = 6.022 x 10^23",
    "Molarity M = moles / Volume (L)",
    "Boyle's Law: P1 * V1 = P2 * V2",
    "Charles's Law: V1 / T1 = V2 / T2",
    "Oxidation is Loss of electrons (OIL)",
    "Reduction is Gain of electrons (RIG)",
    "Benzene Formula: C6H6",
    "Ethanol: C2H5OH",
    "Acetic Acid: CH3COOH",
    "Sulfuric Acid: H2SO4",
    "Nitric Acid: HNO3",
    "Sodium Hydroxide: NaOH",
]

# Multi-line derivations and stacked formulas
MULTILINE_VOCAB = [
    ("Step 1: 2x + 5 = 15\nStep 2: 2x = 10\nStep 3: x = 5", "Equation", "Mathematics"),
    ("Given: u = 0, a = 2, t = 5\nv = u + at = 0 + 10 = 10 m/s", "Equation", "Physics"),
    ("Reactants: 2 H2 + O2\nProduct: 2 H2O\nEnthalpy: Exothermic", "Equation", "Chemistry"),
    ("Topic: Newton's Laws\nLaw 1: Inertia\nLaw 2: F = m * a", "Text", "Physics"),
    ("Chapter 4: Quadratic Equations\nStandard Form: ax^2 + bx + c = 0\nRoots: x = (-b +- sqrt(D))/(2a)", "Equation", "Mathematics"),
    ("Homework Assignment:\n1. Exercise 3.1 Questions 1 to 5\n2. Learn definitions on page 42", "Text", "English"),
]

# ---------------------------------------------------------------------------
# Cross-Platform Font Detection (Windows + Google Colab Linux)
# ---------------------------------------------------------------------------

FONT_CANDIDATES = [
    f for f in (
        glob.glob("C:/Windows/Fonts/*.ttf") +
        glob.glob("C:/Windows/Fonts/*.otf") +
        glob.glob("/usr/share/fonts/**/*.ttf", recursive=True) +
        glob.glob("/usr/share/fonts/**/*.otf", recursive=True) +
        glob.glob("/etc/fonts/**/*.ttf", recursive=True) +
        glob.glob("/root/.fonts/**/*.ttf", recursive=True)
    )
    if any(k in f.lower() for k in [
        'inkfree', 'lhandw', 'segoesc', 'segoepr', 'mistral',
        'mvboli', 'brushsci', 'freescpt', 'rage', 'scriptbl', 'comic', 'forte',
        'arial', 'calibri', 'dejavu', 'liberation', 'free'
    ])
]

if not FONT_CANDIDATES:
    all_ttfs = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    FONT_CANDIDATES = all_ttfs if all_ttfs else ["arial.ttf"]


def generate_single_sample(args):
    idx, text, font_path, board_type, ann_class, subject = args
    font_size = random.randint(26, 36)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    lines = text.split("\n")
    num_lines = len(lines)

    # Measure multi-line text dimensions
    dummy_img = Image.new("L", (1, 1), 0)
    dummy_draw = ImageDraw.Draw(dummy_img)

    line_sizes = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font)
        line_w = max(20, bbox[2] - bbox[0])
        line_h = max(20, bbox[3] - bbox[1])
        line_sizes.append((line_w, line_h))

    max_line_w = max(w for w, _ in line_sizes)
    line_h = max(h for _, h in line_sizes)
    line_spacing = int(line_h * 1.35)

    margin_x = random.randint(20, 40)
    margin_y = random.randint(14, 25)

    target_width = min(512, max(80, max_line_w + margin_x * 2))
    target_height = min(180, max(44, (num_lines * line_spacing) + margin_y * 2))

    # 1. Background Generation
    if board_type == "green_chalkboard":
        b_base = random.randint(35, 55)
        g_base = random.randint(65, 95)
        r_base = random.randint(45, 70)
        bg = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        bg[:, :, 0] = b_base
        bg[:, :, 1] = g_base
        bg[:, :, 2] = r_base

        noise = np.random.normal(0, random.uniform(3.0, 5.0), bg.shape).astype(np.float32)
        bg = np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # Chalk haze and dust
        for _ in range(random.randint(1, 2)):
            cx, cy = random.randint(0, target_width), random.randint(0, target_height)
            rx, ry = random.randint(20, 120), random.randint(10, 40)
            dust = np.zeros((target_height, target_width), dtype=np.float32)
            cv2.ellipse(dust, (cx, cy), (rx, ry), random.randint(-40, 40), 0, 360, random.uniform(4, 12), -1)
            dust = cv2.GaussianBlur(dust, (21, 13), 0)
            bg = np.clip(bg.astype(np.float32) + dust[:, :, np.newaxis], 0, 255).astype(np.uint8)

    elif board_type == "black_slate":
        val = random.randint(28, 45)
        bg = np.full((target_height, target_width, 3), val, dtype=np.uint8)
        noise = np.random.normal(0, 3.5, bg.shape).astype(np.float32)
        bg = np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    else:  # Whiteboard
        w_val = random.randint(235, 250)
        bg = np.full((target_height, target_width, 3), w_val, dtype=np.uint8)
        noise = np.random.normal(0, 2.0, bg.shape).astype(np.float32)
        bg = np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # 2. Handwriting Rendering (Per-line support)
    mask = Image.new("L", (target_width, target_height), 0)
    draw = ImageDraw.Draw(mask)

    start_y = margin_y
    for l_idx, line in enumerate(lines):
        curr_x = margin_x
        curr_y = start_y + (l_idx * line_spacing)
        slope = random.uniform(-0.015, 0.015)

        for char in line:
            if char == " ":
                curr_x += int(font_size * random.uniform(0.3, 0.45))
                continue

            char_y = int(curr_y + (curr_x * slope) + random.uniform(-1.0, 1.0))
            c_mask = Image.new("L", (font_size * 2, font_size * 2), 0)
            c_draw = ImageDraw.Draw(c_mask)
            c_draw.text((4, 4), char, font=font, fill=255)

            rot_angle = random.uniform(-2.5, 2.5)
            c_mask = c_mask.rotate(rot_angle, resample=Image.BICUBIC)
            mask.paste(c_mask, (curr_x, char_y - 4), c_mask)

            bbox = draw.textbbox((0, 0), char, font=font)
            char_w = max(6, bbox[2] - bbox[0])
            curr_x += int(char_w + random.uniform(1.2, 3.5))
            if curr_x > target_width - 15:
                break

    mask_np = np.array(mask)

    # 3. Stroke Physics & Chalk / Marker Blending
    if board_type in ["green_chalkboard", "black_slate"]:
        chalk_color = random.choice([
            (225, 240, 250),
            (180, 225, 245),
            (215, 235, 245),
            (195, 230, 215),
        ])
        grain = np.random.uniform(0.74, 1.0, (target_height, target_width))
        chalk_dust = np.random.normal(0, 8, (target_height, target_width))
        chalk_alpha = np.clip((mask_np.astype(np.float32) / 255.0) * grain + (chalk_dust / 255.0), 0.0, 1.0)
        bloom = cv2.GaussianBlur(chalk_alpha, (5, 5), 0.8) * 0.12
        total_alpha = np.clip(chalk_alpha + bloom, 0.0, 1.0)[:, :, np.newaxis]

        chalk_layer = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            chalk_layer[:, :, c] = chalk_color[c]
        final_img = (bg.astype(np.float32) * (1.0 - total_alpha) + chalk_layer * total_alpha).astype(np.uint8)
    else:  # Whiteboard
        marker_color = random.choice([
            (30, 28, 25),
            (140, 50, 25),
            (30, 25, 145),
            (35, 110, 30),
        ])
        marker_alpha = (cv2.GaussianBlur(mask_np, (3, 3), 0.6).astype(np.float32) / 255.0)[:, :, np.newaxis]
        marker_layer = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            marker_layer[:, :, c] = marker_color[c]
        final_img = (bg.astype(np.float32) * (1.0 - marker_alpha) + marker_layer * marker_alpha).astype(np.uint8)

    final_img = cv2.GaussianBlur(final_img, (3, 3), 0.25)

    img_id = f"GEN_{idx:05d}"
    filename = f"{img_id}_{board_type}.jpg"
    img_path = os.path.join(IMAGES_DIR, filename)
    cv2.imwrite(img_path, final_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    return {
        "image_id": img_id,
        "image_path": f"images/{filename}",
        "text": text,
        "class": ann_class,
        "subject": subject,
        "board_type": "Chalkboard" if "chalkboard" in board_type or "slate" in board_type else "Whiteboard",
        "writer_id": f"teacher_gen_{idx % 16 + 1}",
    }


def main(total_count=30000):
    print("=" * 65)
    print(f"  ECHD UNIVERSAL DATASET GENERATOR: Generating {total_count:,} Images")
    print("  Subjects: English, Mathematics, Physics, Chemistry")
    print("  Formats: Single words, full sentences, multi-line formulas")
    print("=" * 65)

    board_types = ["green_chalkboard", "black_slate", "whiteboard"]
    board_weights = [0.55, 0.25, 0.20]

    all_tasks = []
    for idx in range(total_count):
        dice = random.random()
        if dice < 0.28:
            # English (words, phrases, sentences)
            text = random.choice(ENGLISH_VOCAB)
            ann_class = "Text"
            subject = "English"
        elif dice < 0.53:
            # Mathematics
            text = random.choice(MATH_VOCAB)
            ann_class = "Equation"
            subject = "Mathematics"
        elif dice < 0.73:
            # Physics
            text = random.choice(PHYSICS_VOCAB)
            ann_class = "Equation"
            subject = "Physics"
        elif dice < 0.88:
            # Chemistry
            text = random.choice(CHEMISTRY_VOCAB)
            ann_class = "Equation"
            subject = "Chemistry"
        else:
            # Multi-line formula or derivation
            text, ann_class, subject = random.choice(MULTILINE_VOCAB)

        font_path = random.choice(FONT_CANDIDATES)
        board_type = random.choices(board_types, weights=board_weights)[0]
        all_tasks.append((idx, text, font_path, board_type, ann_class, subject))

    results = []
    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) * 2)) as executor:
        futures = {executor.submit(generate_single_sample, task): task for task in all_tasks}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Synthesizing"):
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                pass

    results.sort(key=lambda x: x["image_id"])
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[DONE] Generated {len(results):,} images in '{IMAGES_DIR}'.")
    print(f"Manifest written to '{MANIFEST_PATH}'.")


if __name__ == "__main__":
    count = 30000
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            pass
    main(total_count=count)
