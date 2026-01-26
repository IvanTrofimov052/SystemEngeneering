import os
import time
import uuid

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


DEFAULT_TIMEOUT = 15
CREATE_TIMEOUT = 25


def _base_url() -> str:
    value = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    return value.rstrip("/")


def _build_driver() -> webdriver.Chrome:
    browser = os.getenv("BROWSER", "chrome").lower()
    headless = os.getenv("HEADLESS", "1") != "0"

    if browser != "chrome":
        raise RuntimeError("Only chrome browser is supported in these tests.")

    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    service = ChromeService(chromedriver_path) if chromedriver_path else ChromeService()

    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(0)
    return driver


@pytest.fixture()
def driver():
    driver = _build_driver()
    try:
        yield driver
    finally:
        driver.quit()


def _wait(driver, condition, timeout=DEFAULT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(condition)


def _send_keys_retry(driver, css_selector: str, text: str, attempts: int = 3):
    for _ in range(attempts):
        try:
            element = driver.find_element(By.CSS_SELECTOR, css_selector)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            if not element.is_displayed() or not element.is_enabled():
                time.sleep(0.2)
                continue
            try:
                element.click()
            except Exception:
                pass
            element.send_keys(text)
            return
        except StaleElementReferenceException:
            time.sleep(0.2)
    # Fallback: set value via JS and dispatch input event
    element = driver.find_element(By.CSS_SELECTOR, css_selector)
    driver.execute_script(
        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
        element,
        text,
    )


def _register(driver, name: str, email: str, password: str):
    base_url = _base_url()
    driver.get(f"{base_url}/register")
    _wait(driver, EC.presence_of_element_located((By.ID, "registerForm")))
    driver.find_element(By.NAME, "name").send_keys(name)
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "#registerForm button").click()
    _wait(driver, EC.url_to_be(f"{base_url}/"))
    _wait(driver, EC.visibility_of_element_located((By.ID, "logoutBtn")))


def _login(driver, email: str, password: str):
    base_url = _base_url()
    driver.get(f"{base_url}/login")
    _wait(driver, EC.presence_of_element_located((By.ID, "loginForm")))
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "#loginForm button").click()
    _wait(driver, EC.url_to_be(f"{base_url}/"))
    _wait(driver, EC.visibility_of_element_located((By.ID, "logoutBtn")))


def _create_post(driver, text: str):
    base_url = _base_url()
    _wait(driver, EC.element_to_be_clickable((By.ID, "newPostLink"))).click()
    _wait(driver, EC.url_to_be(f"{base_url}/posts/new"))
    _wait(driver, EC.presence_of_element_located((By.ID, "editorForm")))
    _wait(
        driver,
        lambda d: "active"
        in d.find_element(By.ID, "sessionStatus").get_attribute("class"),
    )
    driver.find_element(By.NAME, "text").send_keys(text)
    save_btn = driver.find_element(By.ID, "saveBtn")
    driver.execute_script(
        "const el = document.querySelector(\"input[name='image']\"); if (el) el.disabled = true;"
    )
    driver.execute_script(
        "document.getElementById('editorForm').dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}));"
    )
    _wait(
        driver,
        lambda d: save_btn.get_attribute("disabled")
        or "/post/" in d.current_url
        or d.current_url.rstrip("/") == base_url,
    )

    def _post_created(drv):
        url = drv.current_url
        if "/post/" in url:
            return "post"
        if url.rstrip("/") == base_url:
            try:
                drv.find_element(
                    By.XPATH,
                    f"//article[contains(@class,'feed-item')][.//*[contains(text(), '{text}')]]",
                )
                return "feed"
            except Exception:
                return False
        return False

    try:
        result = _wait(driver, _post_created, timeout=CREATE_TIMEOUT)
    except TimeoutException:
        toast_text = ""
        try:
            toast_text = driver.find_element(By.ID, "toast").text.strip()
        except Exception:
            pass
        raise AssertionError(
            f"Post creation timeout. url={driver.current_url} toast={toast_text}"
        ) from None
    if result == "post":
        _wait(driver, EC.presence_of_element_located((By.ID, "detail")))
        _wait(driver, lambda d: text in d.find_element(By.ID, "detail").text)
        return

    driver.get(f"{base_url}/")
    _wait(driver, EC.presence_of_element_located((By.ID, "feed")))
    driver.find_element(
        By.XPATH,
        f"//article[contains(@class,'feed-item')][.//*[contains(text(), '{text}')]]//*[@data-open]",
    ).click()
    _wait(driver, EC.presence_of_element_located((By.ID, "detail")))
    _wait(driver, lambda d: text in d.find_element(By.ID, "detail").text)


