from typing import List, Union, Dict, Optional
import os
import re
from pathlib import Path
from abc import ABC, abstractmethod
from functools import cached_property
import pandas as pd
## ASE
from ase import Atoms
from ase.io import read

## Utils.
from .utils import parse_lammps_dump
from .exception import (
    PlaceHolderSeriesError,
    BaseSeriesReaderError,
)

class PlaceholderSeries:
    """
    Handle a series of files or folders indexed by a single placeholder.

    Example
    -------
    pattern = "./simulations/[.lammpsdump"

    Existing files:

        000000.lammpsdump
        000100.lammpsdump
        000200.lammpsdump

    series.values

        [0, 100, 200]

    series.get_path(300)

        "./simulations/000300.lammpsdump"
    """
    __version__ = "1.0.0"
    def __init__(self,pattern: str,placeholder: str = "[",)->None:
        self.pattern = pattern
        self.placeholder = placeholder
        if pattern.count(placeholder) != 1:
            raise PlaceHolderSeriesError(
                f"Pattern must contain exactly one placeholder "
                f"('{placeholder}')."
            )
        self._regex = self._build_regex()
        self._width = self._find_width()
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"pattern='{self.pattern}', "
            f"n_values={len(self)})")
    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}\n"
            f"├── pattern     : {self.pattern}\n"
            f"├── folder      : {self.folder}\n"
            f"├── width       : {self._width}\n"
            f"└── n_values    : {len(self)}"
        )
    def __len__(self) -> int:
        return len(self.values)
    def __iter__(self):
        return iter(self.values)
    def __getitem__(self, item):
        return self.values[item]
    def __contains__(self, item) -> bool:
        return item in self.values
    def __eq__(self, other) -> bool:
        if not isinstance(other, PlaceholderSeries):
            return False
        return ( self.pattern == other.pattern and self.placeholder == other.placeholder )
    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "placeholder": self.placeholder,
        }
    @classmethod
    def from_dict(cls, data: dict):
        return cls( pattern=data["pattern"], placeholder=data["placeholder"] )
    def _build_regex(self)->re.Pattern:
        """
        Build the regular expression used to match files/folders.

        Returns
        -------
        re.Pattern
            Compiled regular expression where the placeholder is
            replaced by a numeric capture group.
        """
        name = Path(self.pattern).name
        escaped = re.escape(name)
        escaped = escaped.replace(re.escape(self.placeholder),r"(\d+)")
        return re.compile(f"^{escaped}$")
    @property
    def folder(self)->str:
        """
        Parent directory containing the matching files/folders.

        Returns
        -------
        str
            Path to the parent directory.
        """
        return str(Path(self.pattern).parent)
    def _find_width(self)->int:
        """
        Determine the width of the numeric field.

        The width is obtained from the longest matching integer found
        in the target directory.

        Returns
        -------
        int
            Number of digits used for zero-padding.
        """
        widths = []
        if not os.path.isdir(self.folder):
            return 1
        for name in os.listdir(self.folder):
            match = self._regex.match(name)
            if match:
                widths.append(len(match.group(1)))
        return max(widths) if widths else 1
    @cached_property
    def values(self)->List[int]:
        """
        Extract all integer values matching the placeholder pattern.

        Returns
        -------
        List[int]
            Sorted integer values extracted from matching file/folder
            names.

        Example
        -------
        Files:

            000005.lammpsdump
            000010.lammpsdump

        Returns:

            [5, 10]
        """
        values = []
        if not os.path.isdir(self.folder):
            return values
        for name in os.listdir(self.folder):
            match = self._regex.match(name)
            if match:
                values.append(int(match.group(1)))
        return sorted(values)
    @property
    def names(self)->List[str]:
        """
        Return matching file/folder names.

        Returns
        -------
        List[str]
            Sorted names corresponding to the discovered placeholder
            values.
        """
        return [os.path.basename(self.get_path(v)) for v in self.values]
    @property
    def paths(self)->List[str]:
        """
        Return matching file/folder paths.

        Returns
        -------
        List[str]
            Sorted absolute or relative paths corresponding to the
            discovered placeholder values.
        """
        return [ self.get_path(v) for v in self.values ]
    @property
    def first(self) -> str | None:
        """
        Return the first path in the series.
        """
        return self.paths[0] if self.paths else None
    @property
    def last(self) -> str | None:
        """
        Return the last path in the series.
        """
        return self.paths[-1] if self.paths else None
    def exists(self, value: int) -> bool:
        """
        Check whether a given series value exists.
        """
        return value in self.values
    def index(self, value: int) -> int:
        """
        Return the position of a value in the series.
        """
        return self.values.index(value)
    def get_path(self,value: int,) -> str:
        """
        Build a path corresponding to a placeholder value.

        Parameters
        ----------
        value : int
            Integer value used to replace the placeholder.

        Returns
        -------
        str
            Path generated from the pattern.

        Notes
        -----
        The numeric value is zero-padded using the width inferred from
        existing matching files/folders.
        """
        replacement = str(value).zfill(self._width)
        return self.pattern.replace( self.placeholder, replacement)
