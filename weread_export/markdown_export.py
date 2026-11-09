"""Capture the reader's rendered HTML and export accessible chapters as Markdown."""

import hashlib
import logging
from pathlib import Path
from time import sleep
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait

logger = logging.getLogger(__name__)


# The reader clears preRenderContent after painting its canvas. Observe it before
# navigation so the normal rendering process cannot discard the text we need.
CAPTURE_SCRIPT = r"""
(() => {
    window.__wrsMarkdown = null;
    window.__wrsMarkdownQueue = [];
    const capture = () => {
        const node = document.querySelector('#preRenderContent');
        if (!node || (!node.textContent.trim() && !node.querySelector('img,svg image'))) return;
        const html = node.innerHTML;
        if (window.__wrsMarkdown?.html === html) return;
        window.__wrsMarkdown = {html, url: location.href};
        window.__wrsMarkdownQueue.push(window.__wrsMarkdown);
    };
    new MutationObserver(capture).observe(document, {
        childList: true, subtree: true, characterData: true
    });
    capture();
})();
"""


def html_to_markdown(html, base_url, image_store=None):
    """Keep semantic content and optionally save linked images locally."""
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('script, style, noscript, [data-wr-ignore="1"]'):
        node.decompose()
    for node in soup.select('svg image'):
        image = soup.new_tag('img')
        image['src'] = node.get('href') or node.get('xlink:href', '')
        image['alt'] = node.get('aria-label', '')
        node.replace_with(image)
    for node in soup.select('img'):
        src = node.get('data-src') or node.get('data-original') or node.get('src')
        if not src and node.get('srcset'):
            src = node['srcset'].split(',')[-1].strip().split()[0]
        if src:
            node['src'] = image_store.save(src, base_url) if image_store else urljoin(base_url, src)
        elif image_store:
            raise RuntimeError('正文图片缺少图片地址，停止导出以避免缺图')
    for node in soup.select('a[href]'):
        node['href'] = urljoin(base_url, node['href'])
    # The book owns H1; chapter headings start at H2.
    for node in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
        node.name = f'h{int(node.name[1]) + 1}'
    return markdownify(str(soup), heading_style='ATX', bullets='-').strip()


def _page_signature(driver):
    state = driver.execute_script("""
        const content = document.querySelector('#renderTargetContent, .renderTargetContent');
        const canvases = [...document.querySelectorAll('.wr_canvasContainer canvas')];
        let pixels;
        try { pixels = canvases.map(canvas => canvas.toDataURL()).join('|'); }
        catch (error) { if (error.name !== 'SecurityError') throw error; pixels = null; }
        return {dom: location.href + '\\n' + (content ? content.innerHTML : '')
            + '\\n' + document.body.innerText, pixels};
    """)
    # Canvas redraws do not mutate innerHTML. Some illustrated books use tainted
    # canvases; WebDriver can still capture the rendered container in that case.
    pixels = state['pixels']
    if pixels is None:
        pixels = driver.find_element('css selector', '.wr_canvasContainer').screenshot_as_png
    elif isinstance(pixels, str):
        pixels = pixels.encode()
    return hashlib.sha256(state['dom'].encode() + pixels).hexdigest()


def _wait_for_stable_page(driver, wait):
    previous = None

    def settled(d):
        nonlocal previous
        current = _page_signature(d)
        stable = current == previous
        previous = current
        return stable and d.execute_script('return window.__wrsMarkdown')

    sleep(.5)
    wait.until(settled)


def _start_from_first_chapter(driver, wait):
    # The reader restores saved progress asynchronously after document load.
    # Let that render finish before our catalog jump, otherwise the restoration
    # can overwrite the jump and silently resume in a later chapter.
    wait.until(lambda d: d.execute_script('return window.__wrsMarkdown'))
    _wait_for_stable_page(driver, wait)

    def visible(d, selector):
        return d.execute_script("""return [...document.querySelectorAll(arguments[0])].find(
            node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden') || null;
        """, selector)

    wait.until(lambda d: visible(d, 'button.catalog')).click()
    first = wait.until(lambda d: visible(d, '.readerCatalog_list_item_title_text')
                       or visible(d, '.readerCatalog_list_item_inner, li.chapterItem'))
    first_title = first.get_attribute('textContent').strip()
    logger.info('Markdown：从目录首项“%s”开始，忽略上次阅读进度', first_title)
    # The catalog opens scrolled to the saved chapter. Bring its first entry
    # inside the custom scroll viewport before sending a real WebDriver click.
    driver.execute_script("""const area = document.querySelector('.readerCatalog_list_scroll_area');
        if (area) area.scrollTop = 0;
        arguments[0].scrollIntoView({block:'nearest'});
        window.__wrsMarkdown = null;
        window.__wrsMarkdownQueue = [];""", first)
    first.click()
    wait.until(lambda d: not visible(d, '.readerCatalog'))
    wait.until(lambda d: d.execute_script('return window.__wrsMarkdown'))
    _wait_for_stable_page(driver, wait)
    selected = driver.execute_script("""return document.querySelector(
        '.readerCatalog_list_item_selected .readerCatalog_list_item_title_text')?.textContent || null;""")
    if selected and selected.strip() != first_title:
        raise RuntimeError(f'目录首项切换未生效，当前仍在“{selected.strip()}”，已停止以避免缺章')


