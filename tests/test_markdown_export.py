import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import quote

from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from weread_export.markdown_export import export_markdown, html_to_markdown


FIXTURE = '''<!doctype html><meta charset="utf-8">
<span class="readerTopBar_title_link">测试书</span>
<div id="preRenderContent"></div><div id="renderTargetContent">page0</div>
<div class="wr_canvasContainer"><canvas width="40" height="40"></canvas></div>
<button class="renderTarget_pager_button_right" onclick="advance()">下一页</button>
<script>
let page = 0;
function chapter(html) {
    document.querySelector('#preRenderContent').innerHTML = html;
    setTimeout(() => document.querySelector('#preRenderContent').innerHTML = '', 30);
}
setTimeout(() => chapter('<h1>第一章</h1><p><span>中</span><span>文</span>正文</p>'), 50);
function advance() {
    page++;
    if (page === 1) {
        // A recommendation page changes the UI without replacing the canvas.
        document.querySelector('button').insertAdjacentHTML('beforebegin', '<div>点评页</div>');
    } else if (page === 2) {
        // Normal reader pagination can redraw pixels without any DOM mutation.
        const context = document.querySelector('canvas').getContext('2d');
        context.fillStyle = 'black'; context.fillRect(0, 0, 40, 40);
    } else {
        document.querySelector('#renderTargetContent').textContent = 'page' + page;
    }
    if (page === 3) {
        chapter('<h1>第二章</h1><p>终章正文</p>');
        document.querySelector('button').remove();
        let end = document.createElement('div');
        end.className = 'readerFooter_ending'; end.textContent = '全书完';
        document.body.append(end);
    }
}
</script>'''


class MarkdownConversionTest(unittest.TestCase):
    def test_semantic_content_and_character_spans(self):
        result = html_to_markdown(
            '<style>bad css</style><h1>第一章</h1><p><span>中</span><span>文</span>'
            '<strong>加粗</strong></p><ul><li>项目</li></ul>'
            '<a href="/note">链接</a><img src="/a.png" alt="图片">'
            '<table><tr><th>列</th></tr><tr><td>值</td></tr></table>'
            '<script>bad script</script>', 'https://weread.qq.com/web/reader/book')
        for text in ('## 第一章', '中文', '**加粗**', '- 项目', '| 列 |', '| 值 |',
                     '[链接](https://weread.qq.com/note)', '![图片](https://weread.qq.com/a.png)'):
            self.assertIn(text, result)
        self.assertNotIn('bad', result)


@unittest.skipUnless(os.environ.get('WEREAD_BROWSER_TESTS') == '1', '需启用本地 Chrome 测试')
class MarkdownBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class FixtureChrome(Chrome):
            def get(self, url):
                super().get('data:text/html;charset=utf-8,' + quote(getattr(self, 'fixture', FIXTURE)))
        options = ChromeOptions()
        options.add_argument('--headless=new')
        cls.driver = FixtureChrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def reader(self):
        return SimpleNamespace(driver=self.driver, patience=5, S=lambda selector:
            WebDriverWait(self.driver, 5).until(lambda d: d.find_element(By.CSS_SELECTOR, selector)))

    def test_capture_survives_canvas_cleanup_and_deduplicates_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = export_markdown(self.reader(), 'https://weread.qq.com/web/reader/test', directory)
            text = path.read_text(encoding='utf-8')
            self.assertEqual(text.count('中文正文'), 1)
            self.assertIn('## 第二章', text)
            self.assertIn('终章正文', text)
            self.assertNotIn('尚未完成', text)
            self.assertFalse(list(Path(directory).glob('*.partial.md')))

    def test_page_limit_keeps_partial_and_preserves_previous_export(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / '测试书.md'
            target.write_text('previous export', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, '页上限'):
                export_markdown(self.reader(), 'https://weread.qq.com/web/reader/test', directory, max_pages=1)
            self.assertEqual(target.read_text(encoding='utf-8'), 'previous export')
            partial = Path(directory) / '测试书.partial.md'
            self.assertIn('尚未完成', partial.read_text(encoding='utf-8'))
            self.assertIn('中文正文', partial.read_text(encoding='utf-8'))

    def test_catalog_reset_does_not_export_restored_middle_position(self):
        catalog = '''<button class="catalog" onclick="document.querySelector('.readerCatalog').style.display='block'">目录</button>
        <div class="readerCatalog" style="display:none"><div class="readerCatalog_list_item_inner"
          onclick="page=0;this.parentElement.style.display='none';setTimeout(() => {
            document.querySelector('.readerFooter_ending').remove();
            chapter('<h1>第一章</h1><p>中文正文</p>');}, 800)">扉页</div></div>
        <div class="readerFooter_ending">全书完</div>'''
        self.driver.fixture = FIXTURE.replace('<script>', catalog + '<script>').replace(
            "setTimeout(() => chapter('<h1>第一章</h1><p><span>中</span><span>文</span>正文</p>'), 50)",
            "setTimeout(() => chapter('<h1>恢复到中途</h1><p>不应从这里开始</p>'), 0)")
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = export_markdown(self.reader(), 'https://weread.qq.com/web/reader/test', directory, from_start=True)
                text = path.read_text(encoding='utf-8')
                self.assertIn('## 第一章', text)
                self.assertIn('终章正文', text)
                self.assertNotIn('恢复到中途', text)
        finally:
            del self.driver.fixture

    def test_canvas_security_error_falls_back_to_webdriver_screenshot(self):
        self.driver.fixture = FIXTURE.replace('<script>', '''<script>
            HTMLCanvasElement.prototype.toDataURL = function() {
                throw new DOMException('Tainted canvas', 'SecurityError');
            };
        ''')
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = export_markdown(self.reader(), 'https://weread.qq.com/web/reader/test', directory)
                self.assertIn('终章正文', path.read_text(encoding='utf-8'))
        finally:
            del self.driver.fixture


if __name__ == '__main__':
    unittest.main()
