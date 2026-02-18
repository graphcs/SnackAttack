"""Quick test for background remover module."""
from PIL import Image
import io
from src.generators.background_remover import ensure_transparency

# Test: Already transparent image should be skipped (no API call)
img = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
px = img.load()
for y in range(15, 35):
    for x in range(15, 35):
        px[x, y] = (0, 0, 255, 255)
buf = io.BytesIO()
img.save(buf, format='PNG')
raw = buf.getvalue()
processed = ensure_transparency(raw)
assert processed == raw, 'Already-transparent image should be returned as-is'
print('Test PASSED: Already-transparent image skipped (no API call)')
print('Note: Full API test requires network access to api.rembg.com')
