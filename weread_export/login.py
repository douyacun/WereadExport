"""Login selectors for both the current and legacy WeRead pages."""

from pathlib import Path
from time import monotonic
import logging

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.wait import WebDriverWait

logger = logging.getLogger(__name__)


def is_logged_in(driver):
    cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
    if cookies.get('wr_vid') and cookies.get('wr_skey'):
        return driver.execute_script("""
            return document.readyState === 'complete' && ![...document.querySelectorAll('a,button')].some(
                node => node.textContent.trim() === '登录' && node.getClientRects().length
                    && getComputedStyle(node).visibility !== 'hidden');
        """)
    return driver.execute_script("""
        return [...document.querySelectorAll('.menu_container')].some(
            node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');
    """)


def save_login_qrcode(driver, path, timeout=30):
    """Open the login dialog and save a loaded, visible QR image."""
    wait = WebDriverWait(driver, timeout)

    def login_button(d):
        return d.execute_script("""
            return [...document.querySelectorAll(
                'button.navBar_link_Login, .wr_index_page_top_section_header_action_link, a, button'
            )].find(node => node.textContent.trim() === '登录' && node.getClientRects().length
                && getComputedStyle(node).visibility !== 'hidden') || null;
        """)

    last_click = float('-inf')
    clicks = 0
    logger.info('正在查找微信读书登录入口…')

    def open_dialog(d):
        nonlocal last_click, clicks
        opened = d.execute_script("""return [...document.querySelectorAll(
            '.wr_login_modal_wrapper, .wr_login_modal_qr_wrapper, .login_dialog_qrcode, .login_qrcode_container'
        )].some(node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');""")
        if opened:
            return True
        # The server-rendered link can appear before Vue has attached its click
        # handler. Retry only while no login dialog is visible.
        button = login_button(d)
        if button and monotonic() - last_click >= 1:
            clicks += 1
            logger.info('点击登录入口（第 %s 次）', clicks)
            button.click()
            last_click = monotonic()
        return False

    try:
        wait.until(open_dialog)
        logger.info('登录弹窗已打开，正在加载二维码…')
    except TimeoutException as exc:
        raise RuntimeError('微信读书登录弹窗未打开，页面可能尚未加载完成或结构已变化') from exc

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def loaded_image(d, selector):
        return d.execute_script("""
            return [...document.querySelectorAll(arguments[0])].find(node =>
                node.complete && node.naturalWidth > 0 && node.getClientRects().length
                && getComputedStyle(node).visibility !== 'hidden') || null;
        """, selector)

    def save_image(d):
        try:
            image = loaded_image(d, '.login_dialog_qrcode img, .wr_login_modal_qr_wrapper img')
            if image:
                logger.debug('已找到页面内的二维码图片')
                return image.screenshot(str(path))
            frames = d.execute_script("""return [...document.querySelectorAll(
                '.login_qrcode_container iframe')].filter(node => node.getClientRects().length);""")
            for frame in frames:
                try:
                    d.switch_to.frame(frame)
                    image = loaded_image(d, 'img.qrcode, img.web_qrcode_img, .wrp_code img')
                    if image:
                        logger.debug('已找到微信登录 iframe 内的二维码图片')
                        return image.screenshot(str(path))
                finally:
                    d.switch_to.default_content()
        except StaleElementReferenceException:
            return False
        return False

    try:
        wait.until(save_image)
    except TimeoutException as exc:
        raise RuntimeError('登录二维码加载超时，请检查微信登录服务的网络连接或稍后重试') from exc
    return path
