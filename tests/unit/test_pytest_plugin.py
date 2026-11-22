import pytest

pytest_plugins = ["pytester"]
pytestmark = pytest.mark.unit


def _run(pytester, body):
    pytester.makeini("[pytest]\nmarkers =\n    unit: x\n")
    pytester.makepyfile(body)
    return pytester.runpytest("-p", "dot11test.pytest_plugin", "-rs")


def test_not_implemented_in_test_becomes_skip(pytester):
    result = _run(pytester, """
        def test_toggle():
            raise NotImplementedError("ios.wifi_helper.disable not configured")
    """)
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*ios.wifi_helper.disable not configured*"])


def test_not_implemented_in_fixture_becomes_skip(pytester):
    result = _run(pytester, """
        import pytest

        @pytest.fixture
        def wifi_on():
            raise NotImplementedError("no helper")

        def test_scan(wifi_on):
            pass
    """)
    result.assert_outcomes(skipped=1)


def test_other_errors_still_fail(pytester):
    result = _run(pytester, """
        def test_bad():
            raise ValueError("real bug")
    """)
    result.assert_outcomes(failed=1)


def test_unit_marked_tests_are_not_masked(pytester):
    result = _run(pytester, """
        import pytest

        @pytest.mark.unit
        def test_framework_code():
            raise NotImplementedError("forgot to implement")
    """)
    result.assert_outcomes(failed=1)
