import base64
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import numpy as np
import cv2
import string
import tensorflow as tf
import os
from dotenv import load_dotenv
load_dotenv()

# ------------------------- إعداد نموذج TFLite -------------------------
CHARS = string.ascii_lowercase + string.ascii_uppercase + string.digits
IDX2CHAR = {i: c for i, c in enumerate(CHARS)}
IMG_W, IMG_H = 300, 50

interpreter = tf.lite.Interpreter(model_path=r"captcha_model.tflite")
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

def preprocess_image_bytes(img_bytes):
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (IMG_W, IMG_H))
    img = img.astype("float32") / 255.0
    img = np.expand_dims(img, axis=(0,-1))
    return img

def حل_كابتشا_نموذج_جديد(style_attribute):
    base64_match = re.search(r"base64,(.*?)['\"]", style_attribute)
    if not base64_match:
        return None
    img_bytes = base64.b64decode(base64_match.group(1))
    img = preprocess_image_bytes(img_bytes)
    interpreter.set_tensor(input_details[0]['index'], img)
    interpreter.invoke()
    y_pred = interpreter.get_tensor(output_details[0]['index'])
    
    input_len = np.ones(y_pred.shape[0]) * y_pred.shape[1]
    decoded, _ = tf.keras.backend.ctc_decode(y_pred, input_length=input_len, greedy=True)
    out = decoded[0][0].numpy().flatten()
    out = [int(c) for c in out if c >= 0 and c < len(CHARS)]
    return "".join([IDX2CHAR[i] for i in out])


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_photo(photo_path, caption="تم الحجز بنجاح!"):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo_file:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": photo_file})

# ------------------------- فتح المتصفح -------------------------
def فتح_متصفح_بروفايل(profile_name):
    options = Options()
    options.add_argument("--start-maximized")
    options.page_load_strategy = 'eager'
    options.add_argument(r"--user-data-dir=C:\Users\user\AppData\Local\Google\Chrome\User Data\temp_" + profile_name.replace(" ", "_"))
    options.add_argument(f"--profile-directory={profile_name}")
    options.add_experimental_option("detach", True)
    return webdriver.Chrome(options=options)

def كتابة_بطيئة(input_elem, text, delay_per_char=0.3):
    driver = input_elem._parent
    driver.execute_script("arguments[0].value = '';", input_elem)
    for char in text:
        input_elem.send_keys(char)
        time.sleep(delay_per_char)

# ------------------------- حل الكابتشا الثانية + إرسال صورة الصفحة -------------------------
def مراقبة_وحل_الكابتشا_الثانية(driver, wait, profile_name):
    while True:
        try:
            style_attr = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[starts-with(@style, 'background:white url(')]")
            )).get_attribute("style")

            result = حل_كابتشا_نموذج_جديد(style_attr)
            if not result:
                continue

            input_elem = driver.find_element(By.CSS_SELECTOR, "#appointment_newAppointmentForm_captchaText")
            كتابة_بطيئة(input_elem, result, delay_per_char=0.5)

            time.sleep(1)
            submit_btn = driver.find_element(By.CSS_SELECTOR, "#appointment_newAppointmentForm_appointment_addAppointment")
            driver.execute_script("arguments[0].click();", submit_btn)
            time.sleep(2)

            errors = driver.find_elements(By.XPATH, "//*[contains(text(), 'Der eingegebene Text ist falsch')]")
            if errors:
                time.sleep(0.5)
                continue

            # حفظ صورة الصفحة بعد النجاح
            screenshot_path = f"{profile_name}_final_page.png"
            driver.save_screenshot(screenshot_path)

            # إرسال الصورة بصمت
            send_telegram_photo(screenshot_path)
            return True
        except:
            time.sleep(0.5)

# ------------------------- تشغيل البروفايل الأساسي -------------------------
def تشغيل_البروفايل_الأساسي():
    profile_name = "Default"  # ضع اسم البروفايل الأساسي هنا
    driver = فتح_متصفح_بروفايل(profile_name)
    wait = WebDriverWait(driver, 10, poll_frequency=0.1)
    driver.get("https://service2.diplo.de/rktermin/extern/appointment_showMonth.do?locationCode=riad&realmId=1267&categoryId=2936")
    مراقبة_وحل_الكابتشا_الثانية(driver, wait, profile_name)

# ------------------------- البداية -------------------------
تشغيل_البروفايل_الأساسي()