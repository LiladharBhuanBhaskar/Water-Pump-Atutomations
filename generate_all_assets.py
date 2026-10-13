import os
import numpy as np
from PIL import Image, ImageDraw
from collections import deque

# Paths
SRC_IMAGE = r"C:\Users\bhask\.gemini\antigravity-ide\brain\05feee0f-c0b2-490f-8d21-7e62892bd795\.user_uploaded\media_1791806774017.jpg"
RES_DIR = r"frontend\android\app\src\main\res"
PUBLIC_DIR = r"frontend\public"

def extract_badge(src_path):
    print("Extracting badge with alpha from source...")
    im = Image.open(src_path)
    arr = np.array(im, dtype=np.float32)
    h, w, _ = arr.shape
    dist_white = np.sqrt(np.sum((255.0 - arr)**2, axis=2))

    visited = np.zeros((h, w), dtype=bool)
    q = deque()
    for x, y in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1), (0, 10), (10, 0), (w-1, 10), (w-11, 0)]:
        visited[y, x] = True
        q.append((x, y))

    while q:
        x, y = q.popleft()
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                if dist_white[ny, nx] < 45.0:
                    visited[ny, nx] = True
                    q.append((nx, ny))

    alpha = np.full((h, w), 255, dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            if visited[y, x]:
                d = dist_white[y, x]
                if d < 10.0:
                    alpha[y, x] = 0
                else:
                    alpha[y, x] = int(np.clip((d - 10.0) / 35.0, 0.0, 1.0) * 255.0)

    rgb = arr.copy()
    for y in range(h):
        for x in range(w):
            if visited[y, x] and alpha[y, x] > 0:
                a = alpha[y, x] / 255.0
                rgb[y, x] = np.clip((rgb[y, x] - 255.0 * (1.0 - a)) / max(a, 0.01), 0, 255)

    rgba = np.dstack([rgb.astype(np.uint8), alpha])
    badge = Image.fromarray(rgba, "RGBA")
    return badge

def create_round_icon(badge):
    w, h = badge.size
    circle_mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(circle_mask)
    draw.ellipse((8, 8, w - 8, h - 8), fill=255)

    round_badge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bg_circle = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_circle)
    bg_draw.ellipse((8, 8, w - 8, h - 8), fill=(4, 28, 56, 255))
    round_badge.paste(bg_circle, (0, 0), circle_mask)

    scaled_badge = badge.resize((int(w * 0.94), int(h * 0.94)), Image.Resampling.LANCZOS)
    ox = (w - scaled_badge.width) // 2
    oy = (h - scaled_badge.height) // 2
    round_badge.paste(scaled_badge, (ox, oy), scaled_badge)

    final_round = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    final_round.paste(round_badge, (0, 0), circle_mask)
    return final_round

def create_foreground(badge, size):
    # Adaptive icon foreground: 108dp canvas, safe zone is inner 72dp circle (diameter 66.7%).
    # We place badge scaled to 72% so it fits safely inside any mask shape.
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    target_badge_size = int(size * 0.72)
    scaled = badge.resize((target_badge_size, target_badge_size), Image.Resampling.LANCZOS)
    offset = (size - target_badge_size) // 2
    canvas.paste(scaled, (offset, offset), scaled)
    return canvas

