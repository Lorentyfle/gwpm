"""Test of the General Work Path Manager classes."""
import pytest
from pathlib import Path
## Classes tested.
from gwpm import (
    GeneralWorkPathManager,
    ReferenceVariable,
)
## Exceptions.
from gwpm import (
    ReplacerConfigurationError,
    PathResolutionError,
    ReferenceResolutionError,
    DependencyLoopError,
    PlaceHolderSeriesError,
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
    rv = ReferenceVariable(
        [["a"]],
        -1,
    )
    gwpm = GeneralWorkPathManager(
        [["x"], rv],
        placeholders=["?", "!"],
    )
    assert rv.reference_position == 0
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
        "__type__": "ReferenceVariable",
        "values": [["a"], ["b"]],
        "reference_position": 0,
    }
def test_reference_variable_str():
    rv = ReferenceVariable(
        [["a"]],
        0,
    )
    text = str(rv)
    assert "ReferenceVariable" in text
    assert "reference_position=0" in text
# ==========================================================
# Constructor checks
# ==========================================================
def test_duplicate_placeholders():
    with pytest.raises(ReplacerConfigurationError):
        GeneralWorkPathManager(
            [["A"], ["B"]],
            placeholders=["?", "?"],
        )
def test_invalid_placeholders_length():
    with pytest.raises(PathResolutionError):
        GeneralWorkPathManager(
            [["A"], ["B"]],
            placeholders=["?"],
        )
def test_reference_variable_out_of_range():
    rv = ReferenceVariable(
        [["a"]],
        reference_position=2,
    )

    with pytest.raises(ReplacerConfigurationError):
        GeneralWorkPathManager(
            [["A"], rv],
            placeholders=["?", "!"],
        )
def test_reference_variable_self_reference():
    rv = ReferenceVariable(
        [["a"]],
        reference_position=1,
    )
    with pytest.raises(ReplacerConfigurationError):
        GeneralWorkPathManager(
            [["A"], rv],
            placeholders=["?", "!"],
        )
def test_current_initially_none():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
    )

    assert gwpm.current_path is None
    assert gwpm.current_path_file is None
def test_constructor_placeholders_none():
    with pytest.raises(ReplacerConfigurationError):
        GeneralWorkPathManager(
            [["A"]],
            placeholders=None,
        )
def test_reference_variable_future_reference():
    rv = ReferenceVariable(
        [["a"]],
        0,
    )
    with pytest.raises(ReplacerConfigurationError):
        GeneralWorkPathManager(
            [rv, ["b"]],
            placeholders=["?", "!"],
        )
# ==========================================================
# Basic container behavior
# ==========================================================
def test_len():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    assert len(gwpm) == 2
def test_contains():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    assert "?" in gwpm
    assert "!" not in gwpm
def test_getitem_by_index():
    gwpm = GeneralWorkPathManager(
        [["A", "B"]],
        placeholders=["?"],
    )

    assert gwpm[0] == ["A", "B"]
def test_getitem_by_placeholders():
    gwpm = GeneralWorkPathManager(
        [["A", "B"]],
        placeholders=["?"],
    )

    assert gwpm["?"] == ["A", "B"]
def test_getitem_unknown_placeholders():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    with pytest.raises(KeyError):
        gwpm["!"]
def test_keys_values_items():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    assert gwpm.keys() == ["?", "!"]
    assert gwpm.values() == [["A"], ["B"]]
    assert gwpm.items() == [
        ("?", ["A"]),
        ("!", ["B"]),
    ]
def test_iter():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    assert list(gwpm) == [
        ("?", ["A"]),
        ("!", ["B"]),
    ]
def test_repr():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
        path="./?/",
        file="data.xyz",
    )

    text = repr(gwpm)

    assert "GeneralWorkPathManager" in text
    assert "n_variables=1" in text
    assert "n_variables=1" in repr(gwpm)
def test_str():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    text = str(gwpm)

    assert "general_path" in text
    assert "output_folder" in text
def test_eq_other_type():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )
    assert gwpm != "hello"
