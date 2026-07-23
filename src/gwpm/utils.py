from typing import List, Union, Any, Optional
import warnings

import numpy as np
from numpy import ndarray
from pathlib import Path
# ASE.
try:
    from ase import Atoms
    from ase.cell import Cell
except ImportError: # pragma: no cover
    Atoms = None
    Cell = None
def _require_ase():
    if Atoms is None:
        raise ImportError(
            "ASE is required. "
            "Install with pip install gwpm[structures]"
            )
###################
def parse_index_option(index:int, timesteps:list)->list:
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
    if isinstance(index, int):  # Direct integer index
        return [timesteps[index]] if index < len(timesteps) else []
    elif isinstance(index, str):
        return timesteps[slice(*map(lambda x: int(x) if x else None, index.split(":")))]
    return []
def detect_structure_size(file_path:str)->List[int]:
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
def parse_lammps_dump( file_path: str, element_mapping: dict, index: Union[int, str] = ":" ):
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
    # Initialize variables
    positions = []
    symbols = []
    box_bounds = []
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
    selected_positions = parse_index_option(index, timesteps)
    with open(file_path, "r") as f:
        for i, pos in enumerate(selected_positions):
            ## Find the position to take data.
            f.seek(pos)
            ## mode = 0 : Nothing. mode = 1 : Box bounds. mode = 2 : Atoms.
            mode = 0
            # current_structure = [f.readline()]
            atom_lines = []
            for _ in range(structure_sizes[i] - 1):  # Use detected size per structure
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
                    # Identify if a new data needs to be added
                    ## Forces
                    fx_idx = col_index.get("fx")
                    fy_idx = col_index.get("fy")
                    fz_idx = col_index.get("fz")
                    #
                    has_forces = (
                        fx_idx is not None and fy_idx is not None and fz_idx is not None
                    )
                    #
                    if has_forces:  # Declare it only if useful.
                        forces = []
                    ##
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
                    atom_id = int(data[col_index["id"]])
                    atom_type = int(data[col_index["type"]])
                    x = float(data[col_index.get("xu", col_index.get("x"))])
                    y = float(data[col_index.get("yu", col_index.get("y"))])
                    z = float(data[col_index.get("zu", col_index.get("z"))])
                    ## Non-required input
                    if has_forces:
                        fx = float(data[fx_idx])
                        fy = float(data[fy_idx])
                        fz = float(data[fz_idx])
                        forces.append([fx, fy, fz])
                    #
                    # Map atom types to elements using the input mapping
                    element = element_mapping.get(atom_type)
                    if not element:
                        raise ValueError(
                            f"Unknown atom type {atom_type}. Please update the element mapping."
                        )
                    atom_lines.append((atom_id, element, [x, y, z]))
            # Remake the order of the atoms
            # Sort by atom_id
            atom_lines.sort(key=lambda x: x[0])
            # Unpack sorted data
            symbols = [line[1] for line in atom_lines]
            positions = [line[2] for line in atom_lines]
            # Create ASE Atoms object.
            cell = np.array([bound[1] - bound[0] for bound in box_bounds])
            atom_array.append(
                Atoms(symbols=symbols, positions=positions, cell=cell, pbc=True)
            )
            # Free memory.
            box_bounds = []  # Reset for the next block
            positions = []  # Reset for the next block
            symbols = []  # Reset for the next block
            #
    return atom_array
########
def check_folder(folder: Union[str,Path])->None:
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
def variable_to_string(
    variable:Any,
    mode: str = None,
    buffer_list_type: str = " ",
    trailing_zero: int = 0,
    leading_zero: int = 0,
    float_trail: bool = False,
    litteral_string: bool = False,
    force_float:bool = False,) -> str:
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
        Minimum number of trailing digits or characters.

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
    >>> variable_to_string(3.5, trailing_zero=2)
    '3.50'

    >>> variable_to_string(True, mode="F90")
    '.TRUE.'

    >>> variable_to_string(
    ...     [[1, 2], [3, 4]],
    ...     mode="matrix_2-0"
    ... )
    '1  2\\n3  4'
    """
    # Function implementation goes here
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
            if mode == None or not mode.lower().__contains__("matrix_"):
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

    # str and int/float must be after else the bool will not be taken care of.
    if isinstance(variable, str):
        lead_zero = "{:0>{}}".format(variable, leading_zero)
        trail_zero = "{:0<{}}".format(lead_zero, trailing_zero)
        if litteral_string:
            trail_zero = litteral_str(trail_zero)
        return trail_zero

    if isinstance(variable, int):
        lead_zero = "{:0>{}}".format(variable, leading_zero)
        trail_zero = "{:0<{}}".format(lead_zero, trailing_zero)
        return trail_zero

    if isinstance(variable, float):
        # Float with exponent
        if str(variable).__contains__("e"):
            _, exponent = str(variable).split("e")
            str_var = format(variable, f".{abs(int(exponent))}f")
            if force_float:
                str_var = str_var.rstrip("0")
                if str_var.endswith("."):
                    str_var += "0"
            elif abs(int(exponent)) > 10:
                str_var = str(variable) # keep scientific notation (the exponent is too big).
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
            lead_zero = "{:0>{}}".format(variable, leading_zero)
            trail_zero = "{:0<{}}".format(lead_zero, trailing_zero)
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
def litteral_str(string: str, verbose: bool = False)->str:
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
def getnonemptylist(str: str, splitSym:str)->List[str]:
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