def create_splash_screen(badge, width, height):
    # Professional dark navy slate theme with radial glow
    splash = Image.new("RGBA", (width, height), (2, 6, 23, 255)) # #020617
    
    # Calculate optimal logo size
    is_portrait = height >= width
    if is_portrait:
        logo_dim = int(width * 0.44)
    else:
        logo_dim = int(height * 0.46)
    
    # Constrain to reasonable bounds
    logo_dim = max(min(logo_dim, 600), 96)
    
    scaled_badge = badge.resize((logo_dim, logo_dim), Image.Resampling.LANCZOS)
    ox = (width - logo_dim) // 2
    oy = (height - logo_dim) // 2
    
    # Subtle soft glow behind badge
    glow = Image.new("RGBA", (logo_dim + 60, logo_dim + 60), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((0, 0, logo_dim + 59, logo_dim + 59), fill=(14, 116, 144, 40)) # cyan glow
    
    splash.paste(glow, (ox - 30, oy - 30), glow)
    splash.paste(scaled_badge, (ox, oy), scaled_badge)
    return splash.convert("RGB")

def main():
    badge = extract_badge(SRC_IMAGE)
    round_badge = create_round_icon(badge)
    
    # Launcher icon densities (size in px)
    densities = {
        "mipmap-mdpi": {"launcher": 48, "foreground": 108},
        "mipmap-hdpi": {"launcher": 72, "foreground": 162},
        "mipmap-xhdpi": {"launcher": 96, "foreground": 216},
        "mipmap-xxhdpi": {"launcher": 144, "foreground": 324},
        "mipmap-xxxhdpi": {"launcher": 192, "foreground": 432},
    }

    print("Generating mipmap launcher icons...")
    for folder, dims in densities.items():
        folder_path = os.path.join(RES_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)
        
        # 1. Standard squircle launcher icon
        l_size = dims["launcher"]
        l_img = badge.resize((l_size, l_size), Image.Resampling.LANCZOS)
        l_img.save(os.path.join(folder_path, "ic_launcher.png"), "PNG")
        
        # 2. Round launcher icon
        r_img = round_badge.resize((l_size, l_size), Image.Resampling.LANCZOS)
        r_img.save(os.path.join(folder_path, "ic_launcher_round.png"), "PNG")
        
        # 3. Adaptive foreground icon
        f_size = dims["foreground"]
        f_img = create_foreground(badge, f_size)
        f_img.save(os.path.join(folder_path, "ic_launcher_foreground.png"), "PNG")
        
        print(f"  Generated {folder}: launcher {l_size}px, round {l_size}px, foreground {f_size}px")

    # Splash screen configurations
    splash_configs = [
        (os.path.join(RES_DIR, "drawable", "splash.png"), 480, 320),
        (os.path.join(RES_DIR, "drawable-port-mdpi", "splash.png"), 320, 480),
        (os.path.join(RES_DIR, "drawable-port-hdpi", "splash.png"), 480, 800),
        (os.path.join(RES_DIR, "drawable-port-xhdpi", "splash.png"), 720, 1280),
        (os.path.join(RES_DIR, "drawable-port-xxhdpi", "splash.png"), 960, 1600),
        (os.path.join(RES_DIR, "drawable-port-xxxhdpi", "splash.png"), 1280, 1920),
        (os.path.join(RES_DIR, "drawable-land-mdpi", "splash.png"), 480, 320),
        (os.path.join(RES_DIR, "drawable-land-hdpi", "splash.png"), 800, 480),
        (os.path.join(RES_DIR, "drawable-land-xhdpi", "splash.png"), 1280, 720),
        (os.path.join(RES_DIR, "drawable-land-xxhdpi", "splash.png"), 1600, 960),
        (os.path.join(RES_DIR, "drawable-land-xxxhdpi", "splash.png"), 1920, 1280),
    ]

    print("Generating splash screens...")
    for target_path, w, h in splash_configs:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        splash_img = create_splash_screen(badge, w, h)
        splash_img.save(target_path, "PNG")
        print(f"  Generated splash {target_path}: {w}x{h}")

    # Web & PWA assets for full consistency
    print("Generating web & public assets...")
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    badge.resize((512, 512), Image.Resampling.LANCZOS).save(os.path.join(PUBLIC_DIR, "icon-512.png"), "PNG")
    badge.resize((192, 192), Image.Resampling.LANCZOS).save(os.path.join(PUBLIC_DIR, "icon-192.png"), "PNG")
    badge.resize((64, 64), Image.Resampling.LANCZOS).save(os.path.join(PUBLIC_DIR, "favicon.ico"), "ICO")
    badge.resize((256, 256), Image.Resampling.LANCZOS).save(os.path.join(PUBLIC_DIR, "logo.png"), "PNG")
    print("All assets successfully generated!")

if __name__ == "__main__":
    main()