def test_reference_variable_to_dict_from_dict_roundtrip():
    gwpm = GeneralWorkPathManager(
        list_of_variables=[
            ["A", "B"],
            ReferenceVariable(
                values=[
                    ["x", "y"],
                    ["z", "w"],
                ],
                reference_position=0,
            ),
        ],
        placeholders=["!", "?"],
    )

    restored = GeneralWorkPathManager.from_dict(
        gwpm.to_dict()
    )

    assert restored == gwpm
    assert isinstance(
        restored.list_of_variables[1],
        ReferenceVariable,
    )
# ==========================================================
# Equality / serialization
# ==========================================================
def test_equality():
    gwpm1 = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
        path="./?/",
    )

    gwpm2 = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
        path="./?/",
    )

    assert gwpm1 == gwpm2
def test_to_dict_from_dict():
    gwpm = GeneralWorkPathManager(
        [["Li", "Na"]],
        path="./?/",
        file="test.xyz",
        placeholders=["?"],
    )

    reconstructed = GeneralWorkPathManager.from_dict(
        gwpm.to_dict()
    )

    assert reconstructed == gwpm
def test_to_dict_reference_variable():
    with pytest.raises(ReplacerConfigurationError):
        gwpm = GeneralWorkPathManager(
            [["300K",'500K'],
                ReferenceVariable([["fcc"]],2),
                ["O"]
            ],placeholders=["?",'!','$']
            )
def test_getlarger_referenceplaceholders():
    gwpm = GeneralWorkPathManager(
        [
            ["300K"],
            ReferenceVariable(
                [["fcc"]],
                0,
            ),
        ],
        placeholders=["?", "!"],
    )
    data = gwpm.to_dict()
    assert (
        data["list_of_variables"][1]["__type__"]
        == "ReferenceVariable"
    )
# ==========================================================
# Serialization
# ==========================================================
def test_reference_variable_from_dict():
    data = {
        "__type__": "ReferenceVariable",
        "values": [["a"], ["b"]],
        "reference_position": 0,
    }

    rv = ReferenceVariable.from_dict(data)

    assert rv.values == [["a"], ["b"]]
    assert rv.reference_position == 0
def test_json_roundtrip(tmp_path):
    filename = tmp_path / "gwpm.json"

    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/",
    )

    gwpm.to_json(filename)

    loaded = GeneralWorkPathManager.from_json(
        filename
    )

    assert loaded == gwpm
def test_pickle_roundtrip(tmp_path):
    filename = tmp_path / "gwpm.pkl"

    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
    )

    gwpm.save(filename)

    loaded = GeneralWorkPathManager.load(
        filename
    )

    assert loaded == gwpm
# ==========================================================
# Index normalization
# ==========================================================
def test_normalize_index_placeholders_dict():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    assert gwpm._normalize_index(
        {"?": 0, "!": 0}
    ) == [0, 0]
def test_normalize_index_variable_dict():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
        variable_names=["x", "y"],
    )

    assert gwpm._normalize_index(
        {"x": 0, "y": 0}
    ) == [0, 0]
def test_normalize_index_missing_key():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    with pytest.raises(PathResolutionError):
        gwpm._normalize_index({"?": 0})
def test_normalize_index_list():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )
    assert gwpm._normalize_index([0]) == [0]
def test_normalize_index_wrong_keys():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
        variable_names=["x", "y"],
    )
    with pytest.raises(PathResolutionError):
        gwpm._normalize_index(
            {
                "?": 0,
                "y": 0,
            }
        )
def test_normalize_index_variable_names_none_uses_empty_set():
    gwpm = GeneralWorkPathManager(
        list_of_variables=[["A"]],
        placeholders=["!"],
    )

    gwpm.variable_names = None

    with pytest.raises(PathResolutionError):
        gwpm._normalize_index({"some_name": 0})
