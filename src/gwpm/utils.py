from typing import List, Union, Dict, Optional
import warnings

import os
import numpy as np
from numpy import ndarray
# ASE.
from ase import Atoms
from ase.cell import Cell

def parse_index_option(index:int, timesteps:list):
    """Convert string index option into actual indices."""
    if isinstance(index, int):  # Direct integer index
        return [timesteps[index]] if index < len(timesteps) else []
    elif isinstance(index, str):
        return timesteps[slice(*map(lambda x: int(x) if x else None, index.split(":")))]
    return []
def detect_structure_size(file_path:str):
    """Determines the number of lines per structure dynamically for each timestep."""
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
    Parses a LAMMPS dump file and returns a list of ASE Atoms objects.

    Args:
        file_path (str):
            Path to the LAMMPS dump file.
        element_mapping (dict):
            Dictionary mapping atom types (int) to element symbols (str).
        index (str): String for the reading of the file.
                     * ``index=0``: first configuration
                     * ``index=-2``: second to last
                     * ``index=':'``: all
                     * ``index='-3:'``: three last
                     * ``index='::2'``: even
                     * ``index='1::2'``: odd
                     * ``index='::50'``: every 50 steps.
    Returns:
    - atom_array (list): List of ASE Atoms objects.
    """
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
def check_folder(folder: str):
    """Function that checks if the folder exist, if it doesn't create one."""
    if not os.path.isdir(folder):
        os.makedirs(folder)
        print("Creating folder(s) following " + folder)

def variable_to_string(
    variable,
    mode: str = None,
    buffer_list_type: str = " ",
    trailing_zero: int = 0,
    leading_zero: int = 0,
    float_trail: bool = False,
    litteral_string: bool = False) -> str:
    """
    Convert a variable into a formatted string for clean output in text files.

    Parameters:
        variable (Any):
            The input variable to convert (int, float, bool, str, list, matrix, etc.).

        mode (str, optional):
            Formatting mode:
            - "F90": Converts booleans to Fortran-style (.TRUE. / .FALSE.).
            - "matrix_2-0": Formats matrices with 2 spaces between rows and 0 between columns.

        buffer_list_type (str, optional):
            Separator used when formatting lists or matrices. Default is a single space.

        trailing_zero (int, optional):
            Number of trailing zeros to append to float values. Default is 0.

        leading_zero (int, optional):
            Number of leading zeros to prepend to numeric values (excluding booleans). Default is 0.

        float_trail (bool, optional):
            If True, keeps trailing zeros in floats even if they are numerically integers.

        litteral_string (bool, optional):
            If True, wraps string values in quotes (" or ') for literal representation.

    Returns:
        str:
            A string representation of the input variable, formatted according to the specified options.

    Examples:
        >>> variable_to_string(3.5, trailing_zero=2)
        '3.50'

        >>> variable_to_string(True, mode="F90")
        '.TRUE.'

        >>> variable_to_string("hello", litteral_string=True)
        '"hello"'

        >>> variable_to_string([[1, 2], [3, 4]], mode="matrix_2-0")
        1 2\n3 4
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
            if int(exponent) < 0:
                str_var = format(variable, ".{}f".format(abs(int(exponent))))
            else:
                str_var = format(variable, ".{}f".format(abs(int(exponent))))
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
    ## Add verification if Cell exist / is installed.
    if isinstance(variable, Cell):
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
def litteral_str(string: str, verbose: bool = False):
    """Add \" or ' in between a string if necessary."""
    if (string.startswith("'") or string.startswith('"')) and (
        string.endswith("'") or string.endswith('"')
    ):
        if verbose:
            print("Nothing to do.")
        return string
    return "'" + string + "'"
def getnonemptylist(str: str, splitSym):
    """Function that will remove spaces and line jump from the read and split the lines in function of spaces.

    This function was done by Stephen Rauch on stackoverflow."""
    return [s for s in str.split(splitSym) if s.strip() != ""]
def _numpy_to_list_recursive(obj):
    """
    Recursively convert NumPy arrays inside nested structures into Python lists.
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        return [_numpy_to_list_recursive(item) for item in obj]
    else:
        return obj