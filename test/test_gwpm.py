import pytest

from Scripts.gwpm.src.path_manager import (
    GeneralWorkPathManager,
    ReferenceVariable,
)


# ==========================================================
# ReferenceVariable
# ==========================================================

def test_reference_variable_creation():
    rv = ReferenceVariable(
        [["a", "b"], ["c", "d"]],
        0,
    )

    assert rv.reference_position == 0
    assert rv.values == [["a", "b"], ["c", "d"]]


def test_reference_variable_negative_reference():
    with pytest.raises(IndexError):
        ReferenceVariable(
            [["a"]],
            -1,
        )


def test_reference_variable_len():
    rv = ReferenceVariable(
        [["a"], ["b"]],
        0,
    )

    assert len(rv) == 2


def test_reference_variable_iter():
    rv = ReferenceVariable(
        [["a"], ["b"]],
        0,
    )

    assert list(rv) == [["a"], ["b"]]


def test_reference_variable_getitem():
    rv = ReferenceVariable(
        [["a"], ["b"]],
        0,
    )

    assert rv[1] == ["b"]


def test_reference_variable_contains():
    rv = ReferenceVariable(
        [["a"], ["b"]],
        0,
    )

    assert ["a"] in rv
    assert ["c"] not in rv


def test_reference_variable_to_dict():
    rv = ReferenceVariable(
        [["a"], ["b"]],
        0,
    )

    assert rv.to_dict() == {
        "values": [["a"], ["b"]],
        "reference_position": 0,
    }


# ==========================================================
# Constructor checks
# ==========================================================

def test_duplicate_replacers():
    with pytest.raises(ValueError):
        GeneralWorkPathManager(
            [["A"], ["B"]],
            replacer=["?", "?"],
        )


def test_invalid_replacer_length():
    with pytest.raises(IndexError):
        GeneralWorkPathManager(
            [["A"], ["B"]],
            replacer=["?"],
        )


def test_reference_variable_out_of_range():
    rv = ReferenceVariable(
        [["a"]],
        reference_position=2,
    )

    with pytest.raises(IndexError):
        GeneralWorkPathManager(
            [["A"], rv],
            replacer=["?", "!"],
        )


def test_reference_variable_self_reference():
    rv = ReferenceVariable(
        [["a"]],
        reference_position=1,
    )

    with pytest.raises(ValueError):
        GeneralWorkPathManager(
            [["A"], rv],
            replacer=["?", "!"],
        )


# ==========================================================
# Basic container behaviour
# ==========================================================

def test_len():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        replacer=["?", "!"],
    )

    assert len(gwpm) == 2


def test_contains():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        replacer=["?"],
    )

    assert "?" in gwpm
    assert "!" not in gwpm


def test_getitem_by_index():
    gwpm = GeneralWorkPathManager(
        [["A", "B"]],
        replacer=["?"],
    )

    assert gwpm[0] == ["A", "B"]


def test_getitem_by_replacer():
    gwpm = GeneralWorkPathManager(
        [["A", "B"]],
        replacer=["?"],
    )

    assert gwpm["?"] == ["A", "B"]


def test_getitem_unknown_replacer():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        replacer=["?"],
    )

    with pytest.raises(KeyError):
        gwpm["!"]


def test_keys_values_items():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        replacer=["?", "!"],
    )

    assert gwpm.keys() == ["?", "!"]
    assert gwpm.values() == [["A"], ["B"]]
    assert gwpm.items() == [
        ("?", ["A"]),
        ("!", ["B"]),
    ]


# ==========================================================
# Equality / serialization
# ==========================================================

def test_equality():
    gwpm1 = GeneralWorkPathManager(
        [["A"]],
        replacer=["?"],
        path="./?/",
    )

    gwpm2 = GeneralWorkPathManager(
        [["A"]],
        replacer=["?"],
        path="./?/",
    )

    assert gwpm1 == gwpm2


def test_to_dict_from_dict():
    gwpm = GeneralWorkPathManager(
        [["Li", "Na"]],
        path="./?/",
        file="test.xyz",
        replacer=["?"],
    )

    reconstructed = GeneralWorkPathManager.from_dict(
        gwpm.to_dict()
    )

    assert reconstructed == gwpm


# ==========================================================
# _resolve_variable
# ==========================================================

def test_resolve_standard_variable():
    gwpm = GeneralWorkPathManager(
        [["A", "B"]],
        replacer=["?"],
    )

    assert (
        gwpm._resolve_variable(
            ["A", "B"],
            1,
            [1],
        )
        == "B"
    )


def test_resolve_reference_variable():
    rv = ReferenceVariable(
        [
            ["fcc", "bcc"],
            ["hcp", "liq"],
        ],
        reference_position=0,
    )

    gwpm = GeneralWorkPathManager(
        [
            ["300K", "600K"],
            rv,
        ],
        replacer=["?", "!"],
    )

    resolved = gwpm._resolve_variable(
        rv,
        0,
        [1, 0],
    )

    assert resolved == "hcp"