def test_normalize_index_missing_variable_name():
    gwpm = GeneralWorkPathManager(
        list_of_variables=[
            ["A", "B"],
            ["X", "Y"],
        ],
        placeholders=["!", "?"],
        variable_names=["element", "phase"],
    )

    with pytest.raises(
        PathResolutionError,
        match=r"Missing variable\(s\):",
    ):
        gwpm._normalize_index({
            "element": 0,
            # "phase" missing
        })
# ==========================================================
# _resolve_variable
# ==========================================================
def test_resolve_standard_variable():
    gwpm = GeneralWorkPathManager(
        [["A", "B"]],
        placeholders=["?"],
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
        placeholders=["?", "!"],
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
        placeholders=["?", "!"],
    )

    with pytest.raises(ReferenceResolutionError):
        gwpm._resolve_variable(
            rv,
            5,
            [0, 5],
        )
# ==========================================================
# Path conversion
# ==========================================================
def test_resolve_path_simple():
    gwpm = GeneralWorkPathManager(
        [
            ["Li", "Na"],
            ["300K", "600K"],
        ],
        path="./?/!/",
        placeholders=["?", "!"],
    )

    result = gwpm.resolve_path([0, 1])

    assert result == Path("Li/600K")
def test_resolve_path_with_file():
    gwpm = GeneralWorkPathManager(
        [
            ["Li"],
            ["300K"],
        ],
        path="./?/!/",
        file="data.xyz",
        placeholders=["?", "!"],
    )

    result = gwpm.resolve_path([0, 0])

    assert result == Path("./Li/300K/data.xyz")
def test_resolve_path_reference_variable():
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
        placeholders=["?", "!"],
    )
    result = gwpm.resolve_path([1, 0])
    assert result == Path("./600K/hcp/")
def test_resolve_path_invalid_indices_length():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    with pytest.raises(PathResolutionError):
        gwpm.resolve_path([0])
def test_immutable_does_not_update_current():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/",
    )

    gwpm.resolve_path(
        [0],
        immutable=True,
    )

    assert gwpm.current_path is None
    assert gwpm.current_path_file is None
# ==========================================================
# Internal path helpers
# ==========================================================
def test_build_path_starter():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
        path="./?/",
    )

    path, path_file = gwpm._build_path(
        starter="/tmp/"
    )

    assert path.startswith("/tmp/")
    assert path_file.startswith("/tmp/")
def test_build_path_output_folder():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
        output_folder="output/",
    )

    path, _ = gwpm._build_path(
        is_out=True,
    )

    assert path.endswith("output/")
# ==========================================================
# Manual path conversion
# ==========================================================
def test_resolve_values():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        path="./?/!/",
        placeholders=["?", "!"],
    )

    result = gwpm.resolve_values(
        ["hello", "world"]
    )

    assert result == Path("./hello/world/")
def test_resolve_values_output_file():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        path="./?/",
        placeholders=["?"],
    )
    result = gwpm.resolve_values(
        ["folder"],
        output_file="data.txt",
    )
    assert result == Path("./folder/data.txt")
def test_resolve_values_wrong_number_of_variables():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        ["!", "?"],
    )

    with pytest.raises(PathResolutionError):
        gwpm.resolve_values(["A"])
def test_resolve_values_recursive_branch():
    gwpm = GeneralWorkPathManager(
        [["x"], ["y"]],
        ["!", "?"],
        path="!/",
        file="?",
    )

    gwpm.resolve_values(
        ["A", "!B"],
        recursive=True,
    )

    assert gwpm.current_path_file == Path("A/AB")
def test_resolve_values_immutable():
    gwpm = GeneralWorkPathManager(
        list_of_variables=[["A"]],
        placeholders=["!"],
        path="./!/",
        file="file.txt",
    )

    result = gwpm.resolve_values(
        ["A"],
        immutable=True,
    )

    assert result == Path("./A/file.txt")
    assert gwpm.current_path is None
    assert gwpm.current_path_file is None
# ==========================================================
# Replacer detection
# ==========================================================
def test_placeholders_used():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    used = gwpm.placeholders_used(
        "./?/!/"
    )

    assert used == ["?", "!"]
def test_contains_placeholders():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    assert gwpm.contains_placeholders("./?/")
    assert not gwpm.contains_placeholders("./folder/")
