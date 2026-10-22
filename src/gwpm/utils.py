from typing import Iterable, List, Union, Any
from concurrent.futures import ThreadPoolExecutor
import math
import os
import warnings

import numpy as np
from numpy import ndarray
from pathlib import Path

# ASE.
try:
    from ase import Atoms
    from ase.cell import Cell
except ImportError:  # pragma: no cover
    Atoms = None
    Cell = None


def _require_ase():
    if Atoms is None:
        raise ImportError("ASE is required. Install with pip install gwpm[structures]")


###################
def parse_index_option(index: int, timesteps: list) -> list:
    """
    Convert an index specification into file offsets.

    This helper accepts either a single integer index or a Python-like
    slice expression encoded as a string and returns the corresponding
    entries from ``timesteps``.

    Parameters
    ----------
    index : int or str
        Selection specification.

        - ``0`` returns the first timestep.
        - ``-1`` returns the last timestep.
        - ``":"`` returns all timesteps.
        - ``"::2"`` returns every second timestep.
        - ``"-10:"`` returns the last ten timesteps.

    timesteps : list
        List of file positions corresponding to timestep locations.

    Returns
    -------
    list
        Selected timestep offsets.

    Examples
    --------
    >>> parse_index_option(0, [10, 20, 30])
    [10]

    >>> parse_index_option("1:", [10, 20, 30])
    [20, 30]

    >>> parse_index_option("::2", [10, 20, 30, 40])
    [10, 30]
    """
    if isinstance(index, str) and ":" not in index:
        index = int(index)  # "-1" is the same as -1, not a slice.
    if isinstance(index, int):  # Direct integer index
        return [timesteps[index]] if -len(timesteps) <= index < len(timesteps) else []
    elif isinstance(index, str):
        return timesteps[slice(*map(lambda x: int(x) if x else None, index.split(":")))]
    return []


def detect_structure_size(file_path: str) -> List[int]:
    """
    Determine the number of lines associated with each structure
    stored in a LAMMPS dump file.

    The function scans the dump file and counts the number of lines
    between successive ``ITEM: TIMESTEP`` markers. This allows the
    parser to handle trajectories where the structure block size may
    vary between timesteps.

    Parameters
    ----------
    file_path : str
        Path to the LAMMPS dump file.

    Returns
    -------
    List[int]
        Number of lines associated with each structure.

    Examples
    --------
    >>> detect_structure_size("dump.lammpstrj")
    [1253, 1253, 1253]
    """
    structure_sizes = []
    with open(file_path, "r") as f:
        line_count = 0
        inside_structure = False
        for line in f:
            if "ITEM: TIMESTEP" in line:
                if inside_structure:
                    structure_sizes.append(
                        line_count
                    )  # Store size for previous structure
                inside_structure = True
                line_count = 1  # Start counting lines for new structure
            elif inside_structure:
                line_count += 1

    structure_sizes.append(line_count)  # Store last structure size
    return structure_sizes  # Returns a list with sizes per structure