def test_resolve_reference_variable_invalid():
    rv = ReferenceVariable(
        [["a"]],
        0,
    )

    gwpm = GeneralWorkPathManager(
        [["x"], rv],
        replacer=["?", "!"],
    )

    with pytest.raises(IndexError):
        gwpm._resolve_variable(
            rv,
            5,
            [0, 5],
        )


# ==========================================================
# Path conversion
# ==========================================================

def test_path_conversion_simple():
    gwpm = GeneralWorkPathManager(
        [
            ["Li", "Na"],
            ["300K", "600K"],
        ],
        path="./?/!/",
        replacer=["?", "!"],
    )

    result = gwpm.path_conversion([0, 1])

    assert result == "./Li/600K/"


def test_path_conversion_with_file():
    gwpm = GeneralWorkPathManager(
        [
            ["Li"],
            ["300K"],
        ],
        path="./?/!/",
        file="data.xyz",
        replacer=["?", "!"],
    )

    result = gwpm.path_conversion([0, 0])

    assert result == "./Li/300K/data.xyz"


def test_path_conversion_reference_variable():
    gwpm = GeneralWorkPathManager(
        [
            ["300K", "600K"],
            ReferenceVariable(
                [
                    ["fcc", "bcc"],
                    ["hcp", "liq"],
                ],
                0,
            ),
        ],
        path="./?/!/",
        replacer=["?", "!"],
    )

    result = gwpm.path_conversion([1, 0])

    assert result == "./600K/hcp/"


def test_path_conversion_invalid_indices_length():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        replacer=["?", "!"],
    )

    with pytest.raises(IndexError):
        gwpm.path_conversion([0])


# ==========================================================
# Manual path conversion
# ==========================================================

def test_path_manual_conversion():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        path="./?/!/",
        replacer=["?", "!"],
    )

    result = gwpm.path_manual_conversion(
        ["hello", "world"]
    )

    assert result == "./hello/world/"


def test_path_manual_conversion_output_file():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        path="./?/",
        replacer=["?"],
    )

    result = gwpm.path_manual_conversion(
        ["folder"],
        output_file="data.txt",
    )

    assert result == "./folder/data.txt"


# ==========================================================
# Replacer detection
# ==========================================================

def test_replacer_used():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        replacer=["?", "!"],
    )

    used = gwpm.replacer_used(
        "./?/!/"
    )

    assert used == ["?", "!"]


def test_contains_replacer():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        replacer=["?"],
    )

    assert gwpm.contains_replacer("./?/")
    assert not gwpm.contains_replacer("./folder/")


# ==========================================================
# Replacement engine
# ==========================================================

def test_apply_replacements():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        replacer=["?", "!"],
    )

    result = gwpm._apply_replacements(
        "./?/!/",
        ["hello", "world"],
    )

    assert result == "./hello/world/"


def test_longest_token_first():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        replacer=["$", "$$"],
    )

    result = gwpm._apply_replacements(
        "$$ and $",
        ["A", "B"],
    )

    assert result == "B and A"


# ==========================================================
# Recursive replacement
# ==========================================================

def test_recursive_replacement():
    gwpm = GeneralWorkPathManager(
        [
            ["Hello"],
            ["? World"],
        ],
        path="./!/",
        replacer=["?", "!"],
    )

    result = gwpm.path_conversion(
        [0, 0],
        refractored=True,
    )

    assert result == "./Hello World/"


def test_non_recursive_replacement():
    gwpm = GeneralWorkPathManager(
        [
            ["Hello"],
            ["? World"],
        ],
        path="./!/",
        replacer=["?", "!"],
    )

    result = gwpm.path_conversion(
        [0, 0],
        refractored=False,
    )

    assert result == "./? World/"


# ==========================================================
# Loop detection
# ==========================================================

def test_valid_dependency_graph():
    gwpm = GeneralWorkPathManager(
        [
            ["A"],
            ["?"],
        ],
        replacer=["?", "!"],
    )

    assert gwpm.check_loop_replacers()


def test_invalid_dependency_graph():
    gwpm = GeneralWorkPathManager(
        [
            ["!"],
            ["?"],
        ],
        replacer=["?", "!"],
    )

    with pytest.raises(ValueError):
        gwpm.check_loop_replacers()


# ==========================================================
# Current property
# ==========================================================

def test_current_property():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        path="./?/",
        file="file.xyz",
        replacer=["?"],
    )

    gwpm.path_conversion([0])

    current = gwpm.current

    assert current["path"] == "./Li/"
    assert current["path_file"] == "./Li/file.xyz"