### Series Readers.
class BaseSeriesReader(ABC):
    """
    Abstract base class for reading placeholder series.

    Subclasses must implement the ``read`` method.
    
    Notes
    -----
    A reader implementation is responsible for:

    1. Reading a single file through ``read``.
    2. Optionally combining several files through ``merge``.

    The helper methods ``read_all`` and ``read_merged`` provide
    generic implementations based on these two operations.
    """
    __version__ = "1.0.0"
    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}()")
    def __str__(self) -> str:
        return self.__repr__()
    @abstractmethod
    def read(self, path:str):
        """
        Read a single file.

        Parameters
        ----------
        path : str
            Path to the file.

        Returns
        -------
        Any
            Parsed content of the file.
        """
        pass
    def read_all(self,series: PlaceholderSeries,):
        """
        Read all files belonging to a placeholder series.

        Parameters
        ----------
        series : PlaceholderSeries
            Series describing the files to read.

        Returns
        -------
        List
            List containing the result of reading each file.
        """
        return [ self.read(path) for path in series.paths ]
    def merge(self, data):
        """
        Merge the results produced by ``read_all``.

        This default implementation performs no merging and simply
        returns the input data unchanged.

        Parameters
        ----------
        data : List
            Output generated by ``read_all``.

        Returns
        -------
        Any
            By default, returns ``data`` unchanged.

        Notes
        -----
        Subclasses may override this method to provide a more
        meaningful merge operation.
        """
        return data
    def read_merged(self, series):
        """
        Read and merge all files belonging to a placeholder series.

        This method is equivalent to:

            self.merge(
                self.read_all(series)
            )

        Parameters
        ----------
        series : PlaceholderSeries
            Series describing the files to read.

        Returns
        -------
        Any
            Merged representation of all files in the series.
            The exact type depends on the reader implementation.
        """
        return self.merge(self.read_all(series))
class CSVReader(BaseSeriesReader):
    """
    Reader for CSV files using pandas.
    """
    def __init__(self,**kwargs,):
        """
        Parameters
        ----------
        **kwargs
            Additional arguments passed directly to
            ``pandas.read_csv``.
        """
        self.kwargs = kwargs
    def __repr__(self) -> str:
        return ( f"CSVReader(kwargs={self.kwargs})" )
    def __str__(self) -> str:
        return self.__repr__()
    def read(self, path:str)->pd.DataFrame:
        """
        Read a CSV file.

        Parameters
        ----------
        path : str
            Path to the CSV file.

        Returns
        -------
        pandas.DataFrame
            Loaded CSV data.
        """
        return pd.read_csv(path, **self.kwargs, )
    def merge(self, data)->pd.DataFrame:
        """
        Concatenate multiple DataFrames into a single DataFrame.

        Parameters
        ----------
        data : List[pandas.DataFrame]
            DataFrames obtained from the CSV files.

        Returns
        -------
        pandas.DataFrame
            Combined DataFrame containing all rows from every
            input DataFrame.

        Notes
        -----
        The index is reset during concatenation.
        """
        return pd.concat(data,ignore_index=True,)
class ASEReader(BaseSeriesReader):
    """
    Reader for ASE-supported structure and trajectory files.
    """
    def __init__(self,index=":",):
        """
        Parameters
        ----------
        index : str or int, optional
            ASE index specification.

            Examples:
                0
                -1
                ":"
                "::10"
            Default is ":".
        """
        self.index = index
    def __repr__(self) -> str:
        return (f"ASEReader(index={self.index!r})")
    def __str__(self) -> str:
        return self.__repr__()
    def read(self, path:str):
        """
        Read an ASE-supported file.

        Parameters
        ----------
        path : str
            Path to the file.

        Returns
        -------
        Atoms or List[Atoms]
            Structure(s) returned by ASE.
        """
        return read(path,self.index,)
    def merge(self, data)->List[Atoms]:
        """
        Merge multiple ASE trajectories into a single trajectory.

        Parameters
        ----------
        data : List[List[Atoms]]
            Structures returned by reading multiple files.

        Returns
        -------
        List[Atoms]
            Flat list containing all structures in the order
            they were read.
        """
        all_atoms = []
        for traj in data:
            all_atoms.extend(traj)
        return all_atoms
class LammpsDumpReader(BaseSeriesReader):
    """
    Reader for LAMMPS dump files using ``parse_lammps_dump``.
    """
    def __init__(self, Z_of_type=None, index_atom=":",):
        """
        Parameters
        ----------
        Z_of_type : dict, optional
            Mapping between LAMMPS atom types and atomic symbols.

            Example:

                {1: "Li", 2: "O"}

        index_atom : str or int, optional
            Structure selection argument passed to
            ``parse_lammps_dump``.

            Default is ":".
        """
        self.Z_of_type = Z_of_type
        self.index_atom = index_atom
    def __repr__(self) -> str:
        return (f"LammpsDumpReader("
            f"index_atom={self.index_atom!r}, "
            f"Z_of_type={self.Z_of_type})")
    def __str__(self) -> str:
        return self.__repr__()
    def read(self, path:str)->List[Atoms]:
        """
        Read a LAMMPS dump file.

        Parameters
        ----------
        path : str
            Path to the dump file.

        Returns
        -------
        Atoms or List[Atoms]
            Parsed ASE structure(s).
        """
        return parse_lammps_dump(
            path,
            self.Z_of_type,
            self.index_atom,
        )
    def merge(self, data)->List[Atoms]:
        """
        Merge multiple LAMMPS dump trajectories.

        Parameters
        ----------
        data : List[List[Atoms]]
            Structures read from each dump file.

        Returns
        -------
        List[Atoms]
            Flat list containing all configurations from all
            dump files, preserving their original ordering.
        """
        all_atoms = []
        for traj in data:
            all_atoms.extend(traj)
        return all_atoms