# ==========================================================
# Replacement engine
# ==========================================================
def test_apply_replacements():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["?", "!"],
    )

    result = gwpm._apply_replacements(
        "./?/!/",
        ["hello", "world"],
    )

    assert result == "./hello/world/"
def test_longest_token_first():
    gwpm = GeneralWorkPathManager(
        [["A"], ["B"]],
        placeholders=["$", "$$"],
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
        placeholders=["?", "!"],
    )

    result = gwpm.resolve_path(
        [0, 0],
        recursive=True,
    )

    assert result == Path("./Hello World/")
def test_non_recursive_replacement():
    gwpm = GeneralWorkPathManager(
        [
            ["Hello"],
            ["? World"],
        ],
        path="./!/",
        placeholders=["?", "!"],
    )

    result = gwpm.resolve_path(
        [0, 0],
        recursive=False,
    )

    assert result == Path("./? World/")
def test_resolve_recursive_stalled():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    with pytest.raises(PathResolutionError):
        gwpm._resolve_recursive(
            "?",
            ["?"],
        )
def test_resolve_recursive_max_depth():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    with pytest.raises(PathResolutionError):
        gwpm._resolve_recursive(
            "?",
            ["??"],
            maximum_loop=5,
        )
# ==========================================================
# Loop detection
# ==========================================================
def test_valid_dependency_graph():
    gwpm = GeneralWorkPathManager(
        [
            ["A"],
            ["?"],
        ],
        placeholders=["?", "!"],
    )

    assert gwpm._check_loop_placeholders()
def test_invalid_dependency_graph():
    gwpm = GeneralWorkPathManager(
        [
            ["!"],
            ["?"],
        ],
        placeholders=["?", "!"],
    )

    with pytest.raises(DependencyLoopError):
        gwpm._check_loop_placeholders()
def test_check_loop_placeholderss_length_mismatch():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    with pytest.raises(DependencyLoopError):
        gwpm._check_loop_placeholders(
            [["A"], ["B"]]
        )
def test_check_loop_placeholderss_nested_list_values():
    gwpm = GeneralWorkPathManager(
        list_of_variables=[
            [
                ["?A", "?B"],
                ["C", "D"],
            ],
            ["X"],
        ],
        placeholders=["!", "?"],
    )
    assert gwpm._check_loop_placeholders() is True
# ==========================================================
# Current property
# ==========================================================
def test_current_property():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        path="./?/",
        file="file.xyz",
        placeholders=["?"],
    )

    gwpm.resolve_path([0])

    current = gwpm.current

    assert current["path"] == Path("./Li/")
    assert current["path_file"] == Path("./Li/file.xyz")
def test_current_property_empty():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    assert gwpm.current == {
        "path": None,
        "path_file": None,
    }
# ==========================================================
# General Path conversion
# ==========================================================
def test_path_general_conversion():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
    )

    result = gwpm.path_general_conversion(
        "./?/",
        "data.xyz",
        [0],
    )

    assert result["path"] == "./Li/"
    assert "Li" in result["path_file"]
    assert result["var_used"] == ["?"]
def test_path_recursive_general_conversion():
    gwpm = GeneralWorkPathManager(
        [
            ["Hello"],
            ["? World"],
        ],
        placeholders=["?", "!"],
    )

    result = (
        gwpm
        .path_recursive_general_conversion(
            "./",
            "!",
            [0, 0],
        )
    )

    assert result == "./Hello World"
def test_path_general_conversion_wrong_number_of_indices():
    gwpm = GeneralWorkPathManager(
        list_of_variables=[
            ["A", "B"],
            ["X", "Y"],
        ],
        placeholders=["!", "?"],
    )

    with pytest.raises(
        PathResolutionError,
        match=r"Expected 2 indices, received 1",
    ):
        gwpm.path_general_conversion(
            g_path="./!/?/",
            g_file="file.txt",
            index=[0],
        )
