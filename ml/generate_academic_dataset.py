"""
ml/generate_academic_dataset.py
Large-scale, ultra-realistic synthetic classroom handwriting dataset generator:
- 4 Core Subjects: English, Mathematics, Physics, Chemistry + Classroom Metadata
- Authentic Board Physics: Green Chalkboard, Black Slate, Whiteboard
- Human handwriting dynamics: per-letter jitter, baseline drift, stroke pressure, chalk dust, eraser ghosts
"""

import os
import sys
import json
import glob
import random
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

DATASET_DIR = os.path.join(REPO_ROOT, "dataset_cache")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
MANIFEST_PATH = os.path.join(DATASET_DIR, "manifest.json")

os.makedirs(IMAGES_DIR, exist_ok=True)

# -------------------------------------------------------------
# Curated Academic Corpora (English, Math, Physics, Chemistry)
# -------------------------------------------------------------

ENGLISH_CORPUS = [
    "Active Voice and Passive Voice", "Direct and Indirect Speech", "Present Continuous Tense",
    "Subject Verb Agreement", "Noun Phrase and Verb Phrase", "Summary of Chapter 3",
    "The protagonist shows great courage", "Explain the central theme of the poem",
    "Synonyms: Rapid, Swift, Quick, Fast", "Antonyms: Expand and Contract",
    "Reading Comprehension: Passage 2", "Write a formal letter to the editor",
    "Identify the figure of speech: Metaphor", "Irony in the opening paragraph",
    "Lohith submitted the English assignment", "Eshwar answered question number four",
    "Ramesh completed the essay on time", "Sathvic read the Shakespeare sonnet",
    "Vocabulary: Ephemeral, Resilient, Candid", "Class Discussion: Modern Poetry",
    "Homework: Complete Exercise 4.2", "Review questions for mid term exam",
    "The cat sat on the mat", "She walked to the library yesterday",
    "He has been studying since morning", "They will arrive tomorrow afternoon",
    "Although it was raining, we played", "Neither Ramesh nor Eshwar was absent",
    "To be or not to be that is the question", "Knowledge is power in modern era",
    "Action speaks louder than words", "Practice makes a person perfect",
    "Chapter 1: The Portrait of a Lady", "Poem: The Road Not Taken by Robert Frost",
    "Notice: Annual Sports Day next week", "Grammar Rule: Use of articles A, An, The",
    "Prepositions of Time: At, On, In", "Conjunctions: Because, Although, Since",
    "Reported Speech Rules and Examples", "Degrees of Comparison: Positive, Comparative, Superlative"
]

MATH_CORPUS = [
    "(a + b)^2 = a^2 + 2ab + b^2", "(a - b)^2 = a^2 - 2ab + b^2", "a^2 - b^2 = (a - b)(a + b)",
    "(a + b + c)^2 = a^2 + b^2 + c^2 + 2ab + 2bc + 2ca", "(x + a)(x + b) = x^2 + (a+b)x + ab",
    "sin^2(x) + cos^2(x) = 1", "1 + tan^2(theta) = sec^2(theta)", "1 + cot^2(theta) = cosec^2(theta)",
    "tan(theta) = sin(theta) / cos(theta)", "sin(2x) = 2 sin(x) cos(x)", "cos(2x) = cos^2(x) - sin^2(x)",
    "dy/dx = 2x + 5", "dy/dx of sin(x) = cos(x)", "dy/dx of cos(x) = -sin(x)", "dy/dx of e^x = e^x",
    "Integral of x^n dx = x^(n+1)/(n+1) + C", "Integral of 1/x dx = ln|x| + C", "Integral of cos(x) dx = sin(x) + C",
    "lim x->0 (sin x / x) = 1", "lim x->0 (e^x - 1)/x = 1", "y = mx + c (Slope Intercept Form)",
    "Ax + By + C = 0", "x/a + y/b = 1 (Intercept Form)", "d = sqrt((x2 - x1)^2 + (y2 - y1)^2)",
    "x = (-b +- sqrt(b^2 - 4ac)) / (2a)", "Discriminant D = b^2 - 4ac", "Area of Triangle = 1/2 * base * height",
    "Area of Circle = pi * r^2", "Circumference = 2 * pi * r", "Volume of Sphere = 4/3 * pi * r^3",
    "det(A) = ad - bc", "Matrix A * A^-1 = Identity Matrix I", "P(A or B) = P(A) + P(B) - P(A and B)",
    "Mean = Sum of x_i / N", "Variance sigma^2 = Sum(x - mu)^2 / N", "Standard Deviation sigma = sqrt(Variance)",
    "Pythagoras Theorem: a^2 + b^2 = c^2", "Log(xy) = Log(x) + Log(y)", "Log(x/y) = Log(x) - Log(y)",
    "e^(i * pi) + 1 = 0", "Arithmetic Progression: T_n = a + (n-1)d", "Geometric Progression: S_n = a(r^n - 1)/(r - 1)"
]

