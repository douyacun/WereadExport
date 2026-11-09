from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest
from urllib.parse import quote, unquote

from PIL import Image

from weread_export.image_store import ImageStore
from weread_export.markdown_export import html_to_markdown


class LocalImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        buffer = BytesIO()
        Image.new('RGB', (4, 4), 'red').save(buffer, format='PNG')
        cls.image = buffer.getvalue()
        cls.requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.requests.append((self.path, dict(self.headers)))
                if self.path == '/missing':
                    self.send_error(404)
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'<html>login required</html>' if self.path == '/bad' else cls.image)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def store(self, directory):
        driver = SimpleNamespace(execute_script=lambda _: 'WereadExport-Test', get_cookies=lambda: [
            {'name': 'private', 'value': 'do-not-forward', 'domain': '.weread.qq.com', 'path': '/'},
        ])
        return ImageStore(driver, directory, '含 空格的书名')

    def test_download_deduplication_and_cookie_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            start = len(self.requests)
            first = store.save('/image.png', self.base + '/reader')
            self.assertEqual(first, store.save('/image.png', self.base + '/reader'))
            self.assertEqual(first, store.save('/same-image', self.base + '/reader'))
            self.assertEqual(len(self.requests) - start, 2)
            self.assertEqual(len(store.files), 1)
            self.assertEqual((Path(directory) / unquote(first)).read_bytes(), self.image)
            self.assertNotIn(' ', first)
            headers = self.requests[-1][1]
            self.assertEqual(headers.get('Referer'), self.base + '/reader')
            self.assertNotIn('Cookie', headers)

    def test_lazy_images_and_svg_image_links_are_local(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            result = html_to_markdown(
                '<img src="/placeholder" data-src="/image.png" alt="图一">'
                '<svg><image xlink:href="/same-image"/></svg>', self.base + '/reader', store)
            self.assertIn('![图一](assets/', result)
            self.assertNotIn(self.base, result)
            self.assertEqual(len(store.files), 1)

    def test_http_error_and_html_response_fail_without_image_file(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            for path in ('/bad', '/missing'):
                with self.assertRaisesRegex(RuntimeError, '图片保存失败'):
                    store.save(path, self.base + '/reader')
            self.assertFalse(store.directory.exists())

    def test_inline_svg_keeps_original_format(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="M0 0L10 10"/></svg>'
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            reference = store.save('data:image/svg+xml,' + quote(svg), self.base + '/reader')
            path = Path(directory) / unquote(reference)
            self.assertEqual(path.suffix, '.svg')
            self.assertEqual(path.read_text(encoding='utf-8'), svg)


if __name__ == '__main__':
    unittest.main()