def parse_lammps_dump(
    file_path: str, element_mapping: dict, index: Union[int, str] = ":"
):
    """
    Read a LAMMPS dump trajectory and convert it into ASE structures.

    The function parses atomic coordinates, simulation cell dimensions,
    and optionally atomic forces from a standard LAMMPS dump file. Each
    selected timestep is returned as an ASE ``Atoms`` object.

    Parameters
    ----------
    file_path : str
        Path to the LAMMPS dump file.

    element_mapping : Dict[int, str]
        Mapping between LAMMPS atom types and chemical symbols.

        Example::

            {
                1: "Li",
                2: "O"
            }

    index : int or str, default=":"
        Structure selection specification.

        - ``0`` : first structure
        - ``-1`` : last structure
        - ``":"`` : all structures
        - ``"-5:"`` : last five structures
        - ``"::10"`` : every tenth structure
        - ``"1::2"`` : every odd structure

    Returns
    -------
    List[ase.Atoms]
        List of ASE ``Atoms`` objects.

    Raises
    ------
    ValueError
        If an atom type appears that is not present in
        ``element_mapping``.

    Notes
    -----
    If force components (``fx``, ``fy``, ``fz``) are present in the
    dump file they are detected during parsing, although they are not
    currently attached to the returned ``Atoms`` objects.

    Examples
    --------
    >>> atoms = parse_lammps_dump(
    ...     "dump.lammpstrj",
    ...     {1: "Li", 2: "O"},
    ...     index="::100"
    ... )
    >>> len(atoms)
    10
    """
    _require_ase()
    atom_array = []
    #
    with open(file_path, "r") as f:
        timesteps = []
        while True:
            line = f.readline()
            if not line:
                break
            if "ITEM: TIMESTEP" in line:
                timesteps.append(
                    f.tell()
                )  # Store file position to read the data of the position.

    structure_sizes = detect_structure_size(
        file_path
    )  # Auto-detect sizes per structure
    ## Select the structures by their number, so the size of each one is used.
    selected_structures = parse_index_option(index, list(range(len(timesteps))))
    with open(file_path, "r") as f:
        for i in selected_structures:
            ## Find the position to take data.
            f.seek(timesteps[i])
            ## mode = 0 : Nothing. mode = 1 : Box bounds. mode = 2 : Atoms.
            mode = 0
            box_bounds = []
            atom_lines = []
            for _ in range(structure_sizes[i] - 1):  # Use the size of this structure
                # Take the line of the file
                line = f.readline()
                # Take the good boxbounds
                if "BOX BOUNDS" in line:
                    # If we look at the BOX BOUNDS and we have nothing else, we are inside the BOX BOUNDS.
                    mode = 1
                    continue
                # Take the good atoms position.
                elif "ITEM: ATOMS" in line:
                    mode = 2
                    #
                    headers = line.strip().split()[2:]  # Skip "ITEM: ATOMS"
                    col_index = {key: idx for idx, key in enumerate(headers)}
                    ## Positions: unwrapped, wrapped or scaled (fraction of the cell).
                    for position_columns, scaled in (
                        (("xu", "yu", "zu"), False),
                        (("x", "y", "z"), False),
                        (("xsu", "ysu", "zsu"), True),
                        (("xs", "ys", "zs"), True),
                    ):
                        if all(c in col_index for c in position_columns):
                            position_idx = [col_index[c] for c in position_columns]
                            break
                    else:
                        raise ValueError(
                            f"No position columns (x/xu/xs/xsu y z) in: {' '.join(headers)}."
                        )
                    ## Elements: from the element column, or from the type with the mapping.
                    if "element" not in col_index:
                        if "type" not in col_index:
                            raise ValueError("No 'type' or 'element' column.")
                        if element_mapping is None:
                            raise ValueError(
                                "Z_of_type must be given to read the 'type' column, e.g. {1: 'Li', 2: 'O'}."
                            )
                    continue
                elif "ITEM:" in line:
                    mode = 0
                    continue
                # Use the mode.
                #
                if mode == 1:
                    box_bounds.append([float(x) for x in line.split()])
                if mode == 2:
                    # Take atom lines.
                    data = line.split()
                    atom_id = (
                        int(data[col_index["id"]])
                        if "id" in col_index
                        else len(atom_lines)
                    )
                    position = [float(data[idx]) for idx in position_idx]
                    #
                    if "element" in col_index:
                        element = data[col_index["element"]]
                    else:
                        # Map atom types to elements using the input mapping
                        atom_type = int(data[col_index["type"]])
                        element = element_mapping.get(atom_type)
                        if not element:
                            raise ValueError(
                                f"Unknown atom type {atom_type}. Please update the element mapping."
                            )
                    atom_lines.append((atom_id, element, position))
            # Remake the order of the atoms
            # Sort by atom_id
            atom_lines.sort(key=lambda x: x[0])
            # Unpack sorted data
            symbols = [line[1] for line in atom_lines]
            positions = np.array([line[2] for line in atom_lines]).reshape(-1, 3)
            cell = _lammps_box_to_cell(box_bounds)
            if scaled:
                positions = positions @ cell
            # Create ASE Atoms object.
            atom_array.append(
                Atoms(symbols=symbols, positions=positions, cell=cell, pbc=True)
            )
            #
    return atom_array