# ==========================================================
# Resolve
# ==========================================================
def test_resolve():
    gwpm = GeneralWorkPathManager(
        [
            ["Li", "Na"],
            ["300K", "600K"],
        ],
        placeholders=["?", "!"],
        path="./?/!/",
        file="data.xyz",
        variable_names=["element", "temperature"],
    )

    result = gwpm.resolve(
        element="Li",
        temperature="600K",
    )

    assert result == Path("./Li/600K/data.xyz")
def test_resolve_missing_variable():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        variable_names=["element"],
    )

    with pytest.raises(KeyError):
        gwpm.resolve()
def test_resolve_invalid_value():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        variable_names=["element"],
    )

    with pytest.raises(PathResolutionError):
        gwpm.resolve(
            element="Fe"
        )
def test_resolve_from_indices():
    gwpm = GeneralWorkPathManager(
        [["Li", "Na"]],
        placeholders=["?"],
        variable_names=["element"],
        path="./?/",
    )

    result = gwpm.resolve(
        element=1,
    )

    assert result == Path("Na")
def test_resolve_reference_variable_as_value():
    gwpm = GeneralWorkPathManager(
        [
            ["300K", "600K"],
            ReferenceVariable(
                [
                    ["fcc"],
                    ["hcp"],
                ],
                0,
            ),
        ],
        placeholders=["?", "!"],
        variable_names=[
            "temperature",
            "structure",
        ],
    )

    with pytest.raises(PathResolutionError):
        gwpm.resolve(
            temperature="300K",
            structure="fcc",
        )
# ==========================================================
# Parsing
# ==========================================================
def test_parse():
    gwpm = GeneralWorkPathManager(
        [
            ["Li"],
            ["300K"],
        ],
        placeholders=["?", "!"],
        variable_names=[
            "element",
            "temperature",
        ],
        path="./?/!/",
    )

    result = gwpm.parse(
        "./Li/300K/"
    )

    assert result == {
        "element": "Li",
        "temperature": "300K",
    }

    result = gwpm.parse(
        "./Na/500K/"
    )

    assert result == {
        "element": "Na",
        "temperature": "500K",
    }
def test_parse_invalid():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/",
    )
    with pytest.raises(PathResolutionError):
        gwpm.parse("completely_invalid")
# ==========================================================
# Iteration
# ==========================================================
def test_iter_paths():
    gwpm = GeneralWorkPathManager(
        [
            ["Li", "Na"],
            ["300K"],
        ],
        placeholders=["?", "!"],
        path="./?/!/",
    )

    data = list(gwpm.iter_paths())

    assert len(data) == 2
def test_all_paths():
    gwpm = GeneralWorkPathManager(
        [
            ["Li", "Na"],
            ["300K"],
        ],
        placeholders=["?", "!"],
        path="./?/!/",
    )
    paths = gwpm.all_paths()
    assert len(paths) == 2
# ==========================================================
# pd.DataFrame
# ==========================================================
def test_dataframe_roundtrip():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
    )

    df = gwpm.to_dataframe()

    reconstructed = (
        GeneralWorkPathManager
        .from_dataframe(df)
    )

    assert reconstructed == gwpm
# ==========================================================
# PlaceholderSeries
# ==========================================================
class DummyReader:
    def read_merged(self, series):
        return "merged"

    def read_all(self, series):
        return "all"
def test_placeholder_series_from_current():
    placeholder = "<P>"
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/",
        file=placeholder+'.xyz'
    )
    gwpm.resolve_path([0])
    series = gwpm.get_placeholder_series(placeholder=placeholder)
    assert series is not None
def test_placeholder_series_without_placeholder():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/",
    )
    gwpm.resolve_path([0])
    with pytest.raises(PlaceHolderSeriesError):
        gwpm.get_placeholder_series()
def test_placeholder_series_template():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/[.xyz",
    )

    series = gwpm.get_placeholder_series(
        use_current=False
    )

    assert series is not None
def test_placeholder_series_no_current_path():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
    )

    with pytest.raises(PathResolutionError):
        gwpm.get_placeholder_series()
