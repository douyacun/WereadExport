"""Download original reader images and return portable Markdown references."""

import hashlib
from http.cookiejar import Cookie, CookieJar
from io import BytesIO
import logging
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from xml.etree import ElementTree

from PIL import Image

logger = logging.getLogger(__name__)


class ImageStore:
    def __init__(self, driver, output, book_name):
        self.driver = driver
        self.output = Path(output)
        self.directory = self.output / 'assets' / book_name
        self.urls = {}
        self.files = set()
        self.user_agent = driver.execute_script('return navigator.userAgent')
        cookies = CookieJar()
        for cookie in driver.get_cookies():
            domain = cookie['domain']
            cookies.set_cookie(Cookie(
                version=0, name=cookie['name'], value=cookie['value'],
                port=None, port_specified=False, domain=domain,
                domain_specified=True, domain_initial_dot=domain.startswith('.'),
                path=cookie.get('path', '/'), path_specified=True,
                secure=cookie.get('secure', False), expires=cookie.get('expiry'),
                discard='expiry' not in cookie, comment=None, comment_url=None,
                rest={'HttpOnly': cookie.get('httpOnly', False)}, rfc2109=False,
            ))
        self.opener = build_opener(HTTPCookieProcessor(cookies))

    def _read(self, url, base_url):
        if url.startswith('blob:'):
            result = self.driver.execute_async_script("""
                const done = arguments[arguments.length - 1];
                fetch(arguments[0]).then(response => {
                    if (!response.ok) throw Error('HTTP ' + response.status);
                    return response.blob();
                }).then(blob => {
                    const reader = new FileReader();
                    reader.onload = () => done({data: reader.result});
                    reader.onerror = () => done({error: 'FileReader failed'});
                    reader.readAsDataURL(blob);
                }).catch(error => done({error: error.message}));
            """, url)
            if not result or result.get('error'):
                raise ValueError('浏览器无法读取 blob 图片')
            url = result['data']
        if urlsplit(url).scheme not in ('https', 'http', 'data'):
            raise ValueError('不支持的图片地址类型')
        request = Request(url, headers={'User-Agent': self.user_agent, 'Referer': base_url})
        for attempt in range(3):
            try:
                with self.opener.open(request, timeout=30) as response:
                    return response.read()
            except (URLError, TimeoutError, OSError) as exc:
                if isinstance(exc, HTTPError) and exc.code not in (408, 429) and exc.code < 500:
                    raise
                if attempt == 2:
                    raise
                logger.warning('图片下载暂时失败，正在重试（%s/2）', attempt + 1)
                sleep(attempt + 1)

    @staticmethod
    def _extension(data):
        if data.lstrip().startswith((b'<svg', b'<?xml')):
            root = ElementTree.fromstring(data)
            if root.tag.rsplit('}', 1)[-1] != 'svg':
                raise ValueError('返回内容不是 SVG 图片')
            return '.svg'
        with Image.open(BytesIO(data)) as image:
            format_name = image.format
            image.verify()
        return {'JPEG': '.jpg', 'TIFF': '.tif'}.get(format_name, '.' + format_name.lower())

    def save(self, source, base_url):
        url = urljoin(base_url, source)
        if url in self.urls:
            return self.urls[url]
        try:
            data = self._read(url, base_url)
            extension = self._extension(data)
            name = hashlib.sha256(data).hexdigest() + extension
            path = self.directory / name
            self.directory.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                temporary = path.with_suffix(path.suffix + '.tmp')
                temporary.write_bytes(data)
                temporary.replace(path)
            reference = quote(path.relative_to(self.output).as_posix(), safe='/')
            self.urls[url] = reference
            if path not in self.files:
                self.files.add(path)
                logger.info('图片已保存：%s（%s 字节）', path.relative_to(self.output), len(data))
            return reference
        except Exception as exc:
            host = urlsplit(url).hostname or urlsplit(url).scheme
            detail = f'HTTP {exc.code}' if isinstance(exc, HTTPError) else type(exc).__name__
            raise RuntimeError(f'图片保存失败（{host}，{detail}），停止导出以避免缺图') from exc