def _lammps_box_to_cell(box_bounds: List[List[float]]) -> ndarray:
    """
    Convert the BOX BOUNDS of a LAMMPS dump into a cell matrix.

    Parameters
    ----------
    box_bounds : List[List[float]]
        Three lines ``lo hi`` (orthogonal box) or ``lo_bound hi_bound tilt``
        (triclinic box, tilts xy, xz, yz).

    Returns
    -------
    ndarray
        3x3 cell matrix (rows are the cell vectors).
    """
    if len(box_bounds) != 3:
        raise ValueError(f"BOX BOUNDS must have 3 lines, got {len(box_bounds)}.")
    if all(len(bound) == 2 for bound in box_bounds):
        return np.diag([bound[1] - bound[0] for bound in box_bounds])
    ## Triclinic: the bounds include the tilts, see the LAMMPS dump documentation.
    (xlo_b, xhi_b, xy), (ylo_b, yhi_b, xz), (zlo, zhi, yz) = box_bounds
    xlo = xlo_b - min(0.0, xy, xz, xy + xz)
    xhi = xhi_b - max(0.0, xy, xz, xy + xz)
    ylo = ylo_b - min(0.0, yz)
    yhi = yhi_b - max(0.0, yz)
    if min(xhi - xlo, yhi - ylo, zhi - zlo) <= 0:
        raise ValueError(f"Invalid triclinic BOX BOUNDS: {box_bounds}.")
    return np.array(
        [
            [xhi - xlo, 0.0, 0.0],
            [xy, yhi - ylo, 0.0],
            [xz, yz, zhi - zlo],
        ]
    )


########
def check_folder(folder: Union[str, Path]) -> None:
    """
    Ensure that a directory exists.

    If the target directory does not already exist, it is created
    along with any missing parent directories.

    Parameters
    ----------
    folder : str or pathlib.Path
        Directory path to verify.

    Notes
    -----
    A message is printed when a new directory is created.

    Examples
    --------
    >>> check_folder("./output")

    >>> check_folder(Path("./output"))
    """
    folder = Path(folder)
    if not folder.is_dir():
        folder.mkdir(parents=True, exist_ok=True)
        print(f"Creating folder(s) following {folder}")


def check_folder_parallel(
    folders: Iterable[Union[str, Path]],
    n_workers: int = 8,
    verbose: bool = True,
) -> int:
    """
    Ensure that many directories exist, creating them in parallel.

    Every folder and its parents are created exactly once, one depth
    level after the other, each level with ``n_workers`` threads. This
    is useful on network filesystems (Lustre, NFS) where each creation
    is a request to a metadata server.

    Parameters
    ----------
    folders : Iterable[str or pathlib.Path]
        Directory paths to verify. To create the folders of a
        ``GeneralWorkPathManager``, use ``gwpm.create_folders()``:
        ``gwpm.all_paths()`` also contains ``gwpm.file``, which would be
        created as a folder.

    n_workers : int, default=8
        Number of threads. Keep it moderate (8-16) on shared HPC
        filesystems, as many simultaneous creations load the metadata
        server.

    verbose : bool, default=True
        Print the number of folders created.

    Returns
    -------
    int
        Number of folders created.

    Raises
    ------
    FileExistsError
        If one of the paths exists as a file.

    Examples
    --------
    >>> check_folder_parallel(["./runs/Li/300K", "./runs/Li/600K"], n_workers=8)
    Created 3 folder(s).
    3
    """
    ## All the folders and their parents, once ("." and "/" always exist).
    levels = {}
    for folder in folders:
        folder = Path(folder)
        for path in (folder, *folder.parents):
            if path == Path(".") or path == Path(path.anchor):
                continue
            levels.setdefault(len(path.parts), set()).add(path)

    def make(path: Path) -> bool:
        try:
            os.mkdir(path)
            return True
        except FileExistsError:
            if not path.is_dir():
                raise
            return False

    created = 0
    with ThreadPoolExecutor(max(1, n_workers)) as executor:
        ## The parents (smaller depth) are created before their children.
        for depth in sorted(levels):
            created += sum(executor.map(make, sorted(levels[depth])))
    if verbose:
        print(f"Created {created} folder(s).")
    return created


