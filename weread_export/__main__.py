"""Entry points for ``weread-export`` and ``python -m weread_export``."""

import argparse
import sys
import logging
from pathlib import Path
from time import sleep

from selenium.common.exceptions import WebDriverException
from selenium.webdriver import Chrome, ChromeOptions

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(prog="weread-export", description="WereadExport：启动微信读书，或导出为 PDF / Markdown。")
    parser.add_argument("book_url", nargs="?", help="微信读书的 /web/reader/ 链接")
    parser.add_argument("--check", action="store_true", help="检查依赖、Chrome 和网站连接后退出")
    parser.add_argument("--verbose", action="store_true", help="显示项目调试日志")
    parser.add_argument("--no-login", action="store_true", help="跳过扫码登录，扫描可访问的内容")
    parser.add_argument("--login-wait", type=int, default=180, help="扫码等待秒数，默认 180")
    parser.add_argument("--format", choices=("pdf", "markdown"), default="pdf", help="导出格式，默认 pdf")
    parser.add_argument("--max-pages", type=int, default=10000, help="Markdown 翻页上限，默认 10000")
    parser.add_argument("--from-current", action="store_true", help="Markdown 从当前阅读位置开始；默认从目录首项开始")
    parser.add_argument("--output", type=Path, default=Path("output"), help="导出目录")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
    if args.verbose:
        logging.getLogger('weread_export').setLevel(logging.DEBUG)
    if args.login_wait <= 0:
        parser.error("--login-wait 必须大于 0")
    if args.max_pages < 1:
        parser.error("--max-pages 必须大于 0")
    if args.format == "markdown" and not args.book_url:
        parser.error("Markdown 导出需要提供书籍链接")
    if args.book_url and not args.book_url.startswith("https://weread.qq.com/web/reader/"):
        parser.error("请提供 https://weread.qq.com/web/reader/ 开头的书籍链接")

    options = ChromeOptions()
    if args.check or args.book_url:
        options.add_argument("--headless=new")
    if not args.check:
        # Visible login and headless exports share the same persisted session.
        profile = Path(".browser-profile").resolve()
        options.add_argument(f"--user-data-dir={profile}")
        logger.info('浏览器登录数据目录：%s', profile)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1280,900")
    logger.info('正在启动 Chrome（%s模式）…', '无头' if args.check or args.book_url else '可见窗口')
    driver = Chrome(options=options)
    try:
        driver.set_page_load_timeout(60)
        from . import WeRead

        with WeRead(driver) as weread:
            logger.info('已打开：%s (%s)', driver.title, driver.current_url)
            if args.check:
                if "weread.qq.com" not in driver.current_url or not driver.title:
                    raise RuntimeError("微信读书页面未正常加载")
                print("检查通过：Python 依赖、Chrome、WebDriver、微信读书连接正常。", flush=True)
                return
            if not args.book_url:
                if not args.no_login:
                    weread.login(wait_turns=args.login_wait, show_qrcode=False)
                    logger.info('登录流程完成。关闭此 Chrome 窗口后，可运行导出命令复用登录状态。')
                else:
                    logger.info('已跳过自动登录。可在 Chrome 窗口中自行操作。')
                logger.info('正在保持浏览器窗口，关闭窗口或按 Ctrl+C 退出。')
                print('导出命令：uv run weread-export "书籍链接" --format markdown', flush=True)
                while True:
                    try:
                        if not driver.window_handles:
                            break
                    except WebDriverException:
                        break
                    sleep(1)
                logger.info('Chrome 窗口已关闭，正在退出。')
                return
            args.output.mkdir(parents=True, exist_ok=True)
            if not args.no_login:
                weread.login(wait_turns=args.login_wait)
            if args.format == "markdown":
                weread.scan2markdown(args.book_url, save_at=str(args.output.resolve()),
                                     max_pages=args.max_pages, from_start=not args.from_current)
            else:
                weread.scan2pdf(args.book_url, save_at=str(args.output.resolve()))
    finally:
        driver.quit()
        logger.info('浏览器已退出，登录数据已保存在本地。')


def cli():
    """Keep console-script and module invocation error handling identical."""
    try:
        main()
    except KeyboardInterrupt:
        print("已退出。")
    except RuntimeError as exc:
        logger.error('操作失败：%s', exc)
        sys.exit(1)
    except WebDriverException as exc:
        logger.error('浏览器操作失败：%s', exc.msg)
        sys.exit(1)


if __name__ == "__main__":
    cli()
