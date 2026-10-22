import pandas as pd
import pytest
from gwpm import (
    PlaceholderSeries,
    BaseSeriesReader,
    CSVReader,
    FunctionReader,
    LammpsLogReader,
    LammpsDumpReader,
    ThermoLogReader,
    PlaceHolderSeriesError,
    BaseSeriesReaderError,
)

### ASE reader test using ASE for testing.
from unittest.mock import patch
from ase import Atoms
from gwpm import ASEReader, PymatgenReader


def write_dump(path, columns, frames, box="pp pp pp", bounds=("0 1",) * 3):
    """Write a LAMMPS dump, one list of atom lines per frame."""
    with open(path, "w") as f:
        for step, atoms in enumerate(frames):
            f.write(f"ITEM: TIMESTEP\n{step}\nITEM: NUMBER OF ATOMS\n{len(atoms)}\n")
            f.write(f"ITEM: BOX BOUNDS {box}\n" + "\n".join(bounds) + "\n")
            f.write(f"ITEM: ATOMS {columns}\n" + "\n".join(atoms) + "\n")


## Import tests.
def test_require_ase(monkeypatch):
    import gwpm.series_reader as sr

    monkeypatch.setattr(sr, "read", None)
    with pytest.raises(ImportError):
        sr._require_ase()


def test_require_pymatgen(monkeypatch):
    import gwpm.series_reader as sr

    monkeypatch.setattr(sr, "Structure", None)
    with pytest.raises(ImportError):
        sr._require_pymatgen()


# ==========================================================
# PlaceholderSeries
# ==========================================================
def test_placeholder_series_values_missing_folder(tmp_path):
    series = PlaceholderSeries(str(tmp_path / "does_not_exist" / "<ID>.txt"))
    assert series.values == []


class DummyReader(BaseSeriesReader):
    def read(self, path):
        return path


def test_base_series_reader_repr():
    reader = DummyReader()
    assert repr(reader) == "DummyReader()"


def test_placeholder_series_creation(tmp_path):
    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series.placeholder == "<ID>"
    assert series.folder == str(tmp_path)


def test_placeholder_series_invalid_placeholder_count():
    with pytest.raises(PlaceHolderSeriesError):
        PlaceholderSeries("<ID>_<ID>.txt")


def test_placeholder_series_empty_directory(tmp_path):
    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert len(series) == 0
    assert series.values == []