def variable_to_string(
    variable: Any,
    mode: str = None,
    buffer_list_type: str = " ",
    trailing_zero: int = 0,
    leading_zero: int = 0,
    float_trail: bool = False,
    litteral_string: bool = False,
    force_float: bool = False,
) -> str:
    """
    Convert a Python object into a formatted string representation.

    The function provides a consistent conversion layer for writing
    values to text-based input files. It supports scalars, lists,
    matrices, NumPy arrays, ASE ``Cell`` objects, and several
    formatting conventions used by scientific software.

    Parameters
    ----------
    variable : Any
        Object to convert.

    mode : str, optional
        Formatting mode.

        Supported values include:

        ``"F90"``
            Format boolean values as Fortran logicals.

        ``"VASP"``
            Format boolean values as VASP logicals.

        ``"matrix_X-Y"``
            Format matrices using X spaces between columns and Y spaces
            before each new row.

    buffer_list_type : str, default=" "
        Separator used when formatting one-dimensional lists.

    trailing_zero : int, default=0
        Minimum number of decimal digits of floats (zeros added on the
        right). Strings are padded on the right to this width. Integers
        are not changed.

    leading_zero : int, default=0
        Minimum width padded with leading zeros.

    float_trail : bool, default=False
        Preserve trailing zeroes for floating-point numbers.

    litteral_string : bool, default=False
        Wrap string values in quotes.

    force_float : bool, default=False
        Force scientific notation values to be expanded as decimal
        floating-point numbers whenever possible.

    Returns
    -------
    str
        Formatted string representation.

    Warns
    -----
    SyntaxWarning
        Issued when an unsupported object type is encountered and
        fallback conversion via ``str()`` is used.

    Examples
    --------
    >>> variable_to_string(3.5, trailing_zero=3)
    '3.500'

    >>> variable_to_string(True, mode="F90")
    '.TRUE.'

    >>> variable_to_string(
    ...     [[1, 2], [3, 4]],
    ...     mode="matrix_2-0"
    ... )
    '1  2\\n3  4'
    """
    # Function implementation goes here
    if isinstance(variable, str) and not (
        leading_zero or trailing_zero or litteral_string
    ):
        return variable  # Nothing to format (most paths).
    if isinstance(variable, np.generic):
        variable = variable.item()  # numpy scalars as Python scalars.
    if isinstance(variable, (list, ndarray)):
        # We have a simple list
        if not all(isinstance(ele, (list, ndarray)) for ele in variable):
            tmp = ""
            for i in range(len(variable)):
                if i == len(variable) - 1:
                    buffer = ""
                else:
                    buffer = buffer_list_type
                trail_zero = variable_to_string(
                    variable[i],
                    mode=mode,
                    trailing_zero=trailing_zero,
                    leading_zero=leading_zero,
                    float_trail=float_trail,
                )
                tmp = tmp + str(trail_zero) + buffer
            return tmp
        else:
            # We have a matrix.
            if mode is None or not mode.lower().__contains__("matrix_"):
                default_mode = True
                line_sep = buffer_list_type
                column_sep = "\n"
                tmp = ""
            else:
                line_sep_nbr, column_sep_nbr = mode.replace("matrix_", "").split("-")
                default_mode = False
                line_sep = " " * int(line_sep_nbr)
                column_sep = "\n" + " " * int(column_sep_nbr)
                tmp = " " * (int(column_sep_nbr))

            for i in range(len(variable)):
                for j in range(len(variable[i])):
                    if j == len(variable[i]) - 1:
                        buffer = ""
                    else:
                        buffer = line_sep
                    trail_zero = variable_to_string(
                        variable[i][j],
                        mode=mode,
                        trailing_zero=trailing_zero,
                        leading_zero=leading_zero,
                        float_trail=float_trail,
                    )
                    if not str(trail_zero).__contains__("-") and not default_mode:
                        trail_zero = " " + trail_zero
                    tmp = tmp + str(trail_zero) + buffer
                if i != len(variable) - 1:
                    tmp = tmp + column_sep
            return tmp
    if (
        isinstance(variable, bool)
        and isinstance(mode, str)
        and mode.upper() in {"F90", "VASP"}
    ):
        return ".TRUE." if variable else ".FALSE."
    if isinstance(variable, bool):
        return str(variable)
    if isinstance(variable, (int, float)) and variable < 0:
        # The zeros are added after the sign: -5 -> "-005".
        return "-" + variable_to_string(
            -variable,
            mode=mode,
            buffer_list_type=buffer_list_type,
            trailing_zero=trailing_zero,
            leading_zero=leading_zero,
            float_trail=float_trail,
            litteral_string=litteral_string,
            force_float=force_float,
        )

    # str and int/float must be after else the bool will not be taken care of.
    if isinstance(variable, str):
        lead_zero = "{:0>{}}".format(variable, leading_zero)
        trail_zero = "{:0<{}}".format(lead_zero, trailing_zero)
        if litteral_string:
            trail_zero = litteral_str(trail_zero)
        return trail_zero

    if isinstance(variable, int):
        # No decimal digits: trailing_zero does not apply.
        return "{:0>{}}".format(variable, leading_zero)

    if isinstance(variable, float):
        if math.isnan(variable) or math.isinf(variable):
            return str(variable)
        # Float with exponent
        if str(variable).__contains__("e"):
            _, exponent = str(variable).split("e")
            str_var = format(variable, f".{abs(int(exponent))}f")
            if force_float:
                str_var = str_var.rstrip("0")
                if str_var.endswith("."):
                    str_var += "0"
            elif abs(int(exponent)) > 10:
                str_var = str(
                    variable
                )  # keep scientific notation (the exponent is too big).
            #
            if float_trail:
                int_part, float_part = str_var.split(
                    "."
                )  # We come back to the float list with float_trail.
                #
                lead_zero = "{:0>{}}".format(int_part, leading_zero)
                trail_zero = "{}.{:0<{}}".format(lead_zero, float_part, trailing_zero)
            else:  # We simply uses the normal values without float_trail, here we do not take into account leading or trailing zeros.
                trail_zero = str_var
            return trail_zero
        elif variable == int(variable) or float_trail:
            int_part, float_part = str(variable).split(".")
            #
            lead_zero = "{:0>{}}".format(int_part, leading_zero)
            trail_zero = "{}.{:0<{}}".format(lead_zero, float_part, trailing_zero)
        else:
            _, float_part = str(variable).split(".")
            lead_zero = "{:0>{}}".format(variable, leading_zero)
            # trailing_zero is the number of decimal digits.
            trail_zero = lead_zero + "0" * max(0, trailing_zero - len(float_part))
        return trail_zero
    if Cell is not None and isinstance(variable, Cell):
        # Special conversion of the Cell class from ASE into a string.
        string_list = []

        for i in range(len(variable)):
            string_list.append(variable[i])
        return variable_to_string(
            string_list,
            mode=mode,
            buffer_list_type=" ",
            trailing_zero=trailing_zero,
            leading_zero=leading_zero,
        )

    # I can add more support later on.
    warnings.warn(
        "Non supported variable type. It will be converted by str() function.",
        SyntaxWarning,
    )
    return str(variable)


