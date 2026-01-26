import os
import sys

try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image

def resize_icon():
    # Input/Output paths
    input_path = "assets/Gemini_Generated_Image_v1i03bv1i03bv1i0.png"
    output_path = "assets/adaptive_icon_fixed.png"

    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    print(f"Processing {input_path}...")
    
    img = Image.open(input_path).convert("RGBA")
    
    # 1. Sample background color (top-left pixel)
    # Convert tuple to int if necessary, but Pillow handles tuples fine
    bg_color = img.getpixel((0, 0))
    
    # If the image has alpha channel, we might want to ensure bg_color is solid
    # Assuming the user's image is the dark one generated previously
    
    # 2. Calculate new dimensions (60% scale)
    original_width, original_height = img.size
    scale_factor = 0.65
    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)
    
    # 3. Resize the original image
    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # 4. Create new canvas with background color
    # Use RGBA if original was RGBA
    final_img = Image.new("RGBA", (original_width, original_height), bg_color)
    
    # 5. Result position (center)
    x_offset = (original_width - new_width) // 2
    y_offset = (original_height - new_height) // 2
    
    final_img.paste(resized_img, (x_offset, y_offset), resized_img)
    
    final_img.save(output_path)
    print(f"Successfully saved to {output_path}")

if __name__ == "__main__":
    resize_icon()