def test_read_placeholder_series_merged():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/",
        file="<P>.xyz",
    )

    gwpm.resolve_path([0])

    result = gwpm.read_placeholder_series(
        DummyReader(),
        placeholder="<P>",
        is_merged=True,
    )

    assert result == "merged"
def test_read_placeholder_series_all():
    gwpm = GeneralWorkPathManager(
        [["Li"]],
        placeholders=["?"],
        path="./?/",
        file="<P>.xyz",
    )

    gwpm.resolve_path([0])

    result = gwpm.read_placeholder_series(
        DummyReader(),
        placeholder="<P>",
        is_merged=False,
    )

    assert result == "all"
# ==========================================================
# Edge cases (possible break points)
# ==========================================================
def test_recursive_replacement_stall():
    gwpm = GeneralWorkPathManager(
        [
            ["?"],
        ],
        placeholders=["?"],
        path="./?/",
    )

    with pytest.raises(DependencyLoopError):
        gwpm.resolve_path(
            [0],
            recursive=True,
        )
def test_deep_dependency_loop():
    gwpm = GeneralWorkPathManager(
        [
            ["!"],
            ["$"],
            ["?"],
        ],
        placeholders=["?", "!", "$"],
    )

    with pytest.raises(DependencyLoopError):
        gwpm._check_loop_placeholders()
def test_recursive_replacement_max_depth():
    gwpm = GeneralWorkPathManager(
        [
            ["??"],
        ],
        placeholders=["?"],
        path="./?/",
    )

    with pytest.raises(DependencyLoopError):
        gwpm.resolve_path(
            [0],
            recursive=True,
        )
def test_reference_variable_roundtrip():
    rv = ReferenceVariable(
        [["a"], ["b"]],
        0,
    )

    reconstructed = (
        ReferenceVariable.from_dict(
            rv.to_dict()
        )
    )

    assert reconstructed.values == rv.values
    assert (
        reconstructed.reference_position
        == rv.reference_position
    )
# ==========================================================
# Basic tests for gwpm properties.
# ==========================================================
def test_getitem_invalid_type():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    with pytest.raises(TypeError):
        gwpm[1.5]
def test_normalize_index_invalid_type():
    gwpm = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )

    with pytest.raises(PathResolutionError):
        gwpm._normalize_index("A")
def test_inequality():
    gwpm1 = GeneralWorkPathManager(
        [["A"]],
        placeholders=["?"],
    )
    gwpm2 = GeneralWorkPathManager(
        [["B"]],
        placeholders=["?"],
    )
    assert gwpm1 != gwpm2
def test_reference_variable_not_contains():
    rv = ReferenceVariable(
        [["a"], ["b"]],
        0,
    )

    assert ["z"] not in rv
def test_iter_paths_content():
    gwpm = GeneralWorkPathManager(
        [
            ["Li", "Na"],
            ["300K"],
        ],
        placeholders=["?", "!"],
        variable_names=[
            "element",
            "temperature",
        ],
        path="./?/!/",
    )

    data = list(gwpm.iter_paths())

    assert data[0]["element"] == "Li"
    assert data[1]["element"] == "Na"
@pytest.mark.parametrize("value", ["None", "NONE", "none"])
def test_init_file_none_case_insensitive(value):
    gwpm = GeneralWorkPathManager(
        list_of_variables=[["A"]],
        placeholders=["!"],
        file=value,
    )

    assert gwpm.file == ""
def test_init_verbose_prints_message(capsys):
    GeneralWorkPathManager(
        list_of_variables=[["A"]],
        placeholders=["!"],
        verbose=True,
    )

    captured = capsys.readouterr()

    assert captured.out == "GeneralWorkPathManager initialized.\n"
# ==========================================================
# GWPM with ReferenceVariable.
# ==========================================================
def test_resolve_reference_variable_indices():
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
        placeholders=["?", "!"],
        variable_names=[
            "temperature",
            "structure",
        ],
        path="./?/!/",
    )

    result = gwpm.resolve(
        temperature=1,
        structure=0,
    )

    assert result == Path("./600K/hcp/")

