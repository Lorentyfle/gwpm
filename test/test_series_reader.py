import pandas as pd
import pytest
from gwpm.src.series_reader import (
    PlaceholderSeries,
    BaseSeriesReader,
    CSVReader,
    FunctionReader,
    LammpsLogReader,
    ThermoLogReader,
)
### ASE reader test using ASE for testing.
from unittest.mock import patch
from gwpm.src.series_reader import ASEReader
# ==========================================================
# PlaceholderSeries
# ==========================================================
def test_placeholder_series_creation(tmp_path):
    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series.placeholder == "["
    assert series.folder == str(tmp_path)
def test_placeholder_series_invalid_placeholder_count():
    with pytest.raises(ValueError):
        PlaceholderSeries("[_[.txt")
def test_placeholder_series_empty_directory(tmp_path):
    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert len(series) == 0
    assert series.values == []
def test_placeholder_series_values(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000100.txt").touch()
    (tmp_path / "000050.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series.values == [1, 50, 100]
def test_placeholder_series_width(tmp_path):
    (tmp_path / "000123.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series._width == 6
def test_placeholder_series_names(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000002.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series.names == [
        "000001.txt",
        "000002.txt",
    ]
def test_placeholder_series_paths(tmp_path):
    file = tmp_path / "000001.txt"
    file.touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series.paths == [str(file)]
def test_placeholder_series_first_last(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000010.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series.first.endswith("000001.txt")
    assert series.last.endswith("000010.txt")
def test_placeholder_series_exists(tmp_path):
    (tmp_path / "000010.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series.exists(10)
    assert not series.exists(15)
def test_placeholder_series_index(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000100.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert series.index(100) == 1
def test_placeholder_series_get_path(tmp_path):
    (tmp_path / "000001.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    expected = str(tmp_path / "000300.txt")

    assert series.get_path(300) == expected
def test_placeholder_series_contains(tmp_path):
    (tmp_path / "000001.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert 1 in series
    assert 10 not in series
def test_placeholder_series_iter(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000002.txt").touch()

    series = PlaceholderSeries(
        str(tmp_path / "[.txt")
    )

    assert list(series) == [1, 2]
def test_placeholder_series_to_dict():
    series = PlaceholderSeries("./[.txt")

    assert series.to_dict() == {
        "pattern": "./[.txt",
        "placeholder": "[",
    }
def test_placeholder_series_from_dict():
    series = PlaceholderSeries.from_dict(
        {
            "pattern": "./[.txt",
            "placeholder": "[",
        }
    )

    assert series.pattern == "./[.txt"
    assert series.placeholder == "["
def test_placeholder_series_equality():
    s1 = PlaceholderSeries("./[.txt")
    s2 = PlaceholderSeries("./[.txt")
    s3 = PlaceholderSeries("./@.txt", placeholder="@")

    assert s1 == s2
    assert s1 != s3
# ==========================================================
# Base Reader
# ==========================================================
class DummyReader(BaseSeriesReader):

    def read(self, path):
        return path.upper()
def test_base_reader_read_all(tmp_path):
    (tmp_path / "000001.txt").touch()
    (tmp_path / "000002.txt").touch()
### CSV reader test
def test_csv_reader_kwargs(tmp_path):

    csv_file = tmp_path / "test.csv"

    csv_file.write_text(
        "A;B\n1;2\n3;4\n"
    )

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
def test_function_reader_lambda():

    reader = FunctionReader(
        lambda x: x * 2
    )

    assert reader.read(4) == 8
### LAMMPSLOGREADER
def test_function_reader_lambda():

    reader = FunctionReader(
        lambda x: x * 2
    )

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

    reader = ThermoLogReader(
        timestep_fs=2.0
    )

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
@patch("ml_dft_gw.gw.paths.series_reader.read")
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

    merged = reader.merge([
        traj1,
        traj2,
        traj3,
    ])

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
@patch("ml_dft_gw.gw.paths.series_reader.read")
def test_ase_reader_read_all(mock_read, tmp_path):

    (tmp_path / "000001.xyz").touch()
    (tmp_path / "000002.xyz").touch()

    mock_read.return_value = ["atoms"]

    series = PlaceholderSeries(
        str(tmp_path / "[.xyz")
    )

    reader = ASEReader()

    result = reader.read_all(series)

    assert len(result) == 2

    assert mock_read.call_count == 2
@patch("ml_dft_gw.gw.paths.series_reader.read")
def test_ase_reader_read_merged(mock_read, tmp_path):

    (tmp_path / "000001.xyz").touch()
    (tmp_path / "000002.xyz").touch()

    mock_read.side_effect = [
        ["a", "b"],
        ["c"],
    ]

    series = PlaceholderSeries(
        str(tmp_path / "[.xyz")
    )

    reader = ASEReader()

    result = reader.read_merged(series)

    assert result == [
        "a",
        "b",
        "c",
    ]