def _unique_email() -> str:
    return f"selenium-{uuid.uuid4().hex[:8]}@example.com"


def _unique_post_text() -> str:
    return f"selenium-post-{uuid.uuid4().hex[:8]}"


def _unique_comment_text() -> str:
    return f"selenium-comment-{uuid.uuid4().hex[:8]}"


def test_register_login_logout(driver):
    name = "Test User"
    email = _unique_email()
    password = "password123"

    _register(driver, name, email, password)

    profile_text = driver.find_element(By.ID, "profileBox").text
    assert name in profile_text
    assert email in profile_text

    driver.find_element(By.ID, "logoutBtn").click()
    _wait(driver, EC.invisibility_of_element_located((By.ID, "logoutBtn")))
    assert driver.find_element(By.ID, "loginLink").is_displayed()
    assert driver.find_element(By.ID, "registerLink").is_displayed()

    _login(driver, email, password)
    session_text = driver.find_element(By.ID, "sessionStatus").text
    assert email in session_text


def test_create_post_and_delete(driver):
    name = "Test User"
    email = _unique_email()
    password = "password123"

    _register(driver, name, email, password)

    post_text = _unique_post_text()
    _create_post(driver, post_text)

    delete_btn = _wait(driver, EC.element_to_be_clickable((By.ID, "deletePost")))
    delete_btn.click()
    _wait(driver, EC.alert_is_present())
    driver.switch_to.alert.accept()

    _wait(driver, EC.invisibility_of_element_located((By.ID, "closeDetail")))
    _wait(driver, lambda d: post_text not in d.find_element(By.ID, "detail").text)


def test_like_and_comment(driver):
    name = "Test User"
    email = _unique_email()
    password = "password123"

    _register(driver, name, email, password)

    post_text = _unique_post_text()
    _create_post(driver, post_text)

    base_url = _base_url()
    driver.get(f"{base_url}/")
    _wait(driver, EC.presence_of_element_located((By.ID, "feed")))

    feed_item = _wait(
        driver,
        lambda d: d.find_element(
            By.XPATH,
            f"//article[contains(@class,'feed-item')][.//*[contains(text(), '{post_text}')]]",
        ),
    )

    like_btn = feed_item.find_element(By.CSS_SELECTOR, "[data-like-toggle]")
    like_btn.click()
    _wait(
        driver,
        lambda d: "is-liked"
        in d.find_element(
            By.XPATH,
            f"//article[contains(@class,'feed-item')][.//*[contains(text(), '{post_text}')]]//*[@data-like-toggle]",
        ).get_attribute("class"),
    )

    driver.find_element(
        By.XPATH,
        f"//article[contains(@class,'feed-item')][.//*[contains(text(), '{post_text}')]]//*[@data-open]",
    ).click()
    _wait(driver, EC.presence_of_element_located((By.ID, "commentForm")))

    comment_text = _unique_comment_text()
    _wait(driver, EC.presence_of_element_located((By.CSS_SELECTOR, "#commentForm textarea[name='text']")))
    _send_keys_retry(driver, "#commentForm textarea[name='text']", comment_text)
    driver.find_element(By.CSS_SELECTOR, "#commentForm button").click()

    _wait(
        driver,
        lambda d: d.find_element(
            By.XPATH,
            f"//div[contains(@class,'comment')][.//*[contains(text(), '{comment_text}')]]",
        ),
    )
