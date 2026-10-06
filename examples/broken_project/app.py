import os

import yaml
from PIL import Image

url = os.environ["WORKSFORME_DEMO_DATABASE_URL"]
image = Image.new("RGB", (1, 1))
config = yaml.safe_load("enabled: true")
