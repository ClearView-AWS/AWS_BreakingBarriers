"""Evidence operators accept both '>= 8' and '>=:8' forms."""

from evidence.status import op_matches


def test_comparison_space_and_colon():
    assert op_matches(">= 8", 9) is True
    assert op_matches(">=:8", 8) is True
    assert op_matches(">= 8", 7) is False
    assert op_matches("<= 15", 12) is True
    assert op_matches("> 18", 20) is True
    assert op_matches("== 7", 7) is True


def test_bool_comparison():
    assert op_matches("== true", True) is True
    assert op_matches("==:true", True) is True
    assert op_matches("== true", False) is False
    assert op_matches("== false", False) is True
    assert op_matches("== false", True) is False