def litteral_str(string: str, verbose: bool = False) -> str:
    """
    Return a quoted string literal.

    If the supplied string is already enclosed in single or double
    quotes it is returned unchanged. Otherwise single quotes are added.

    Parameters
    ----------
    string : str
        String to convert into a literal representation.

    verbose : bool, default=False
        Print diagnostic messages.

    Returns
    -------
    str
        Quoted string.

    Examples
    --------
    >>> litteral_str("hello")
    "'hello'"

    >>> litteral_str("'hello'")
    "'hello'"
    """
    if (string.startswith("'") or string.startswith('"')) and (
        string.endswith("'") or string.endswith('"')
    ):
        if verbose:
            print("Nothing to do.")
        return string
    return "'" + string + "'"


def getnonemptylist(str: str, splitSym: str) -> List[str]:
    """
    Split a string and remove empty fields.

    Parameters
    ----------
    string : str
        Input text.

    splitSym : str
        Delimiter used to split the text.

    Returns
    -------
    List[str]
        Non-empty tokens.

    Notes
    -----
    Original implementation inspired by a Stack Overflow answer from
    Stephen Rauch.

    Examples
    --------
    >>> getnonemptylist("a  b   c", " ")
    ['a', 'b', 'c']
    """
    return [s for s in str.split(splitSym) if s.strip() != ""]


def _numpy_to_list_recursive(obj):
    """
    Recursively convert NumPy arrays into Python lists.

    Nested containers such as lists and tuples are traversed and all
    encountered NumPy arrays are replaced by their corresponding
    ``tolist()`` representation.

    Parameters
    ----------
    obj : Any
        Object to convert.

    Returns
    -------
    Any
        Converted object with all NumPy arrays replaced by native
        Python lists.

    Examples
    --------
    >>> _numpy_to_list_recursive(np.array([1, 2, 3]))
    [1, 2, 3]

    >>> _numpy_to_list_recursive(
    ...     [np.array([1, 2]), np.array([3, 4])]
    ... )
    [[1, 2], [3, 4]]
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        return [_numpy_to_list_recursive(item) for item in obj]
    else:
        return obj
