"""Conservative pacing shared by Markdown and PDF exports."""

import logging
import random
from time import monotonic, sleep

logger = logging.getLogger(__name__)


class PagePacer:
    def __init__(self, *, rng=None, clock=monotonic, sleeper=sleep):
        self.rng = rng if rng is not None else random.Random()
        self.clock = clock
        self.sleeper = sleeper
        self.pages = 0
        self.segment_pages = 0
        self.segment_limit = self.rng.randint(10, 20)
        logger.info('翻页节流已启用：每页等待 8～20 秒；每 10～20 页长休息 60～120 秒（本段 %s 页）',
                    self.segment_limit)

    def page_processed(self):
        """Count physical reader pages, including the first page."""
        self.pages += 1
        self.segment_pages += 1

    def _wait(self, duration, reason):
        logger.info('%s：等待 %.1f 秒（已处理 %s 页，Ctrl+C 可退出）', reason, duration, self.pages)
        deadline = self.clock() + duration
        last_report = self.clock()
        while True:
            remaining = deadline - self.clock()
            if remaining <= 0:
                break
            self.sleeper(min(10, remaining))
            now = self.clock()
            if now - last_report >= 30 and now < deadline:
                logger.info('%s：剩余约 %.0f 秒', reason, deadline - now)
                last_report = now

    def before_turn(self):
        """Wait only when another page is needed, never after the book ends."""
        if self.segment_pages >= self.segment_limit:
            self._wait(self.rng.uniform(60, 120), '分段长休息')
            self.segment_pages = 0
            self.segment_limit = self.rng.randint(10, 20)
            logger.info('长休息结束，下一段随机读取 %s 页', self.segment_limit)
        self._wait(self.rng.uniform(8, 20), '随机翻页间隔')
