from conftest import CASES, ROOT

from firewatch.bench import MAVEN_TEST_COMMAND, TEST_COMMAND, load_cases

JAVA_CASES = ROOT / "bench" / "cases-java"


def test_java_cases_are_discovered_with_maven():
    cases = load_cases(JAVA_CASES)
    assert [case["name"] for case in cases] == [
        "batch_loop_off_by_one",
        "free_shipping_boundary",
        "missing_middle_null",
    ]
    for case in cases:
        assert case["test_command"] == MAVEN_TEST_COMMAND
        assert (case["path"] / "pom.xml").is_file()
        assert case["solution"]


def test_explicit_test_command_wins(tmp_path):
    case_dir = tmp_path / "custom"
    case_dir.mkdir()
    (case_dir / "pom.xml").write_text("<project/>", encoding="utf-8")
    (case_dir / "case.json").write_text(
        '{"title": "t", "category": "c", "test_command": "./gradlew test", "solution": []}',
        encoding="utf-8",
    )
    (case,) = load_cases(tmp_path)
    assert case["test_command"] == "./gradlew test"


def test_python_cases_keep_pytest():
    cases = load_cases(CASES)
    assert cases and all(case["test_command"] == TEST_COMMAND for case in cases)