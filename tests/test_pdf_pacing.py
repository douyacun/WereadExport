from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from weread_export import WeRead


class PdfPacingTest(unittest.TestCase):
    def test_pacing_counts_across_chapters_and_skips_final_wait(self):
        reader = WeRead.__new__(WeRead)
        reader.driver = Mock()
        reader.turn_light_on = Mock()
        reader.set_font_size = Mock()
        reader.switch_to_context = Mock()
        reader.check_all_image_loaded = Mock()
        reader.shot_full_canvas_context = Mock()
        next_chapter = Mock(text='下一章')
        next_chapter.get_attribute.return_value = 'readerFooter_button'
        ending = Mock()
        ending.get_attribute.return_value = 'readerFooter_ending'
        footers = iter((next_chapter, ending))

        def select(selector):
            if selector == 'span.readerTopBar_title_link':
                return SimpleNamespace(text='测试书')
            if selector == 'span.readerTopBar_title_chapter':
                return SimpleNamespace(text='章节')
            if selector == '.readerFooter_button,.readerFooter_ending':
                return next(footers)
            return Mock()

        reader.S = select
        with patch('weread_export.WeRead.PagePacer') as factory, \
                patch('weread_export.WeRead.sleep'), patch('weread_export.WeRead.dir_check'), \
                patch('weread_export.WeRead.img2pdf'):
            reader.scan2pdf('https://weread.qq.com/web/reader/test', show_output=False)
        self.assertEqual(factory.return_value.page_processed.call_count, 2)
        factory.return_value.before_turn.assert_called_once()
        next_chapter.click.assert_called_once()


if __name__ == '__main__':
    unittest.main()
