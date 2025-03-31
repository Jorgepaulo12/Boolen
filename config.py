import os

# Configurações
COURSE_DIR = "courses"
os.makedirs(COURSE_DIR, exist_ok=True)
os.makedirs(os.path.join(COURSE_DIR, "covers"), exist_ok=True)
os.makedirs(os.path.join(COURSE_DIR, "files"), exist_ok=True) 