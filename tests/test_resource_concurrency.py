import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep

from backend.resources import cached_resource


class ResourceConcurrencyTests(unittest.TestCase):
    def test_parallel_cold_requests_build_once(self):
        starts = Barrier(8)
        calls = []

        @cached_resource
        def model():
            calls.append(1)
            sleep(0.03)
            return object()

        def request(_):
            starts.wait(timeout=3)
            return model()

        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(request, range(8)))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(v is values[0] for v in values))

    def test_nested_resources_and_retry_after_failure(self):
        attempts = []

        @cached_resource
        def dataset():
            return 10

        @cached_resource
        def model():
            attempts.append(1)
            if len(attempts) == 1:
                raise ValueError('temporary failure')
            return dataset() + 2

        with self.assertRaises(ValueError):
            model()
        self.assertEqual(model(), 12)
        self.assertEqual(model(), 12)
        self.assertEqual(len(attempts), 2)

    def test_different_models_do_not_build_at_the_same_time(self):
        starts = Barrier(2)
        active = []
        observed = []

        def build():
            active.append(1)
            observed.append(len(active))
            sleep(0.03)
            active.pop()
            return 1

        first, second = cached_resource(build), cached_resource(build)

        def request(model):
            starts.wait(timeout=3)
            return model()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(request, [first, second]))
        self.assertEqual(observed, [1, 1])


if __name__ == '__main__':
    unittest.main()
