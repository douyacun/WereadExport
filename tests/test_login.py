import os
from pathlib import Path
import tempfile
import unittest
from urllib.parse import quote

from selenium.webdriver import Chrome, ChromeOptions

from weread_export.login import is_logged_in, save_login_qrcode


IMAGE = 'data:image/svg+xml,' + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    '<rect width="100" height="100" fill="black"/></svg>')


@unittest.skipUnless(os.environ.get('WEREAD_BROWSER_TESTS') == '1', '需启用本地 Chrome 测试')
class LoginBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = ChromeOptions()
        options.add_argument('--headless=new')
        cls.driver = Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_current_login_link_and_qr(self):
        # The other header action must never be mistaken for the login link.
        html = '<meta charset="utf-8"><div class="menu_container" style="display:none">menu</div>'
        html += '<a class="wr_index_page_top_section_header_action_link" onclick="throw Error()">传书到手机</a>'
        html += '<a class="wr_index_page_top_section_header_action_link" onclick="document.querySelector(\'section\').style.display=\'block\'">登录</a>'
        html += f'<section class="wr_login_modal_qr_wrapper" style="display:none"><img src="{IMAGE}"></section>'
        self.driver.get('data:text/html;charset=utf-8,' + quote(html))
        self.assertFalse(is_logged_in(self.driver))
        with tempfile.TemporaryDirectory() as directory:
            path = save_login_qrcode(self.driver, Path(directory) / 'qr.png', timeout=3)
            self.assertGreater(path.stat().st_size, 0)

    def test_legacy_login_and_visible_menu(self):
        html = '<meta charset="utf-8"><button class="navBar_link_Login" onclick="document.querySelector(\'section\').style.display=\'block\'">登录</button>'
        html += f'<section class="login_dialog_qrcode" style="display:none"><img src="{IMAGE}"></section>'
        html += '<div class="menu_container" style="display:none">menu</div>'
        self.driver.get('data:text/html;charset=utf-8,' + quote(html))
        with tempfile.TemporaryDirectory() as directory:
            save_login_qrcode(self.driver, Path(directory) / 'qr.png', timeout=3)
        self.driver.execute_script("document.querySelector('.menu_container').style.display='block'")
        self.assertTrue(is_logged_in(self.driver))

    def test_iframe_qrcode(self):
        frame = f'<img class="qrcode" src="{IMAGE}">'
        frame_url = 'data:text/html;charset=utf-8,' + quote(frame)
        html = '<meta charset="utf-8"><a onclick="document.querySelector(\'section\').style.display=\'block\'">登录</a>'
        html += f'<section class="login_qrcode_container" style="display:none"><iframe src="{frame_url}"></iframe></section>'
        self.driver.get('data:text/html;charset=utf-8,' + quote(html))
        with tempfile.TemporaryDirectory() as directory:
            save_login_qrcode(self.driver, Path(directory) / 'qr.png', timeout=3)
        self.assertTrue(self.driver.execute_script('return window === window.top'))

    def test_click_retried_until_page_handler_is_ready(self):
        html = '<meta charset="utf-8"><script>let attempts=0;</script>'
        html += '<a onclick="if (++attempts > 1) document.querySelector(\'section\').style.display=\'block\'">登录</a>'
        html += f'<section class="wr_login_modal_qr_wrapper" style="display:none"><img src="{IMAGE}"></section>'
        self.driver.get('data:text/html;charset=utf-8,' + quote(html))
        with tempfile.TemporaryDirectory() as directory:
            save_login_qrcode(self.driver, Path(directory) / 'qr.png', timeout=4)
        self.assertEqual(self.driver.execute_script('return attempts'), 2)


if __name__ == '__main__':
    unittest.main()
