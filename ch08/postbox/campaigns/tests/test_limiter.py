import time

from campaigns import limiter


def name():
    return f"test-{time.time_ns()}"


def test_it_lets_through_up_to_the_maximum_then_stops(real_redis):
    name = f"test-{time.time_ns()}"
    now = 1_000_000.0
    outcomes = [limiter.allow(name, 3, now=now) for _ in range(5)]
    assert outcomes == [True, True, True, False, False]


def test_a_new_window_starts_from_zero(real_redis):
    n = name()
    assert [limiter.allow(n, 1, now=1_000_000.0) for _ in range(2)] == [True, False]
    assert limiter.allow(n, 1, now=1_000_001.0) is True


def test_different_names_do_not_share_the_counter(real_redis):
    a, b = name() + "a", name() + "b"
    assert limiter.allow(a, 1, now=5.0) is True
    assert limiter.allow(b, 1, now=5.0) is True
    assert limiter.allow(a, 1, now=5.0) is False


def test_the_counters_expire_by_themselves(real_redis):
    n = name()
    limiter.allow(n, 1, now=2_000_000.0)
    ttl = real_redis.ttl(f"limit:{n}:{2_000_000}")
    assert 0 < ttl <= 2
