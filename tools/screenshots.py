"""Screenshot the demo page for the README (needs Chrome):

    python tools/screenshots.py

Starts the demo locally, runs both live cards, saves docs/images/demo_full.png."""
import sys
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web.app import create_app  # noqa: E402

OUT = ROOT / "docs" / "images"
PORT = 5055


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    server = make_server("127.0.0.1", PORT, create_app())
    threading.Thread(target=server.serve_forever, daemon=True).start()

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(f"http://127.0.0.1:{PORT}/")
        Select(driver.find_element(By.ID, "pages")).select_by_value("2")
        driver.find_element(By.ID, "books-run").click()
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#books-result table")))
        Select(driver.find_element(By.ID, "invoice")).select_by_value("pioneer")
        driver.find_element(By.ID, "invoice-run").click()
        WebDriverWait(driver, 90).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#invoice-result table")))
        height = driver.execute_script("return document.documentElement.scrollHeight")
        driver.set_window_size(1280, height + 200)   # window chrome eats part of the height
        driver.save_screenshot(str(OUT / "demo_full.png"))
    finally:
        driver.quit()
        server.shutdown()
    print("Saved", OUT / "demo_full.png")


if __name__ == "__main__":
    main()