def export_markdown(weread, book_url, save_at='.', max_pages=10000, from_start=False):
    """Export accessible text; optionally reset the saved reading position."""
    if not book_url.startswith('https://weread.qq.com/web/reader/'):
        raise ValueError('请提供微信读书 /web/reader/ 链接')
    if max_pages < 1:
        raise ValueError('max_pages 必须大于 0')
    driver = weread.driver
    registration = driver.execute_cdp_cmd(
        'Page.addScriptToEvaluateOnNewDocument', {'source': CAPTURE_SCRIPT}
    )
    partial = None
    phase = '加载正文'
    try:
        driver.get(book_url)
        wait = WebDriverWait(driver, weread.patience)
        if from_start:
            phase = '切换到目录首项'
            _start_from_first_chapter(driver, wait)
        phase = '加载正文'
        wait.until(lambda d: d.execute_script('return window.__wrsMarkdown'))
        title = weread.S('.readerTopBar_title_link').text.strip() or '微信读书'
        # A generated filename must stay within the requested output directory.
        from .script import escape
        filename = escape(title).strip('. ') or '微信读书'
        output = Path(save_at)
        output.mkdir(parents=True, exist_ok=True)
        from .image_store import ImageStore
        images = ImageStore(driver, output, filename)
        target = output / f'{filename}.md'
        partial = output / f'{filename}.partial.md'
        safe_title = title.replace('\n', ' ').replace('#', r'\#')
        header = f'# {safe_title}\n\n来源：<{book_url}>\n\n'
        sections = []
        seen = set()

        def save_partial():
            partial.write_text(header + '> 导出尚未完成，以下仅为已读取内容。\n\n'
                               + '\n\n'.join(sections) + '\n', encoding='utf-8')

        save_partial()
        for page in range(1, max_pages + 1):
            snapshots = driver.execute_script("""
                const queue = window.__wrsMarkdownQueue;
                return queue?.length ? queue.splice(0) : [window.__wrsMarkdown].filter(Boolean);
            """)
            for snapshot in snapshots:
                phase = f'第 {page} 页转换正文及下载图片'
                body = html_to_markdown(snapshot['html'], snapshot['url'], image_store=images)
                if not body:
                    raise RuntimeError('当前章节没有可转换的正文内容，页面结构可能已变化')
                fingerprint = hashlib.sha256((snapshot['url'] + body).encode()).hexdigest()
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    sections.append(body)
                    save_partial()
                    logger.info('Markdown：已保存 %s 段章节内容（第 %s 页）', len(sections), page)

            endings = driver.execute_script(
                "return [...document.querySelectorAll('.readerFooter_ending')]"
            )
            if any(node.is_displayed() for node in endings):
                partial.write_text(header + '\n\n'.join(sections) + '\n', encoding='utf-8')
                partial.replace(target)
                print(f'Markdown 导出完成：{target.resolve()}', flush=True)
                logger.info('已保存 %s 张本地图片，目录：%s', len(images.files), images.directory.resolve())
                return target

            candidates = driver.execute_script("""return [...document.querySelectorAll(
                '.renderTarget_pager_button_right, .readerFooter_button')];""")
            next_button = next((node for node in candidates if node.is_displayed()
                                and node.is_enabled()
                                and node.text.strip() in ('下一页', '下一章')), None)
            if next_button is None:
                raise RuntimeError('没有找到可用的下一页或结束标记，可能需要登录、解锁章节或适配页面')
            if page == max_pages:
                raise RuntimeError(f'达到 --max-pages={max_pages} 页上限，尚未确认书籍结束')
            signature = _page_signature(driver)
            phase = f'第 {page} 页点击“{next_button.text.strip()}”后等待画面变化'
            logger.info('Markdown：第 %s 页，点击“%s”', page, next_button.text.strip())
            next_button.click()
            wait.until(lambda d: _page_signature(d) != signature)
            logger.debug('第 %s 页翻页后画面已变化', page)
            # Wait for the canvas and pre-render DOM to settle after navigation.
            phase = f'第 {page} 页翻页后等待渲染稳定'
            _wait_for_stable_page(driver, wait)
    except TimeoutException as exc:
        detail = f'；已读取内容保存在 {partial.resolve()}' if partial and partial.exists() else ''
        raise RuntimeError(f'{phase}超时，请检查登录、阅读权限和页面结构' + detail) from exc
    except Exception as exc:
        if partial and partial.exists():
            raise RuntimeError(f'{exc}；已读取内容保存在 {partial.resolve()}') from exc
        raise
    finally:
        driver.execute_cdp_cmd('Page.removeScriptToEvaluateOnNewDocument', registration)
