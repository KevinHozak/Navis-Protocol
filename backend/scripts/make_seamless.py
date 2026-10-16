import sys
from PIL import Image, ImageOps


def make_kaleidoscope_seamless(input_path, output_path):
    img = Image.open(input_path).convert("RGBA")
    w, h = img.size

    # Half size
    half_w, half_h = w // 2, h // 2
    img_half = img.resize((half_w, half_h), Image.LANCZOS)

    # Create the 4 quadrants
    top_left = img_half
    top_right = ImageOps.mirror(top_left)
    bottom_left = ImageOps.flip(top_left)
    bottom_right = ImageOps.mirror(bottom_left)

    seamless = Image.new("RGBA", (w, h))
    seamless.paste(top_left, (0, 0))
    seamless.paste(top_right, (half_w, 0))
    seamless.paste(bottom_left, (0, half_h))
    seamless.paste(bottom_right, (half_w, half_h))

    seamless.save(output_path)
    print(f"✅ Created perfectly seamless mirrored texture at {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python make_seamless.py <input> <output>")
        sys.exit(1)
    make_kaleidoscope_seamless(sys.argv[1], sys.argv[2])