class LammpsLogReader(BaseSeriesReader):
    """
    Reader for standard LAMMPS log files.

    The thermodynamic table located between the lines
    containing "Step" and "Loop" is converted into a
    pandas DataFrame.
    """
    def __repr__(self) -> str:
        return "LammpsLogReader()"
    def __str__(self) -> str:
        return self.__repr__()
    def read(self, path:str)->pd.DataFrame:
        """
        Read a LAMMPS log file.

        Parameters
        ----------
        path : str
            Path to the log file.

        Returns
        -------
        pandas.DataFrame
            DataFrame containing:

            - Step
            - Temp
            - PotEng
            - KinEng
            - TotEng
            - Press
        """
        with open(path) as f:
            lines = f.readlines()
        reading = False
        data = []
        for line in lines:
            if "Step" in line:
                reading = True
                continue
            if "Loop" in line:
                break
            if reading:
                data.append(line.strip().split())

        return pd.DataFrame(
            data,
            columns=[
                "Step",
                "Temp",
                "PotEng",
                "KinEng",
                "TotEng",
                "Press",
            ],dtype=float,)
    def merge(self, data)->pd.DataFrame:
        """
        Concatenate LAMMPS thermodynamic logs while preserving
        step continuity.

        Parameters
        ----------
        data : List[pandas.DataFrame]
            DataFrames generated from successive LAMMPS log files.

        Returns
        -------
        pandas.DataFrame
            Single DataFrame containing all thermodynamic data.

        Notes
        -----
        For every DataFrame after the first, the ``Step`` column
        is shifted by the final step of the already concatenated
        data. This produces a continuous step sequence across
        multiple simulations.
        """
        result = pd.DataFrame()
        for df in data:
            if not result.empty:
                last_step = (result["Step"].iloc[-1])
                df = df.copy()
                df["Step"] += last_step
            result = pd.concat([result, df],ignore_index=True,)
        return result
class FunctionReader(BaseSeriesReader):
    """
    Reader wrapper around a user-defined function.

    This class makes it possible to use any custom file
    parser with the ``BaseSeriesReader`` interface.
    """
    def __init__(self,read_function,):
        """
        Parameters
        ----------
        read_function : callable
            Function taking a path as input and returning
            the parsed content.

        Example
        -------
        >>> def read_my_file(path):
        ...     return open(path).read()
        ...
        >>> reader = FunctionReader(read_my_file)
        """
        self.read_function = read_function
    def __repr__(self) -> str:
        name = getattr(
            self.read_function,
            "__name__",
            "anonymous")
        return (f"FunctionReader("
            f"read_function='{name}')")
    def __str__(self) -> str:
        return self.__repr__()
    def read(self, path:str):
        """
        Read a file using the user-provided function.

        Parameters
        ----------
        path : str
            Path to the file.

        Returns
        -------
        Any
            Result returned by ``read_function``.
        """
        return self.read_function(path)
class ThermoLogReader(BaseSeriesReader):
    def __init__(self,timestep_fs=None,)->None:
        """
        Reader for thermo_*.log file type saved used ASE.

        Parameters
        ----------
        timestep_fs : float | None
            MD timestep in fs.
        """
        self.timestep_fs = timestep_fs
    def __repr__(self) -> str:
        return (f"ThermoLogReader("
            f"timestep_fs={self.timestep_fs})")
    def __str__(self) -> str:
        return self.__repr__()
    def read(self, path:str)->pd.DataFrame:
        """
        Read a thermo_*.log file.

        Parameters
        ----------
        path : str
        timestep_fs : float | None
            MD timestep in fs.

        Returns
        -------
        pandas.DataFrame
        """
        with open(path, "r") as f:
            header = f.readline().strip()
        columns = header.lstrip("#").split()
        df = pd.read_csv(
            path,
            sep=r"\s+",
            skiprows=1,
            names=columns,
        )
        df["E_tot(eV)"] = df["E_pot(eV)"] + df["E_kin(eV)"]
        if self.timestep_fs is not None:
            df["time_fs"] = df["step"] * self.timestep_fs
            df["time_ps"] = df["time_fs"] * 1e-3
        return df
    def merge(self, data)->pd.DataFrame:
        result = pd.DataFrame()
        for df in data:
            if not result.empty:
                last_step = (result["step"].iloc[-1])
                df = df.copy()
                df["step"] += last_step
            result = pd.concat([result, df],ignore_index=True,)
        return result