PHYSICS_CORPUS = [
    "F = m * a (Newton Second Law)", "v = u + a * t", "s = u * t + 0.5 * a * t^2", "v^2 = u^2 + 2 * a * s",
    "p = m * v (Linear Momentum)", "Impulse J = F * delta_t = delta_p", "Kinetic Energy = 1/2 * m * v^2",
    "Potential Energy = m * g * h", "Work Done W = F * d * cos(theta)", "Power P = Work / Time = F * v",
    "F = G * (m1 * m2) / r^2", "Acceleration due to gravity g = 9.8 m/s^2", "T = 2 * pi * sqrt(L / g)",
    "Ohm's Law: V = I * R", "Electrical Power P = V * I = I^2 * R = V^2 / R", "Equivalent Resistance Series: R1 + R2 + R3",
    "Parallel Resistance: 1/R = 1/R1 + 1/R2", "Capacitance C = Q / V", "Energy stored in Capacitor U = 1/2 C V^2",
    "Magnetic Force F = q * (v x B)", "Force on current wire F = I * L * B * sin(theta)", "Faraday Law: emf = - d(Phi)/dt",
    "Speed of Light c = 3 x 10^8 m/s", "Refraction Snell's Law: n1 sin(i) = n2 sin(r)", "Lens Formula: 1/f = 1/v - 1/u",
    "Mirror Formula: 1/f = 1/v + 1/u", "Magnification m = -v / u", "First Law of Thermodynamics: delta_Q = delta_U + W",
    "Ideal Gas Equation: P * V = n * R * T", "Pressure P = Force / Area", "Density rho = Mass / Volume",
    "Bernoulli Equation: P + 1/2 rho v^2 + rho g h = const", "Frequency f = 1 / Time Period T", "Wave Speed v = f * lambda",
    "Planck Equation: E = h * nu", "Einstein Mass Energy: E = m * c^2", "de Broglie Wavelength: lambda = h / p"
]

CHEMISTRY_CORPUS = [
    "2 H2 + O2 -> 2 H2O", "CH4 + 2 O2 -> CO2 + 2 H2O", "HCl + NaOH -> NaCl + H2O", "CaCO3 -> CaO + CO2",
    "2 Na + 2 H2O -> 2 NaOH + H2", "N2 + 3 H2 -> 2 NH3 (Haber Process)", "Photosynthesis: 6 CO2 + 6 H2O -> C6H12O6 + 6 O2",
    "Respiration: C6H12O6 + 6 O2 -> 6 CO2 + 6 H2O", "Fe + CuSO4 -> FeSO4 + Cu (Displacement)",
    "2 KClO3 -> 2 KCl + 3 O2", "Zn + 2 HCl -> ZnCl2 + H2", "pH = -log10[H+]", "pOH = -log10[OH-]",
    "pH + pOH = 14 at 25 deg C", "Avogadro Number N_A = 6.022 x 10^23", "Molarity M = moles of solute / Liters of solution",
    "Molality m = moles of solute / kg of solvent", "Boyle's Law: P1 * V1 = P2 * V2", "Charles's Law: V1 / T1 = V2 / T2",
    "General Gas Constant R = 8.314 J/(mol K)", "Oxidation is Loss of electrons (OIL)", "Reduction is Gain of electrons (RIG)",
    "Anode: Oxidation reaction", "Cathode: Reduction reaction", "Electrochemical Cell: Zn | Zn2+ || Cu2+ | Cu",
    "Functional Groups: -OH (Alcohol), -CHO (Aldehyde)", "-COOH (Carboxylic Acid), -NH2 (Amine)",
    "Alkanes: C_n H_(2n+2)", "Alkenes: C_n H_(2n)", "Alkynes: C_n H_(2n-2)", "Benzene Formula: C6H6",
    "Esterification: Acid + Alcohol -> Ester + Water", "Periodic Trend: Electronegativity increases across period",
    "Atomic Radius decreases across period", "Ionization Energy increases left to right", "Valency of Carbon = 4 (Tetravalent)"
]

