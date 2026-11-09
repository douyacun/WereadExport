from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from weread_export.__main__ import main


class LoginCommandTest(unittest.TestCase):
    def test_visible_command_logs_in_and_closes_cleanly(self):
        driver = MagicMock()
        driver.window_handles = []
        reader = MagicMock()
        with patch('sys.argv', ['weread_export']), patch('weread_export.__main__.Chrome', return_value=driver), \
                patch('weread_export.WeRead') as create_reader:
            create_reader.return_value.__enter__.return_value = reader
            main()
        reader.login.assert_called_once_with(wait_turns=180, show_qrcode=False)
        driver.quit.assert_called_once()

    def test_export_reuses_visible_login_profile(self):
        configurations = []
        for args in ([], ['https://weread.qq.com/web/reader/test', '--format', 'markdown']):
            driver = MagicMock()
            driver.window_handles = []
            with patch('sys.argv', ['weread_export', *args]), \
                    patch('weread_export.__main__.Chrome', return_value=driver) as chrome, \
                    patch('weread_export.WeRead') as create_reader:
                main()
                configurations.append(chrome.call_args.kwargs['options'].arguments)
                if args:
                    call = create_reader.return_value.__enter__.return_value.scan2markdown.call_args
                    self.assertTrue(call.kwargs['from_start'])
        expected = f'--user-data-dir={Path(".browser-profile").resolve()}'
        for arguments in configurations:
            self.assertIn(expected, arguments)


if __name__ == '__main__':
    unittest.main()
