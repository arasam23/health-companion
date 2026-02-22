import os
from PIL import Image, ImageDraw, ImageFont
from logger import extract_biometrics, log_biometrics

def create_dummy_biometrics_image(filename="dummy_test.jpg"):
    """Creates a simple image with text to test OCR/Vision extraction."""
    img = Image.new('RGB', (400, 300), color = (73, 109, 137))
    d = ImageDraw.Draw(img)
    text = "Weight: 185.5 lb\nBMI: 24.1\nBody Fat: 15.2%\nMetabolic Age: 30"
    try:
        # Use default font
        d.text((10,10), text, fill=(255,255,0))
    except:
        pass
    img.save(filename)
    return filename

if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") == "your_api_key_here":
        print("Please set your GEMINI_API_KEY in the .env file before running this test.")
        exit(1)

    print("Creating dummy image...")
    image_path = create_dummy_biometrics_image()
    
    print("Testing Biometrics Extraction via Gemini...")
    result = extract_biometrics(image_path)
    
    if result:
        print("\n--- Extracted Data ---")
        print(result.model_dump_json(indent=2))
        
        print("\nLogging to Database...")
        db_msg = log_biometrics(result)
        print(db_msg)
    else:
        print("Extraction failed.")

    # Cleanup
    if os.path.exists(image_path):
        os.remove(image_path)
