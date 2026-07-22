import pytest
from unittest.mock import patch
from gwpm.utils import parse_index_option, detect_structure_size, litteral_str, getnonemptylist, _numpy_to_list_recursive, parse_lammps_dump
from gwpm import (
    check_folder,
    variable_to_string
)
import numpy as np

#### parse_lammps_dump
def test_parse_lammps_dump(tmp_path):
    dump = tmp_path / "dump.lammpstrj"

    dump.write_text(
        "ITEM: TIMESTEP\n"
        "0\n"
        "ITEM: NUMBER OF ATOMS\n"
        "2\n"
        "ITEM: BOX BOUNDS pp pp pp\n"
        "0 10\n"
        "0 10\n"
        "0 10\n"
        "ITEM: ATOMS id type x y z\n"
        "2 2 1.0 1.0 1.0\n"
        "1 1 0.0 0.0 0.0\n"
    )

    atoms = parse_lammps_dump(
        str(dump),
        {1: "Li", 2: "O"},
        ":",
    )

    assert len(atoms) == 1
    assert atoms[0].get_chemical_symbols() == ["Li", "O"]
def test_parse_lammps_dump_with_forces(tmp_path):
    dump = tmp_path / "dump_force.lammpstrj"

    dump.write_text(
        "ITEM: TIMESTEP\n"
        "0\n"
        "ITEM: NUMBER OF ATOMS\n"
        "1\n"
        "ITEM: BOX BOUNDS pp pp pp\n"
        "0 10\n"
        "0 10\n"
        "0 10\n"
        "ITEM: ATOMS id type x y z fx fy fz\n"
        "1 1 0 0 0 1.0 2.0 3.0\n"
    )

    atoms = parse_lammps_dump(
        str(dump),
        {1: "Li"},
    )

    assert len(atoms) == 1
def test_parse_lammps_dump_unknown_atom_type(tmp_path):
    dump = tmp_path / "bad.lammpstrj"

    dump.write_text(
        "ITEM: TIMESTEP\n"
        "0\n"
        "ITEM: NUMBER OF ATOMS\n"
        "1\n"
        "ITEM: BOX BOUNDS pp pp pp\n"
        "0 10\n"
        "0 10\n"
        "0 10\n"
        "ITEM: ATOMS id type x y z\n"
        "1 99 0 0 0\n"
    )

    with pytest.raises(ValueError):
        parse_lammps_dump(
            str(dump),
            {1: "Li"},
        )
#### parse_index_option
def test_parse_index_option_int():
    assert parse_index_option(1, [10, 20, 30]) == [20]
def test_parse_index_option_int_out_of_range():
    assert parse_index_option(10, [10, 20, 30]) == []
def test_parse_index_option_slice():
    assert parse_index_option("1:", [10, 20, 30]) == [20, 30]
def test_parse_index_option_invalid_type():
    assert parse_index_option(None, [10, 20, 30]) == []
#### detect_structure_size
def test_detect_structure_size(tmp_path):
    dump = tmp_path / "dump.lammpstrj"

    dump.write_text(
        "ITEM: TIMESTEP\n"
        "0\n"
        "ITEM: NUMBER OF ATOMS\n"
        "1\n"
        "ITEM: TIMESTEP\n"
        "1\n"
        "ITEM: NUMBER OF ATOMS\n"
        "1\n"
    )

    sizes = detect_structure_size(str(dump))

    assert len(sizes) == 2
#### variable_to_string
def test_variable_to_string_list():
    assert variable_to_string([1, 2, 3]) == "1 2 3"
def test_variable_to_string_matrix():
    assert variable_to_string([[1, 2], [3, 4]]) == "1 2\n3 4"
def test_variable_to_string_matrix_custom():
    result = variable_to_string(
        [[1, 2], [3, 4]],
        mode="matrix_2-1",
    )
    assert "\n" in result