SUBJECT_MAP = {
    "English": (ENGLISH_CORPUS, "Text"),
    "Mathematics": (MATH_CORPUS, "Equation"),
    "Physics": (PHYSICS_CORPUS, "Equation"),
    "Chemistry": (CHEMISTRY_CORPUS, "Equation"),
}

FONT_CANDIDATES = [
    f for f in glob.glob("C:/Windows/Fonts/*.ttf")
    if any(k in f.lower() for k in [
        'inkfree', 'lhandw', 'segoesc', 'segoepr', 'mistral', 
        'mvboli', 'brushsci', 'freescpt', 'rage', 'scriptbl', 'comic', 'forte'
    ])
]
if not FONT_CANDIDATES:
    FONT_CANDIDATES = ["arial.ttf"]


def generate_single_sample(args):
    idx, subject, text, ann_class, font_path, board_type = args
    font_size = random.randint(28, 38)
    target_width = 480
    target_height = 96

    # 1. Background Generation
    if board_type == "green_chalkboard":
        # Green blackboard base
        b_base = random.randint(35, 52)
        g_base = random.randint(65, 92)
        r_base = random.randint(45, 68)
        bg = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        bg[:, :, 0] = b_base
        bg[:, :, 1] = g_base
        bg[:, :, 2] = r_base

        # Slate grain
        noise = np.random.normal(0, random.uniform(3.5, 6.0), bg.shape).astype(np.float32)
        bg = np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # Chalk haze and eraser streaks
        for _ in range(random.randint(1, 3)):
            cx, cy = random.randint(0, target_width), random.randint(0, target_height)
            rx, ry = random.randint(30, 200), random.randint(10, 50)
            dust = np.zeros((target_height, target_width), dtype=np.float32)
            cv2.ellipse(dust, (cx, cy), (rx, ry), random.randint(-40, 40), 0, 360, random.uniform(6, 18), -1)
            dust = cv2.GaussianBlur(dust, (25, 15), 0)
            bg = np.clip(bg.astype(np.float32) + dust[:, :, np.newaxis], 0, 255).astype(np.uint8)

        # Classroom lighting gradient
        grad = np.linspace(random.uniform(0.85, 1.0), random.uniform(1.0, 1.15), target_width)
        bg = np.clip(bg.astype(np.float32) * grad[np.newaxis, :, np.newaxis], 0, 255).astype(np.uint8)

    elif board_type == "black_slate":
        val = random.randint(25, 40)
        bg = np.full((target_height, target_width, 3), val, dtype=np.uint8)
        noise = np.random.normal(0, 4.0, bg.shape).astype(np.float32)
        bg = np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    else:  # Whiteboard
        w_val = random.randint(232, 248)
        bg = np.full((target_height, target_width, 3), w_val, dtype=np.uint8)
        noise = np.random.normal(0, 2.0, bg.shape).astype(np.float32)
        bg = np.clip(bg.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # 2. Handwriting Rendering
    font = ImageFont.truetype(font_path, font_size)
    mask = Image.new("L", (target_width, target_height), 0)
    draw = ImageDraw.Draw(mask)

    curr_x = random.randint(18, 35)
    base_y = target_height // 2 - font_size // 2 + random.randint(-4, 4)
    slope = random.uniform(-0.025, 0.025)

    for char in text:
        if char == " ":
            curr_x += int(font_size * random.uniform(0.32, 0.48))
            continue

        char_y = int(base_y + (curr_x * slope) + random.uniform(-1.8, 1.8))
        c_mask = Image.new("L", (font_size * 2, font_size * 2), 0)
        c_draw = ImageDraw.Draw(c_mask)
        c_draw.text((4, 4), char, font=font, fill=255)

        rot_angle = random.uniform(-3.5, 3.5)
        c_mask = c_mask.rotate(rot_angle, resample=Image.BICUBIC)
        mask.paste(c_mask, (curr_x, char_y - 4), c_mask)

        bbox = draw.textbbox((0, 0), char, font=font)
        char_w = max(8, bbox[2] - bbox[0])
        curr_x += int(char_w + random.uniform(1.5, 4.5))
        if curr_x > target_width - 30:
            break

    mask_np = np.array(mask)

    # 3. Stroke Physics & Chalk/Marker Blending
    if board_type in ["green_chalkboard", "black_slate"]:
        chalk_color = random.choice([
            (160, 230, 245),  # Pale yellow chalk
            (215, 235, 245),  # Off-white chalk
            (180, 215, 240),  # Soft warm chalk
            (225, 240, 250),  # Bright white chalk
        ])
        grain = np.random.uniform(0.70, 1.0, (target_height, target_width))
        chalk_dust = np.random.normal(0, 14, (target_height, target_width))
        chalk_alpha = np.clip((mask_np.astype(np.float32) / 255.0) * grain + (chalk_dust / 255.0), 0.0, 1.0)
        bloom = cv2.GaussianBlur(chalk_alpha, (5, 5), 1.0) * 0.2
        total_alpha = np.clip(chalk_alpha + bloom, 0.0, 1.0)[:, :, np.newaxis]

        chalk_layer = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            chalk_layer[:, :, c] = chalk_color[c]
        final_img = (bg.astype(np.float32) * (1.0 - total_alpha) + chalk_layer * total_alpha).astype(np.uint8)
    else:  # Whiteboard
        marker_color = random.choice([
            (35, 32, 30),    # Black dry erase
            (145, 55, 30),   # Blue marker
            (35, 28, 150),   # Red marker
            (38, 115, 32),   # Green marker
        ])
        marker_alpha = (cv2.GaussianBlur(mask_np, (3, 3), 0.7).astype(np.float32) / 255.0)[:, :, np.newaxis]
        marker_layer = np.zeros_like(bg, dtype=np.float32)
        for c in range(3):
            marker_layer[:, :, c] = marker_color[c]
        final_img = (bg.astype(np.float32) * (1.0 - marker_alpha) + marker_layer * marker_alpha).astype(np.uint8)

    # Slight camera defocus
    final_img = cv2.GaussianBlur(final_img, (3, 3), 0.35)

    # Save image
    img_id = f"SYNTH_{idx:05d}"
    filename = f"{img_id}_{subject.lower()}_{board_type}.jpg"
    img_path = os.path.join(IMAGES_DIR, filename)
    cv2.imwrite(img_path, final_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    return {
        "image_id": img_id,
        "image_path": f"images/{filename}",
        "text": text,
        "class": ann_class,
        "subject": subject,
        "board_type": "Chalkboard" if "chalkboard" in board_type or "slate" in board_type else "Whiteboard",
        "writer_id": f"teacher_synth_{idx % 12 + 1}",
    }


def main(total_count=4000):
    print("=" * 65)
    print(f"  ECHD ACADEMIC DATASET SYNTHESIZER: Generating {total_count:,} Images")
    print("  Subjects: English, Mathematics, Physics, Chemistry")
    print("=" * 65)

    # Load existing real samples if any
    existing_samples = []
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                existing_samples = json.load(f)
            # Filter to keep real non-synthetic samples
            existing_samples = [s for s in existing_samples if not s.get("image_id", "").startswith("SYNTH_")]
        except Exception:
            existing_samples = []

    print(f"Retained {len(existing_samples)} original real dataset samples.")

    # Prepare generator tasks
    subjects = ["English", "Mathematics", "Physics", "Chemistry"]
    board_types = ["green_chalkboard", "green_chalkboard", "black_slate", "whiteboard"]

    tasks = []
    for i in range(1, total_count + 1):
        subj = random.choice(subjects)
        corpus, ann_class = SUBJECT_MAP[subj]
        base_text = random.choice(corpus)

        # Randomize variations: numbers, variables, question tags
        if subj in ["Mathematics", "Physics"] and random.random() < 0.4:
            num1 = random.randint(2, 25)
            num2 = random.randint(2, 10)
            text = f"{base_text} (Case {num1}.{num2})"
        elif subj == "English" and random.random() < 0.3:
            name = random.choice(["Lohith", "Eshwar", "Ramesh", "Sathvic", "Vishnu", "Priya", "Rahul"])
            text = f"{name}: {base_text}"
        else:
            text = base_text

        font_path = random.choice(FONT_CANDIDATES)
        board_type = random.choice(board_types)
        tasks.append((i, subj, text, ann_class, font_path, board_type))

    print(f"Generating {len(tasks)} samples using multithreading...")
    new_samples = []

    # Fast multithreading
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(generate_single_sample, t) for t in tasks]
        for f in tqdm(as_completed(futures), total=len(futures), desc="Synthesizing board frames"):
            new_samples.append(f.result())

    # Merge real + synthetic
    all_samples = existing_samples + sorted(new_samples, key=lambda x: x["image_id"])

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, indent=2)

    print("=" * 65)
    print(f"[SUCCESS] Dataset generation complete!")
    print(f"Total dataset size: {len(all_samples):,} annotated images")
    print(f"Manifest written to: {MANIFEST_PATH}")
    print("=" * 65)


if __name__ == "__main__":
    count = 4000
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            pass
    main(count)
