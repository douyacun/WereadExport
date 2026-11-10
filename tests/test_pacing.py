import unittest
from unittest.mock import Mock

from weread_export.pacing import PagePacer


class FakeClock:
    def __init__(self):
        self.now = 0
        self.waits = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


class PacingTest(unittest.TestCase):
    def make_pacer(self, limits=(10, 20), intervals=(8, 120, 20)):
        clock = FakeClock()
        rng = Mock()
        rng.randint.side_effect = limits
        rng.uniform.side_effect = intervals
        return PagePacer(rng=rng, clock=clock.time, sleeper=clock.sleep), clock, rng

    def test_first_page_and_random_short_wait(self):
        pacer, clock, rng = self.make_pacer()
        pacer.page_processed()
        pacer.before_turn()
        self.assertEqual(pacer.pages, 1)
        self.assertEqual(clock.now, 8)
        rng.uniform.assert_called_once_with(8, 20)

    def test_boundary_and_new_random_segment(self):
        pacer, clock, rng = self.make_pacer(intervals=(120, 20))
        for _ in range(10):
            pacer.page_processed()
        with self.assertLogs('weread_export.pacing', level='INFO') as logs:
            pacer.before_turn()
        self.assertEqual(clock.now, 140)
        self.assertTrue(all(0 < wait <= 10 for wait in clock.waits))
        self.assertEqual(pacer.segment_limit, 20)
        self.assertEqual(pacer.segment_pages, 0)
        self.assertTrue(any('剩余约' in line for line in logs.output))
        self.assertEqual(rng.uniform.call_args_list[0].args, (60, 120))
        self.assertEqual(rng.uniform.call_args_list[1].args, (8, 20))

    def test_does_not_pause_before_boundary(self):
        pacer, clock, rng = self.make_pacer(limits=(20,), intervals=(8,))
        for _ in range(19):
            pacer.page_processed()
        pacer.before_turn()
        self.assertEqual(clock.now, 8)
        self.assertEqual(pacer.segment_pages, 19)
        rng.randint.assert_called_once_with(10, 20)

    def test_interrupted_wait_does_not_reset_segment(self):
        pacer, clock, rng = self.make_pacer(intervals=(60,))
        for _ in range(10):
            pacer.page_processed()
        pacer.sleeper = Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            pacer.before_turn()
        self.assertEqual(pacer.segment_pages, 10)
        self.assertEqual(rng.randint.call_count, 1)


if __name__ == '__main__':
    unittest.main()