def test_placeholder_series_values(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000100.txt").touch()
    (tmp_path / "000050.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series.values == [1, 50, 100]


def test_placeholder_series_width(tmp_path):
    (tmp_path / "000123.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series._width == 6


def test_placeholder_series_names(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000002.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series.names == [
        "000001.txt",
        "000002.txt",
    ]


def test_placeholder_series_paths(tmp_path):
    file = tmp_path / "000001.txt"
    file.touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series.paths == [str(file)]


def test_placeholder_series_first_last(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000010.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series.first.endswith("000001.txt")
    assert series.last.endswith("000010.txt")


def test_placeholder_series_exists(tmp_path):
    (tmp_path / "000010.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series.exists(10)
    assert not series.exists(15)


def test_placeholder_series_index(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000100.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert series.index(100) == 1


def test_placeholder_series_get_path(tmp_path):
    (tmp_path / "000001.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    expected = str(tmp_path / "000300.txt")

    assert series.get_path(300) == expected


def test_placeholder_series_contains(tmp_path):
    (tmp_path / "000001.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert 1 in series
    assert 10 not in series


def test_placeholder_series_iter(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000002.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    assert list(series) == [1, 2]


def test_placeholder_series_to_dict():
    series = PlaceholderSeries("./<ID>.txt")

    assert series.to_dict() == {
        "pattern": "./<ID>.txt",
        "placeholder": "<ID>",
    }


def test_placeholder_series_from_dict():
    series = PlaceholderSeries.from_dict(
        {
            "pattern": "./<ID>.txt",
            "placeholder": "<ID>",
        }
    )

    assert series.pattern == "./<ID>.txt"
    assert series.placeholder == "<ID>"


def test_placeholder_series_equality():
    s1 = PlaceholderSeries("./<ID>.txt")
    s2 = PlaceholderSeries("./<ID>.txt")
    s3 = PlaceholderSeries("./@.txt", placeholder="@")

    assert s1 == s2
    assert s1 != s3


def test_placeholder_series_repr(tmp_path):
    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))
    result = repr(series)
    assert "PlaceholderSeries" in result
    assert "pattern=" in result


def test_placeholder_series_str(tmp_path):
    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    text = str(series)

    assert "PlaceholderSeries" in text
    assert "pattern" in text
    assert "folder" in text
    assert "width" in text
    assert "n_values" in text


def test_placeholder_series_getitem(tmp_path):
    (tmp_path / "001.txt").touch()
    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))
    assert series[0] == 1


def test_placeholder_series_eq_returns_false_for_other_object():
    series = PlaceholderSeries("./<ID>.txt")
    assert series.__eq__(123) is False


# ==========================================================
# Base Reader
# ==========================================================
def test_base_series_reader_str():
    class DummyReader(BaseSeriesReader):
        def read(self, path):
            return path

    reader = DummyReader()
    assert str(reader) == "DummyReader()"


def test_base_series_reader_abstract_read():
    class DummyReader(BaseSeriesReader):
        def read(self, path):
            return path

    reader = DummyReader()
    assert BaseSeriesReader.read(reader, "some_path") is None


def test_base_reader_read_all(tmp_path):
    class DummyReader(BaseSeriesReader):
        def read(self, path):
            return path.upper()

    (tmp_path / "000001.txt").touch()
    (tmp_path / "000002.txt").touch()


def test_base_series_reader_merge():
    class DummyReader(BaseSeriesReader):
        def read(self, path):
            return path

    reader = DummyReader()
    data = [1, 2, 3]
    assert reader.merge(data) == data


### CSV reader test
def test_csv_reader_kwargs(tmp_path):
    csv_file = tmp_path / "test.csv"

    csv_file.write_text("A;B\n1;2\n3;4\n")

    reader = CSVReader(sep=";")

    df = reader.read(csv_file)

    assert list(df.columns) == ["A", "B"]
    assert len(df) == 2


def test_csv_reader_repr():
    reader = CSVReader(sep=";")

    assert "CSVReader" in repr(reader)
    assert "sep" in repr(reader)


def test_csv_reader_str():
    reader = CSVReader()

    assert str(reader) == repr(reader)


def test_csv_reader_merge():
    reader = CSVReader()
    result = reader.merge(
        [
            pd.DataFrame({"x": [1]}),
            pd.DataFrame({"x": [2]}),
        ]
    )
    assert len(result) == 2


## Function reader test
def test_function_reader_repr():
    def my_reader(path):
        return path

    reader = FunctionReader(my_reader)

    assert "my_reader" in repr(reader)


def test_function_reader_str():
    def my_reader(path):
        return path

    reader = FunctionReader(my_reader)

    assert str(reader) == repr(reader)


### Lammpsdumpreader
def test_lammps_dump_reader_init_custom_arguments():
    reader = LammpsDumpReader(
        Z_of_type={"a": "b"},
        index_atom=0,
    )
    assert reader.Z_of_type == {"a": "b"}
    assert reader.index_atom == 0


def test_lammps_dump_reader_repr():
    reader = LammpsDumpReader(Z_of_type={1: "Li"}, index_atom=":")

    text = repr(reader)

    assert "LammpsDumpReader" in text
    assert "Li" in text


def test_lammps_dump_reader_str():
    reader = LammpsDumpReader(
        Z_of_type={1: "Li"},
        index_atom=-1,
    )

    assert str(reader) == repr(reader)


def test_lammps_dump_reader_read():
    with patch("gwpm.series_reader.parse_lammps_dump", return_value=["dummy"]) as mock:
        reader = LammpsDumpReader(
            Z_of_type={1: "Li"},
            index_atom=-1,
        )

        result = reader.read("dump.lammpstrj")

        mock.assert_called_once_with(
            "dump.lammpstrj",
            {1: "Li"},
            -1,
        )

        assert result == ["dummy"]


def test_lammps_dump_reader_merge():
    reader = LammpsDumpReader()

    merged = reader.merge(
        [
            [Atoms("H")],
            [Atoms("He")],
        ]
    )

    assert len(merged) == 2


### LAMMPSLOGREADER
def test_function_reader_lambda():
    reader = FunctionReader(lambda x: x * 2)

    assert reader.read(4) == 8


def test_lammps_log_reader_str():
    reader = LammpsLogReader()

    assert str(reader) == "LammpsLogReader()"


def test_lammps_log_reader_read(tmp_path):
    logfile = tmp_path / "log.lammps"

    logfile.write_text(
        """LAMMPS
Step Temp PotEng KinEng TotEng Press
0 300 -10 5 -5 0
1 301 -11 5 -6 0
Loop time
"""
    )

    reader = LammpsLogReader()

    df = reader.read(logfile)

    assert len(df) == 2

    assert list(df.columns) == [
        "Step",
        "Temp",
        "PotEng",
        "KinEng",
        "TotEng",
        "Press",
    ]


def test_lammps_log_reader_merge_empty():
    reader = LammpsLogReader()

    merged = reader.merge([])

    assert merged.empty


def test_lammps_log_reader_merge_steps():
    reader = LammpsLogReader()

    df1 = pd.DataFrame(
        {
            "Step": [0, 1],
            "Temp": [1, 1],
            "PotEng": [1, 1],
            "KinEng": [1, 1],
            "TotEng": [1, 1],
            "Press": [1, 1],
        }
    )

    df2 = pd.DataFrame(
        {
            "Step": [0, 1],
            "Temp": [2, 2],
            "PotEng": [2, 2],
            "KinEng": [2, 2],
            "TotEng": [2, 2],
            "Press": [2, 2],
        }
    )

    merged = reader.merge([df1, df2])

    assert list(merged["Step"]) == [0, 1, 1, 2]


### Thermolog reader
def test_thermo_log_reader_repr():
    reader = ThermoLogReader()

    assert "ThermoLogReader" in repr(reader)


def test_thermo_log_reader_str():
    reader = ThermoLogReader()

    assert str(reader) == repr(reader)


def test_thermo_log_reader_read(tmp_path):
    logfile = tmp_path / "thermo.log"

    logfile.write_text(
        """# step E_pot(eV) E_kin(eV)
0 -10 2
1 -11 2
"""
    )

    reader = ThermoLogReader()

    df = reader.read(logfile)

    assert "E_tot(eV)" in df.columns

    assert df["E_tot(eV)"].tolist() == [
        -8,
        -9,
    ]


def test_thermo_log_reader_with_time(tmp_path):
    logfile = tmp_path / "thermo.log"

    logfile.write_text(
        """# step E_pot(eV) E_kin(eV)
0 -10 2
1 -11 2
"""
    )

    reader = ThermoLogReader(timestep_fs=2.0)

    df = reader.read(logfile)

    assert "time_fs" in df.columns
    assert "time_ps" in df.columns

    assert df["time_fs"].tolist() == [0.0, 2.0]


def test_thermo_log_reader_merge_empty():
    reader = ThermoLogReader()

    merged = reader.merge([])

    assert merged.empty


def test_thermo_log_reader_merge_steps():
    reader = ThermoLogReader()

    df1 = pd.DataFrame(
        {
            "step": [0, 1],
            "E_pot(eV)": [0, 0],
            "E_kin(eV)": [0, 0],
        }
    )

    df2 = pd.DataFrame(
        {
            "step": [0, 1],
            "E_pot(eV)": [0, 0],
            "E_kin(eV)": [0, 0],
        }
    )

    merged = reader.merge([df1, df2])

    assert list(merged["step"]) == [0, 1, 1, 2]


## ASE Reader
def test_ase_reader_init():
    reader = ASEReader()

    assert reader.index == ":"


def test_ase_reader_custom_index():
    reader = ASEReader(index="::10")

    assert reader.index == "::10"


def test_ase_reader_repr():
    reader = ASEReader(index=":")

    assert repr(reader) == "ASEReader(index=':')"


def test_ase_reader_str():
    reader = ASEReader(index="::5")

    assert str(reader) == repr(reader)


@patch("gwpm.series_reader.read")
def test_ase_reader_read(mock_read):
    fake_atoms = ["atoms"]

    mock_read.return_value = fake_atoms

    reader = ASEReader(index=":")

    result = reader.read("test.xyz")

    mock_read.assert_called_once_with(
        "test.xyz",
        ":",
    )

    assert result == fake_atoms


def test_ase_reader_merge():
    reader = ASEReader()

    traj1 = ["a", "b"]
    traj2 = ["c"]
    traj3 = ["d", "e"]

    merged = reader.merge(
        [
            traj1,
            traj2,
            traj3,
        ]
    )

    assert merged == [
        "a",
        "b",
        "c",
        "d",
        "e",
    ]


def test_ase_reader_merge_empty():
    reader = ASEReader()

    merged = reader.merge([])

    assert merged == []


@patch("gwpm.series_reader.read")
def test_ase_reader_read_all(mock_read, tmp_path):
    (tmp_path / "000001.xyz").touch()
    (tmp_path / "000002.xyz").touch()

    mock_read.return_value = ["atoms"]

    series = PlaceholderSeries(str(tmp_path / "<ID>.xyz"))

    reader = ASEReader()

    result = reader.read_all(series)

    assert len(result) == 2

    assert mock_read.call_count == 2


@patch("gwpm.series_reader.read")
def test_ase_reader_read_merged(mock_read, tmp_path):
    (tmp_path / "000001.xyz").touch()
    (tmp_path / "000002.xyz").touch()

    mock_read.side_effect = [
        ["a", "b"],
        ["c"],
    ]

    series = PlaceholderSeries(str(tmp_path / "<ID>.xyz"))

    reader = ASEReader()

    result = reader.read_merged(series)

    assert result == [
        "a",
        "b",
        "c",
    ]


### PymatgenReader
def test_pymatgen_reader_init():
    def dummy_reader(path):
        return path

    reader = PymatgenReader(dummy_reader)

    assert reader.read_function is dummy_reader
    assert reader.kwargs == {}


def test_pymatgen_reader_init_kwargs():
    def dummy_reader(path, primitive=False):
        return primitive

    reader = PymatgenReader(
        dummy_reader,
        primitive=True,
    )

    assert reader.kwargs == {"primitive": True}


def test_pymatgen_reader_non_callable():
    with pytest.raises(TypeError):
        PymatgenReader("not_callable")


def test_pymatgen_reader_repr():
    def dummy_reader(path):
        return path

    reader = PymatgenReader(dummy_reader)

    assert repr(reader) == "PymatgenReader(read_function='dummy_reader', kwargs={})"


def test_pymatgen_reader_str():
    def dummy_reader(path):
        return path

    reader = PymatgenReader(dummy_reader)

    assert str(reader) == repr(reader)


def test_pymatgen_reader_read():
    def dummy_reader(path):
        return f"reading:{path}"

    reader = PymatgenReader(dummy_reader)

    assert reader.read("file.cif") == "reading:file.cif"


def test_pymatgen_reader_read_kwargs():
    def dummy_reader(path, primitive=False):
        return {
            "path": path,
            "primitive": primitive,
        }

    reader = PymatgenReader(
        dummy_reader,
        primitive=True,
    )

    result = reader.read("test.cif")

    assert result == {
        "path": "test.cif",
        "primitive": True,
    }


def test_pymatgen_reader_merge():
    def dummy_reader(path):
        return path

    reader = PymatgenReader(dummy_reader)

    data = ["a", "b", "c"]

    assert reader.merge(data) == data


def test_pymatgen_reader_read_all():
    class DummySeries:
        paths = [
            "file_1",
            "file_2",
            "file_3",
        ]

    def dummy_reader(path):
        return path.upper()

    reader = PymatgenReader(dummy_reader)
    assert reader.read_all(DummySeries()) == [
        "FILE_1",
        "FILE_2",
        "FILE_3",
    ]


def test_pymatgen_reader_read_merged():
    class DummySeries:
        paths = [
            "file_1",
            "file_2",
        ]

    def dummy_reader(path):
        return path.upper()

    reader = PymatgenReader(dummy_reader)

    assert reader.read_merged(DummySeries()) == [
        "FILE_1",
        "FILE_2",
    ]


# ==========================================================
# Missing files (issue #1).
# ==========================================================
def test_read_all_missing_folder(tmp_path):
    series = PlaceholderSeries(str(tmp_path / "missing" / "log_<ID>.lammps"))

    with pytest.raises(BaseSeriesReaderError, match="Folder not found"):
        LammpsLogReader().read_merged(series)


def test_read_all_no_matching_file(tmp_path):
    (tmp_path / "other.txt").touch()
    series = PlaceholderSeries(str(tmp_path / "log_<ID>.lammps"))

    with pytest.raises(BaseSeriesReaderError, match="No file matching"):
        LammpsLogReader().read_merged(series)


def test_lammps_log_reader_no_thermo_table(tmp_path):
    path = tmp_path / "log.lammps"
    path.write_text("LAMMPS (2 Aug 2023)\nERROR: something\n")

    with pytest.raises(BaseSeriesReaderError, match="No thermo table"):
        LammpsLogReader().read(str(path))


# ==========================================================
# Reading errors.
# ==========================================================
def test_placeholder_series_unpadded_paths(tmp_path):
    for i in [1, 2, 10]:
        (tmp_path / f"log_{i}.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "log_<ID>.txt"))

    assert series.names == ["log_1.txt", "log_2.txt", "log_10.txt"]
    assert series.get_path(20) == str(tmp_path / "log_20.txt")


def test_placeholder_series_duplicate_value(tmp_path):
    (tmp_path / "1.txt").touch()
    (tmp_path / "01.txt").touch()

    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))

    with pytest.raises(PlaceHolderSeriesError, match="found twice"):
        series.values


def test_placeholder_series_placeholder_in_folder(tmp_path):
    with pytest.raises(PlaceHolderSeriesError, match="last part"):
        PlaceholderSeries(str(tmp_path / "run_<ID>" / "x.txt"))


def test_ase_reader_merge_int_index():
    reader = ASEReader(index=-1)
    a, b = Atoms("Cu"), Atoms("Al")

    assert reader.merge([a, b]) == [a, b]


def test_lammps_dump_reader_no_z_of_type(tmp_path):
    path = tmp_path / "dump.lammpstrj"
    write_dump(path, "id type x y z", [["1 1 0 0 0"]])

    with pytest.raises(BaseSeriesReaderError, match="Z_of_type"):
        LammpsDumpReader().read(str(path))


@patch("gwpm.series_reader.parse_lammps_dump", return_value=[])
def test_lammps_dump_reader_no_structure(mock_parse):
    with pytest.raises(BaseSeriesReaderError, match="No structure"):
        LammpsDumpReader(Z_of_type={1: "Li"}, index_atom=5).read("dump.lammpstrj")


def test_lammps_log_reader_several_runs(tmp_path):
    path = tmp_path / "log.lammps"
    path.write_text(
        """Step Temp PotEng
0 300 -10
100 301 -11
Loop time of 1.0
Step Temp PotEng Press
100 301 -11 1
WARNING: something not fatal
200 302 -12 2
Loop time of 1.0
"""
    )

    df = LammpsLogReader().read(str(path))

    assert df["Step"].tolist() == [0, 100, 100, 200]
    assert list(df.columns) == ["Step", "Temp", "PotEng", "Press"]
    assert df["Press"].isna().tolist() == [True, True, False, False]


def test_lammps_log_reader_error(tmp_path):
    path = tmp_path / "log.lammps"
    path.write_text("Step Temp\n0 300\nERROR: Lost atoms\n")

    with pytest.raises(BaseSeriesReaderError, match="Lost atoms"):
        LammpsLogReader().read(str(path))


def test_lammps_log_reader_not_closed(tmp_path):
    path = tmp_path / "log.lammps"
    path.write_text("Step Temp\n0 300\n10 301\n")

    with pytest.raises(BaseSeriesReaderError, match="not closed"):
        LammpsLogReader().read(str(path))


def test_lammps_log_reader_wrong_line(tmp_path):
    path = tmp_path / "log.lammps"
    path.write_text("Step Temp\n0 300 1\nLoop time\n")

    with pytest.raises(BaseSeriesReaderError, match="Line 2"):
        LammpsLogReader().read(str(path))


def test_thermo_log_reader_missing_columns(tmp_path):
    path = tmp_path / "thermo.log"
    path.write_text("#step T\n0 300\n")

    with pytest.raises(BaseSeriesReaderError, match="E_pot"):
        ThermoLogReader().read(str(path))


def test_thermo_log_reader_missing_step_with_timestep(tmp_path):
    path = tmp_path / "thermo.log"
    path.write_text("#E_pot(eV) E_kin(eV)\n0 0\n")

    with pytest.raises(BaseSeriesReaderError, match="step"):
        ThermoLogReader(timestep_fs=2.0).read(str(path))


# ==========================================================
# Stress test fixes.
# ==========================================================
def test_placeholder_series_sees_new_files(tmp_path):
    (tmp_path / "1.txt").touch()
    series = PlaceholderSeries(str(tmp_path / "<ID>.txt"))
    assert series.values == [1]

    (tmp_path / "2.txt").touch()

    assert series.values == [1, 2]
    assert series.last == str(tmp_path / "2.txt")


def test_placeholder_series_path_object(tmp_path):
    (tmp_path / "1.txt").touch()

    assert PlaceholderSeries(tmp_path / "<ID>.txt").values == [1]


def test_placeholder_series_folder_names(tmp_path):
    (tmp_path / "run_1").mkdir()

    assert PlaceholderSeries(str(tmp_path / "run_<ID>") + "/").names == ["run_1"]


def test_lammps_log_reader_skips_text_lines(tmp_path):
    path = tmp_path / "log.lammps"
    path.write_text(
        "Step Temp\n0 300\nSHAKE stats (type/ave/delta/count) on step 0\n10 301\nLoop time\n"
    )

    assert LammpsLogReader().read(str(path))["Step"].tolist() == [0, 10]


def test_lammps_dump_variable_number_of_atoms(tmp_path):
    path = tmp_path / "dump.lammpstrj"
    frames = [
        [f"{i + 1} 1 {k} 0 0" for i in range(n)] for k, n in enumerate([1, 2, 1, 2])
    ]
    write_dump(path, "id type x y z", frames)

    last = LammpsDumpReader({1: "Li"}, -1).read(str(path))
    every_other = LammpsDumpReader({1: "Li"}, "1::2").read(str(path))

    assert [len(a) for a in last] == [2]
    assert last[0].positions[:, 0].tolist() == [3.0, 3.0]
    assert [len(a) for a in every_other] == [2, 2]


def test_lammps_dump_string_index(tmp_path):
    path = tmp_path / "dump.lammpstrj"
    write_dump(path, "id type x y z", [[f"1 1 {k} 0 0"] for k in range(3)])

    atoms = LammpsDumpReader({1: "Li"}, "-1").read(str(path))

    assert len(atoms) == 1
    assert atoms[0].positions[0, 0] == 2.0


def test_lammps_dump_triclinic(tmp_path):
    path = tmp_path / "dump.lammpstrj"
    write_dump(
        path,
        "id type x y z",
        [["1 1 0 0 0"]],
        box="xy xz yz pp pp pp",
        bounds=("0 3 1", "0 2 0", "0 2 0"),
    )

    cell = LammpsDumpReader({1: "Li"}).read(str(path))[0].cell.array

    assert cell.tolist() == [[2.0, 0.0, 0.0], [1.0, 2.0, 0.0], [0.0, 0.0, 2.0]]


def test_lammps_dump_scaled_positions(tmp_path):
    path = tmp_path / "dump.lammpstrj"
    write_dump(path, "id type xs ys zs", [["1 1 0.5 0.5 0.5"]], bounds=("0 2",) * 3)

    atoms = LammpsDumpReader({1: "Li"}).read(str(path))[0]

    assert atoms.positions[0].tolist() == [1.0, 1.0, 1.0]


def test_lammps_dump_element_column(tmp_path):
    path = tmp_path / "dump.lammpstrj"
    write_dump(path, "id element x y z", [["1 Li 0 0 0"]])

    assert LammpsDumpReader().read(str(path))[0].get_chemical_symbols() == ["Li"]


def test_lammps_dump_no_positions(tmp_path):
    path = tmp_path / "dump.lammpstrj"
    write_dump(path, "id type vx vy vz", [["1 1 0 0 0"]])

    with pytest.raises(BaseSeriesReaderError, match="No position columns"):
        LammpsDumpReader({1: "Li"}).read(str(path))


def test_function_reader_not_callable():
    with pytest.raises(TypeError):
        FunctionReader("x")


@pytest.mark.parametrize(
    "second, expected",
    [
        ([0, 10], [0, 10, 10, 20]),
        ([10, 20], [0, 10, 10, 20]),
        ([20, 30], [0, 10, 20, 30]),
    ],
)
def test_log_merge_steps_restart_or_continue(second, expected):
    first = pd.DataFrame({"Step": [0, 10]})

    merged = LammpsLogReader().merge([first, pd.DataFrame({"Step": second})])
    thermo = ThermoLogReader().merge(
        [first.rename(columns={"Step": "step"}), pd.DataFrame({"step": second})]
    )

    assert merged["Step"].tolist() == expected
    assert thermo["step"].tolist() == expected
