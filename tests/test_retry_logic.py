import time

from app.utils.retry_logic import (
    RateLimitTracker,
    TranslationRateLimiter,
    create_retry_decorator,
    retry_with_exponential_backoff,
)


class TestRateLimitTracker:
    def test_initial_state(self):
        tracker = RateLimitTracker()
        assert tracker.consecutive_rate_limits == 0
        assert tracker.calculate_delay() == 0
        assert tracker.should_apply_preventive_delay() is False

    def test_record_rate_limit(self):
        tracker = RateLimitTracker()
        tracker.record_rate_limit()
        assert tracker.consecutive_rate_limits == 1
        delay = tracker.calculate_delay()
        assert delay > 0

    def test_record_success_resets(self):
        tracker = RateLimitTracker()
        tracker.record_rate_limit()
        tracker.record_rate_limit()
        assert tracker.consecutive_rate_limits == 2
        tracker.record_success()
        assert tracker.consecutive_rate_limits == 0

    def test_exponential_backoff(self):
        tracker = RateLimitTracker()
        tracker.record_rate_limit()
        d1 = tracker.calculate_delay()
        tracker.record_rate_limit()
        d2 = tracker.calculate_delay()
        tracker.record_rate_limit()
        d3 = tracker.calculate_delay()
        assert d2 >= d1
        assert d3 >= d2

    def test_max_delay_cap(self):
        tracker = RateLimitTracker()
        tracker.max_delay = 300.0
        tracker.consecutive_rate_limits = 100
        delay = tracker.calculate_delay()
        assert delay <= tracker.max_delay * 1.26  # max_delay + jitter

    def test_is_rate_limit_error(self):
        tracker = RateLimitTracker()
        assert tracker.is_rate_limit_error(Exception("rate limit exceeded")) is True
        assert tracker.is_rate_limit_error(Exception("429")) is True
        assert tracker.is_rate_limit_error(Exception("Too Many Requests")) is True
        assert tracker.is_rate_limit_error(Exception("something else")) is False

    def test_preventive_delay(self):
        tracker = RateLimitTracker()
        tracker.record_rate_limit()
        assert tracker.should_apply_preventive_delay() is True
        preventive = tracker.get_preventive_delay()
        assert preventive > 0
        assert preventive <= 10.0


class TestRetryDecorator:
    def test_success_no_retry(self):
        call_count = 0

        @retry_with_exponential_backoff(max_retries=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_retry_then_success(self):
        call_count = 0

        @retry_with_exponential_backoff(max_retries=3, base_delay=0.001)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 3

    def test_all_retries_exhausted(self):
        call_count = 0

        @retry_with_exponential_backoff(max_retries=2, base_delay=0.001)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("persistent error")

        try:
            always_fail()
            raise AssertionError("Should have raised")
        except ValueError:
            pass
        assert call_count == 3


class TestTranslationRateLimiter:
    def test_get_tracker_google(self):
        limiter = TranslationRateLimiter()
        tracker = limiter.get_tracker("google")
        assert isinstance(tracker, RateLimitTracker)

    def test_get_tracker_openai(self):
        limiter = TranslationRateLimiter()
        tracker = limiter.get_tracker("openai")
        assert isinstance(tracker, RateLimitTracker)

    def test_create_decorator_google(self):
        decorator = create_retry_decorator("google")
        assert callable(decorator)

    def test_create_decorator_openai(self):
        decorator = create_retry_decorator("openai")
        assert callable(decorator)

    def test_get_tracker_unknown_service(self):
        limiter = TranslationRateLimiter()
        tracker = limiter.get_tracker("unknown")
        assert isinstance(tracker, RateLimitTracker)

    def test_apply_service_delay_no_need(self):
        limiter = TranslationRateLimiter()
        limiter.get_tracker("google").consecutive_rate_limits = 0
        limiter.apply_service_delay("google")

    def test_apply_service_delay_with_preventive(self):
        limiter = TranslationRateLimiter()
        limiter.get_tracker("google").consecutive_rate_limits = 1
        limiter.get_tracker("google").last_rate_limit_time = time.time()
        limiter.apply_service_delay("google")

    def test_preventive_delay_after_rate_limit(self):
        tracker = RateLimitTracker()
        tracker.consecutive_rate_limits = 1
        tracker.last_rate_limit_time = time.time()
        assert tracker.should_apply_preventive_delay() is True
        delay = tracker.get_preventive_delay()
        assert delay > 0
        assert delay <= 10.0

    def test_no_preventive_delay_without_history(self):
        tracker = RateLimitTracker()
        assert tracker.should_apply_preventive_delay() is False
        assert tracker.get_preventive_delay() == 0

    def test_preventive_delay_expired(self):
        tracker = RateLimitTracker()
        tracker.consecutive_rate_limits = 1
        tracker.last_rate_limit_time = time.time() - 400
        assert tracker.should_apply_preventive_delay() is False