def test_variable_to_string_bool_f90():
    assert variable_to_string(True, mode="F90") == ".TRUE."
    assert variable_to_string(False, mode="F90") == ".FALSE."
def test_variable_to_string_bool():
    assert variable_to_string(True) == "True"
def test_variable_to_string_literal_string():
    assert (
        variable_to_string(
            "abc",
            litteral_string=True,
        )
        == "'abc'"
    )
def test_variable_to_string_int():
    assert variable_to_string(12, leading_zero=4) == "0012"
def test_variable_to_string_float_trail():
    assert variable_to_string(
        1.0,
        trailing_zero=3,
        float_trail=True,
    ) == "1.000"
def test_variable_to_string_float_scientific():
    result = variable_to_string(
        1e-3,
        float_trail=True,
        trailing_zero=3,
    )

    assert result.startswith("0.")
def test_variable_to_string_scientific():
    result = variable_to_string(
        1e-5,
        float_trail=True,
        trailing_zero=6,
    )
    assert isinstance(result, str)
def test_variable_to_string_scientific_positive():
    result = variable_to_string(1e3)
    assert isinstance(result, str)
def test_variable_to_string_float_integer():
    assert variable_to_string(
        1.0,
        float_trail=True,
        trailing_zero=3,
    ) == "1.000"
def test_variable_to_string_float_positive_exponent():
    result = variable_to_string(2e5)
    assert result == "200000.0"
def test_variable_to_string_scientific_no_float_trail():
    result = variable_to_string(1e-5)

    assert isinstance(result, str)
    assert "e" not in result
from ase.cell import Cell
def test_variable_to_string_cell():
    cell = Cell([[1,0,0],[0,1,0],[0,0,1]])

    result = variable_to_string(cell)

    assert "1" in result
def test_variable_to_string_warning():
    class Dummy:
        pass

    with pytest.warns(SyntaxWarning):
        variable_to_string(Dummy())
def test_variable_to_string_float_non_integer_with_padding():
    result = variable_to_string(
        1.23,
        trailing_zero=6,
    )
    assert result == "1.2300"
def test_variable_to_string_float_non_integer():
    result = variable_to_string(1.23)

    assert result == "1.23"
def test_variable_to_string_positive_exponent_branch():
    result = variable_to_string(1e20)
    assert result == "100000000000000000000.00000000000000000000"
#### litteral_string
def test_litteral_str_already_quoted():
    assert litteral_str("'abc'") == "'abc'"
def test_litteral_str_verbose(capsys):
    result = litteral_str("'abc'", verbose=True)

    captured = capsys.readouterr()

    assert result == "'abc'"
    assert "Nothing to do." in captured.out
def test_litteral_str():
    assert litteral_str("abc") == "'abc'"
### getnonemptylist
def test_getnonemptylist():
    result = getnonemptylist(
        " a   b   c ",
        " ",
    )

    assert result == ["a", "b", "c"]
###### _numpy_to_list_recursive
def test_numpy_to_list_recursive_array():
    arr = np.array([1, 2, 3])
    assert _numpy_to_list_recursive(arr) == [1, 2, 3]
def test_numpy_to_list_recursive_nested():
    obj = [
        np.array([1, 2]),
        (np.array([3, 4]),),
    ]

    result = _numpy_to_list_recursive(obj)

    assert result == [[1, 2], [[3, 4]]]
def test_numpy_to_list_recursive_scalar():
    assert _numpy_to_list_recursive(42) == 42
#### check_folder
def test_check_folder_creates_folder(tmp_path, capsys):
    folder = tmp_path / "new_folder"

    check_folder(str(folder))

    assert folder.is_dir()

    captured = capsys.readouterr()
    assert "Creating folder(s) following" in captured.out
def test_check_folder_existing_folder(tmp_path, capsys):
    folder = tmp_path / "existing"
    folder.mkdir()

    check_folder(str(folder))

    assert folder.is_dir()

    captured = capsys.readouterr()
    assert captured.out == ""

