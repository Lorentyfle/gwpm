from typing import Union, Optional, Any, List, Tuple, Dict, Callable
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from pathlib import Path
import os
import re
import warnings
import numpy as np
import pandas as pd
import json
import pickle


from .utils import variable_to_string, check_folder_parallel
from .series_reader import PlaceholderSeries, BaseSeriesReader
from .exception import (
    ReplacerConfigurationError,
    ReferenceResolutionError,
    PathResolutionError,
    DependencyLoopError,
    SerializationError,
)

## Types that can be saved by name in ``to_dict`` and recovered by ``from_dict``.
_SERIALIZABLE_TYPES = {"str": str, "int": int, "float": float, "bool": bool}


@lru_cache(maxsize=None)
def _compile_placeholders(placeholders: Tuple[str, ...]) -> re.Pattern:
    """
    Regex matching any placeholders token, longest first (cached, as it is
    used for every resolved path).
    """
    return re.compile(
        "|".join(
            re.escape(placeholder)
            for placeholder in sorted(placeholders, key=len, reverse=True)
        )
    )


@dataclass
class ReferenceVariable:
    """
    Variable whose first index depends on the selection made for
    another variable.

    A ``ReferenceVariable`` is used when the available values of a
    variable depend on the chosen index of another variable in
    ``GeneralWorkPathManager``.

    Parameters
    ----------
    values : List
        Nested list of values. The first dimension corresponds to the
        referenced variable index and the second dimension corresponds
        to this variable's own index.

    reference_position : int
        Position of the variable whose selected index should be used as
        the first index into ``values``.

    Examples
    --------
    >>> temperatures = ["300K", "600K"]
    >>> structures = ReferenceVariable(
    ...     [
    ...         ["fcc", "bcc"],  # used when temperature index is 0
    ...         ["hcp", "liq"],  # used when temperature index is 1
    ...     ],
    ...     reference_position=0,
    ... )

    If temperature index 1 is selected, ``structures`` will resolve
    values from ``["hcp", "liq"]``.
    """

    values: List[List[Any]]
    reference_position: int

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}(reference_position={self.reference_position})"
        )

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __getitem__(self, item):
        return self.values[item]

    def __contains__(self, item) -> bool:
        return item in self.values

    def to_dict(self) -> dict:
        """
        Export the object as a dictionary.
        """
        return {
            "__type__": self.__class__.__name__,
            "values": self.values,
            "reference_position": self.reference_position,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(values=data["values"], reference_position=data["reference_position"])


class GeneralWorkPathManager:
    """
    Manage collections of related file paths that differ only by a set of
    placeholder variables.

    The class generates concrete paths by replacing user-defined placeholder
    tokens (``self.placeholders``) with values selected from
    ``self.list_of_variables``. It supports recursive substitutions,
    dependent variables through ``ReferenceVariable``, batch file loading,
    and convenience utilities for reading simulation outputs.

    Examples
    --------
    >>> gwpm = GeneralWorkPathManager(
    ...     list_of_variables=[
    ...         ["Li", "Na"],
    ...         ["300K", "600K"],
    ...     ],
    ...     path="./?/!/",
    ...     placeholders=["?", "!"],
    ... )

    >>> gwpm.resolve_path([0, 1])
    './Li/600K/'

    Giving ``variable_type`` converts the values returned by ``iter_paths``,
    ``all_paths_and_variables`` and ``parse`` to the wished types:

    >>> gwpm = GeneralWorkPathManager(
    ...     list_of_variables=[
    ...         ["Li", "Na"],
    ...         ["300", "600"],
    ...     ],
    ...     variable_names=["element", "temperature"],
    ...     variable_type=[str, int],
    ...     path="./?/!K/",
    ...     placeholders=["?", "!"],
    ... )
    >>> gwpm.parse("./Li/600K/")
    {'element': 'Li', 'temperature': 600}
    """

    __version__: str = "1.5.0"

    def __init__(
        self,
        list_of_variables: List[Union[List[Any], ReferenceVariable]],
        placeholders: List[str],
        path: str = "./",
        file: str = "",
        variable_names: Optional[List[str]] = None,
        output_folder: str = "./output/",
        verbose: bool = False,
        variable_type: Optional[List[Optional[Callable]]] = None,
        series_placeholder: str = "<ID>",
    ) -> None:
        if placeholders is None:
            raise ReplacerConfigurationError("Replacer must be given.")
        if isinstance(placeholders, str):
            placeholders = [placeholders]
        if len(set(placeholders)) != len(placeholders):
            raise ReplacerConfigurationError("Replacers must be unique.")
        if any(not isinstance(r, str) or r == "" for r in placeholders):
            raise ReplacerConfigurationError("Replacers must be non-empty strings.")
        for r in placeholders:
            if r in series_placeholder or series_placeholder in r:
                raise ReplacerConfigurationError(
                    f"The placeholders '{r}' overlaps the series placeholder "
                    f"'{series_placeholder}', so resolving a path would replace "
                    f"part of it. Either change this placeholders, or give "
                    f"another series_placeholder (e.g. series_placeholder='[')."
                )
        if len(list_of_variables) != len(placeholders):
            raise PathResolutionError(
                "The list of variables in the folder tree must be the same as the one of the placeholders."
            )
        for i, variable in enumerate(list_of_variables):
            if isinstance(variable, ReferenceVariable):
                ref = variable.reference_position
                if ref < 0:
                    ref = i + ref
                if ref < 0 or ref >= len(list_of_variables):
                    raise ReplacerConfigurationError(
                        "ReferenceVariable cannot reference itself."
                    )
                if ref == i:
                    raise ReplacerConfigurationError(
                        "ReferenceVariable cannot reference itself."
                    )
                if ref > i:
                    raise ReplacerConfigurationError(
                        "ReferenceVariable must reference a previous variable."
                    )
                if ref != variable.reference_position:
                    ## Copy, so the given object can be reused elsewhere.
                    list_of_variables = list(list_of_variables)
                    list_of_variables[i] = ReferenceVariable(variable.values, ref)
        if variable_names is None:
            variable_names = [f"var_{i}" for i in range(len(list_of_variables))]
        if len(variable_names) != len(list_of_variables):
            raise ReplacerConfigurationError(
                f"{len(variable_names)} variable_names given for {len(list_of_variables)} variables."
            )
        if len(set(variable_names)) != len(variable_names):
            raise ReplacerConfigurationError("variable_names must be unique.")
        ## Missing types (or None) are considered as str.
        if variable_type is not None:
            if len(variable_type) > len(list_of_variables):
                raise ReplacerConfigurationError(
                    "variable_type cannot be longer than list_of_variables."
                )
            variable_type = list(variable_type) + [str] * (
                len(list_of_variables) - len(variable_type)
            )
            variable_type = [str if t is None else t for t in variable_type]
            for t in variable_type:
                if not callable(t):
                    raise ReplacerConfigurationError(
                        f"variable_type entries must be callable, got {t!r}."
                    )
        self.list_of_variables: List[Union[List[Any], ReferenceVariable]] = (
            list_of_variables
        )
        self.placeholders: List[str] = placeholders
        self.variable_names: List[str] = variable_names
        self.variable_type: Optional[List[Callable]] = variable_type
        self.series_placeholder: str = series_placeholder
        self.general_path: str = path
        self.current_path: Optional[Path] = None
        self.current_path_file: Optional[Path] = None
        self.file: str = file
        self.output_folder: str = output_folder
        self.verbose: bool = verbose
        if self.file is None or self.file.lower() == "none":
            self.file = ""
        if verbose:
            print("GeneralWorkPathManager initialized.")

    ##################################
    #### Getting back important data and information of the class.
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"n_variables={len(self.list_of_variables)}, "
            f"path='{self.general_path}', "
            f"file='{self.file}')"
        )

    def __str__(self):
        return (
            f"{self.__class__.__name__}\n"
            f"├── general_path       : {self.general_path}\n"
            f"├── file               : {self.file}\n"
            f"├── current_path       : {self.current_path}\n"
            f"├── current_path_file  : {self.current_path_file}\n"
            f"├── output_folder      : {self.output_folder}\n"
            f"├── placeholders       : {self.placeholders}\n"
            f"└── n_variables        : {len(self.list_of_variables)}"
        )

    def __len__(self) -> int:
        return len(self.list_of_variables)

    def __iter__(self):
        return iter(zip(self.placeholders, self.list_of_variables))

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.list_of_variables[item]
        if isinstance(item, str):
            if item in self.placeholders:
                return self.list_of_variables[self.placeholders.index(item)]
            if item in self.variable_names:
                return self.list_of_variables[self.variable_names.index(item)]
            raise KeyError(f"Unknown placeholders or variable name '{item}'.")
        raise TypeError("Item must be an integer, a placeholders or a variable name.")

    def __contains__(self, item) -> bool:
        return item in self.placeholders

    def __eq__(self, other) -> bool:
        if not isinstance(other, GeneralWorkPathManager):
            return False
        return (
            self.list_of_variables == other.list_of_variables
            and self.placeholders == other.placeholders
            and self.variable_names == other.variable_names
            and self.variable_type == other.variable_type
            and self.series_placeholder == other.series_placeholder
            and self.general_path == other.general_path
            and self.file == other.file
            and self.output_folder == other.output_folder
        )

    def keys(self):
        """
        Return all placeholders.
        """
        return self.placeholders

    def values(self):
        """
        Return all variables.
        """
        return self.list_of_variables

    def items(self):
        """
        Return (placeholders, variable) pairs.
        """
        return list(zip(self.placeholders, self.list_of_variables))

    @property
    def current(self) -> Dict[str, Optional[Path]]:
        """
        Return the most recently resolved path information.

        Returns
        -------
        Dict[str, Optional[Path]]
            Dictionary containing:

            ``path``
                Last generated directory path.

            ``path_file``
                Last generated path including filename.
        """
        return {
            "path": self.current_path,
            "path_file": self.current_path_file,
        }

    def placeholders_used(self, text_to_test: str) -> List[str]:
        """
        Return the placeholders tokens present in a string.

        Parameters
        ----------
        text_to_test : str
            Text to inspect.

        Returns
        -------
        List[str]
            List of placeholders tokens found in the order defined by
            ``self.placeholders``.
        """
        rep_used = []
        for r in self.placeholders:
            if text_to_test.__contains__(r):
                rep_used.append(r)
        return rep_used

    def contains_placeholders(self, text_to_test: str) -> bool:
        """
        Check whether a string contains any placeholders token.

        Parameters
        ----------
        text_to_test : str
            Text to inspect.

        Returns
        -------
        bool
            True if at least one placeholders token is present, otherwise False.
        """
        for r in self.placeholders:
            if text_to_test.__contains__(r):
                return True
        return False

    def iter_paths(
        self,
        is_out: bool = False,
        starter: Optional[str] = None,
        recursive: bool = False,
    ):
        """
        Iterate over all possible path combinations.

        Parameters
        ----------
        is_out, starter, recursive
            Passed to ``resolve_path``.

        Yields
        -------
        dict
            One entry per variable name (converted by ``variable_type``
            if given), plus ``index`` and ``path``.
        """
        for index in self._iter_indices():
            data = {
                name: self._cast_variable(
                    i,
                    self._resolve_variable(
                        variable,
                        index[i],
                        list(index),
                    ),
                )
                for i, (name, variable) in enumerate(
                    zip(self.variable_names, self.list_of_variables)
                )
            }
            data["index"] = list(index)
            data["path"] = self.resolve_path(
                list(index),
                is_out=is_out,
                starter=starter,
                recursive=recursive,
                immutable=True,
            )
            yield data

    def _iter_indices(self, prefix: Optional[List[int]] = None):
        """
        Iterate over all valid index combinations.

        For a ``ReferenceVariable`` the number of values depends on the
        index selected for the referenced variable, so the combinations
        are built variable by variable instead of with ``product``.

        Yields
        -------
        List[int]
            Index of each variable, in the order of ``self.list_of_variables``.
        """
        if prefix is None:
            if not any(
                isinstance(variable, ReferenceVariable)
                for variable in self.list_of_variables
            ):
                ## Without ReferenceVariable, every combination is valid.
                for index in product(*(range(len(v)) for v in self.list_of_variables)):
                    yield list(index)
                return
            prefix = []
        position = len(prefix)
        if position == len(self.list_of_variables):
            yield prefix
            return
        variable = self.list_of_variables[position]
        if isinstance(variable, ReferenceVariable):
            n_values = len(variable.values[prefix[variable.reference_position]])
        else:
            n_values = len(variable)
        for idx in range(n_values):
            yield from self._iter_indices(prefix + [idx])

    ###################################################
    ### Save, load and return data.
    def all_paths(
        self,
        is_out: bool = False,
        starter: Optional[str] = None,
        recursive: bool = False,
    ):
        """Return all generated paths as a list (options of ``resolve_path``)."""
        return [
            item["path"]
            for item in self.iter_paths(
                is_out=is_out, starter=starter, recursive=recursive
            )
        ]

    def create_folders(
        self,
        n_workers: int = 8,
        is_out: bool = False,
        starter: Optional[str] = None,
        recursive: bool = False,
        verbose: bool = True,
    ) -> int:
        """
        Create the folders of every path combination, in parallel.

        Only the folder part of the template is used (``self.file`` is
        never created as a folder). See ``check_folder_parallel``.

        Parameters
        ----------
        n_workers : int, default=8
            Number of threads (keep 8-16 on shared HPC filesystems).
        is_out, starter, recursive
            Passed to ``resolve_path``.
        verbose : bool, default=True
            Print the number of folders created.

        Returns
        -------
        int
            Number of folders created.
        """
        path, _ = self._build_path(starter=starter, is_out=is_out)
        if recursive:
            self._check_loop_placeholders()
        folders = []
        for index in self._iter_indices():
            variables = [
                self._resolve_variable(variable, idx, index)
                for variable, idx in zip(self.list_of_variables, index)
            ]
            if recursive:
                folders.append(self._resolve_recursive(path, variables))
            else:
                folders.append(self._apply_replacements(path, variables))
        return check_folder_parallel(folders, n_workers=n_workers, verbose=verbose)

    def all_paths_and_variables(
        self,
        is_out: bool = False,
        starter: Optional[str] = None,
        recursive: bool = False,
    ) -> List[Tuple[Dict[str, Any], Path]]:
        """
        Return all generated paths together with the variables used to build them.

        This allows a single loop over every combination, without having
        to recover the variables from the indices or from the path.

        Parameters
        ----------
        is_out, starter, recursive
            Passed to ``resolve_path``.

        Returns
        -------
        List[Tuple[Dict[str, Any], Path]]
            ``(variables, path)`` pairs, where ``variables`` maps each
            variable name to its value (converted by ``variable_type``
            if given).

        Examples
        --------
        >>> for variables, path in gwpm.all_paths_and_variables():
        ...     print(variables, path)
        {'element': 'Li', 'temperature': 300} Li/300K
        """
        return [
            ({name: item[name] for name in self.variable_names}, item["path"])
            for item in self.iter_paths(
                is_out=is_out, starter=starter, recursive=recursive
            )
        ]

    def to_dict(self) -> dict:
        """
        Export the manager configuration.
        """
        serialized_variables = []
        for var in self.list_of_variables:
            if isinstance(var, ReferenceVariable):
                serialized_variables.append(var.to_dict())
            else:
                serialized_variables.append(var)

        return {
            "list_of_variables": serialized_variables,
            "placeholders": self.placeholders,
            "variable_names": self.variable_names,
            "variable_type": (
                None
                if self.variable_type is None
                else [getattr(t, "__name__", repr(t)) for t in self.variable_type]
            ),
            "path": self.general_path,
            "file": self.file,
            "output_folder": self.output_folder,
            "verbose": self.verbose,
            "series_placeholder": self.series_placeholder,
        }

    def to_dataframe(self) -> pd.DataFrame:
        """
        Export the manager configuration as a pandas DataFrame.
        """
        df = pd.DataFrame(self.iter_paths())
        df.attrs["gwpm_config"] = self.to_dict()
        return df

    def to_json(self, filename: str) -> None:
        def numpy_to_python(obj):
            if isinstance(obj, np.generic):
                return obj.item()
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        with open(filename, "w") as f:
            json.dump(self.to_dict(), f, indent=4, default=numpy_to_python)
        return

    def save(self, filename: str):
        """
        Serialize the manager to a pickle file.

        Parameters
        ----------
        filename : str
            Destination filename.

        Notes
        -----
        The object is stored using the standard ``pickle`` module.
        """
        with open(filename, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def from_dict(cls, data: dict):
        """
        Reconstruct a manager from a
        dictionary produced by ``to_dict``.
        """
        variables = []
        for var in data["list_of_variables"]:
            if isinstance(var, dict) and var.get("__type__") == "ReferenceVariable":
                variables.append(ReferenceVariable.from_dict(var))
            else:
                variables.append(var)
        variable_type = data.get("variable_type")
        if variable_type is not None:
            unknown = [t for t in variable_type if t not in _SERIALIZABLE_TYPES]
            if unknown:
                raise SerializationError(
                    f"Cannot recover variable_type {unknown}, only "
                    f"{list(_SERIALIZABLE_TYPES)} can be loaded back. Use save/load instead."
                )
            variable_type = [_SERIALIZABLE_TYPES[t] for t in variable_type]
        return cls(
            list_of_variables=variables,
            path=data["path"],
            file=data["file"],
            output_folder=data["output_folder"],
            placeholders=data["placeholders"],
            variable_names=data.get("variable_names"),
            verbose=data.get(
                "verbose",
                False,
            ),
            variable_type=variable_type,
            series_placeholder=data.get("series_placeholder", "<ID>"),
        )

    @classmethod
    def from_dataframe(cls, data: pd.DataFrame):
        """
        Reconstruct a manager from a
        dictionary produced by ``to_dataframe``.
        """
        return cls.from_dict(data.attrs["gwpm_config"])

    @classmethod
    def from_json(cls, filename: str):
        with open(filename) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load(cls, filename: str):
        """
        Load a previously pickled manager.

        Parameters
        ----------
        filename : str
            Pickle file to load.

        Returns
        -------
        GeneralWorkPathManager
            Restored manager instance.
        """
        with open(filename, "rb") as f:
            return pickle.load(f)

    ###################################################
    ## Internal functions.
    ### Normalize multiple index types to a index kind.
    def _build_path(
        self,
        starter: Optional[str] = None,
        is_out: bool = False,
        output_file: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Build the unresolved path template.

        Parameters
        ----------
        starter : str, optional
            Prefix prepended before the general path.

        is_out : bool, default=False
            If True, append ``output_folder``.

        output_file : str, optional
            File name to use instead of ``self.file``.

        Returns
        -------
        tuple[str, str]
            Unresolved ``(path, path_file)``.
        """
        pieces = []
        if starter is not None:
            pieces.append(starter)
        pieces.append(self.general_path)
        if is_out:
            pieces.append(self.output_folder)
        file = self.file if output_file is None else output_file
        pieces.append(file)
        ## The pieces are joined as strings (e.g. "run_" + "?.dat" can be
        ## wanted), but a missing "/" is often a mistake.
        for left, right in zip(pieces, pieces[1:]):
            if left and right and not left.endswith("/"):
                warnings.warn(
                    f"'{left}' does not end with '/', so it is joined to '{right}' "
                    f"as '{left}{right}'. Add a '/' if this is unintended.",
                    UserWarning,
                    stacklevel=3,
                )
        path = "".join(pieces[:-1])
        return path, path + file

    def _normalize_index(self, index: Union[List[int], Dict[str, int]]) -> List[int]:
        """
        Convert supported index representations to a list of indices.

        Parameters
        ----------
        index : List[int] or Dict[str, int]
            Index specification.

            If a list is provided, it is returned unchanged.

            If a dictionary is provided, keys must correspond to
            either all placeholders or all variable names.

        Returns
        -------
        List[int]
            Normalized index list matching the order of
            ``self.list_of_variables``.

        Raises
        ------
        PathResolutionError
            If required keys are missing or the dictionary keys do not
            match the manager configuration.
        """
        ## If a list (or tuple) is given this is fine.
        if isinstance(index, (list, tuple)):
            return list(index)
        if isinstance(index, dict):
            keys = set(index)
            placeholders_key = set(self.placeholders)
            if self.variable_names is not None:
                variable_keys = set(self.variable_names)
            else:
                variable_keys = set()
            if keys <= placeholders_key:
                missing = placeholders_key - keys
                if missing:
                    raise PathResolutionError(f"Missing placeholders(s): {missing}.")
                return [index[r] for r in self.placeholders]
            if keys <= variable_keys:
                missing = variable_keys - keys
                if missing:
                    raise PathResolutionError(f"Missing variable(s): {missing}.")
                return [index[name] for name in self.variable_names]
            raise PathResolutionError(
                "Index keys must match either all placeholders or all variable names."
            )
        raise PathResolutionError("Index given in a non known data type.")

    def _check_loop_placeholders(
        self, variables: Optional[List[List[str]]] = None
    ) -> bool:
        """
        Check whether the placeholders contains dependency loops.

        A dependency exists when a placeholders's possible values contain
        another placeholders.

        Example
        -------
        placeholders = ["!", "?", "$"]

        variables = [
            ["1", "2"],
            ["!LOL"],
            ["i"]
        ]

        Produces the graph:

            ? -> !

        which is valid.

        A configuration producing:

            ! -> ?
            ? -> !

        is invalid and raises a ValueError.
        """
        if variables is None:
            list_of_variables = self.list_of_variables
        else:
            list_of_variables = variables
        #
        if len(self.placeholders) != len(list_of_variables):
            raise DependencyLoopError(
                "self.placeholders and self.list_of_variables | variables must have the same length."
            )
        # Build the dependency graph.
        graph = {placeholders: set() for placeholders in self.placeholders}
        for placeholders, possible_values in zip(self.placeholders, list_of_variables):
            for value in possible_values:
                if isinstance(value, list):
                    values_to_test = value
                else:
                    values_to_test = [value]
                for subvalue in values_to_test:
                    for other_placeholders in self.placeholders:
                        if other_placeholders in str(subvalue):
                            graph[placeholders].add(other_placeholders)
        visited = set()
        recursion_stack = set()

        def dfs(node: str) -> bool:
            """
            Returns True if a cycle is found.
            """
            if node in recursion_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            recursion_stack.add(node)
            for neighbour in graph[node]:
                if dfs(neighbour):
                    return True
            recursion_stack.remove(node)
            return False

        for placeholders in self.placeholders:
            if dfs(placeholders):
                raise DependencyLoopError(
                    f"Loop detected in placeholders dependencies involving '{placeholders}'."
                )
        return True

    def _apply_replacements(self, text: str, values: List[str]) -> str:
        """
        Replace every placeholders token in `text` with its corresponding
        value from `values`, in a single pass: an inserted value is not
        replaced again (see `_resolve_recursive` for that). Longest
        placeholders tokens are matched first (to avoid partial matches
        when one placeholders is a substring of another, e.g. "$" inside "$$").

        Parameters
        ----------
        text : str
            Text containing placeholders tokens.
        values : List[str]
            Resolved values, in the same order as `self.placeholders`.

        Returns
        -------
        str
            `text` with all placeholders tokens substituted.
        """
        strings = [variable_to_string(value) for value in values]
        placeholders_regex = self._placeholders_regex()
        if not placeholders_regex.search("\0".join(strings)):
            ## No value contains a placeholders: replacing one after the other
            ## (faster) gives the same result as a single pass.
            for placeholders, string in sorted(
                zip(self.placeholders, strings),
                key=lambda pair: len(pair[0]),
                reverse=True,
            ):
                text = text.replace(placeholders, string)
            return text
        lookup = dict(zip(self.placeholders, strings))
        return placeholders_regex.sub(lambda matching: lookup[matching.group(0)], text)

    def _placeholders_regex(self) -> re.Pattern:
        """
        Regex matching any placeholders token, longest first.
        """
        return _compile_placeholders(tuple(self.placeholders))

    def _resolve_recursive(
        self, text: str, values: List[str], maximum_loop: int = 1000
    ) -> str:
        """
        Repeatedly apply `_apply_replacements` until no placeholders token
        remains, allowing a variable's value to itself contain another
        placeholders token.

        Assumes `_check_loop_placeholders` has already been called by the
        caller, so no dependency loop exists (otherwise this loops forever).

        Parameters
        ----------
        text : str
            Text containing placeholders tokens.
        values : List[str]
            Resolved values, in the same order as `self.placeholders`.
        maximum_loop : int
            The number of loops to do before one consider the class trapped in an infinite loop.

        Returns
        -------
        str
            `text` fully resolved, with no placeholders tokens left.
        """
        for _ in range(maximum_loop):
            if not self.contains_placeholders(text):
                break
            new_text = self._apply_replacements(text, values)
            if new_text == text:
                raise PathResolutionError("Replacement process stalled.")
            text = new_text
        else:
            raise PathResolutionError(
                f"Maximum replacement depth of {maximum_loop} depth reached."
            )
        return text

    def _resolve_variable(
        self,
        variable: Union[List, ReferenceVariable],
        idx: int,
        all_indices: List[int],
    ) -> Any:
        """
        Resolve a variable value for a given selection index.

        Parameters
        ----------
        variable : List or ReferenceVariable
            Variable container to resolve.

            - For a regular list, returns ``variable[idx]``.
            - For a ``ReferenceVariable``, the first index is taken from
            another variable's selected index, defined by
            ``variable.reference_position``.

        idx : int
            Index requested for the current variable.

        all_indices : List[int]
            Complete list of indices used for all variables in the current
            path conversion. This is required to resolve
            ``ReferenceVariable`` dependencies.

        Returns
        -------
        Any
            The resolved variable value.

        Raises
        ------
        ReferenceResolutionError
            If a ``ReferenceVariable`` cannot be resolved for the supplied indices.

        Examples
        --------
        >>> variables = [
        ...     ["A", "B"],
        ...     ReferenceVariable(
        ...         [["a0", "a1"],
        ...          ["b0", "b1"]],
        ...         reference_position=0,
        ...     ),
        ... ]
        >>> indices = [1, 0]
        >>> _resolve_variable(variables[1], 0, indices)
        'b0'

        The second variable uses the selected value of the first variable
        (index 1) to determine which sub-list should be accessed.
        """
        if isinstance(variable, ReferenceVariable):
            ref_idx = all_indices[variable.reference_position]
            try:
                return variable.values[ref_idx][idx]
            except IndexError as exc:
                raise ReferenceResolutionError(
                    f"ReferenceVariable resolution failed: "
                    f"reference={ref_idx}, index={idx}."
                ) from exc
        try:
            return variable[idx]
        except IndexError as exc:
            raise PathResolutionError(
                f"Index {idx} out of range for a variable of {len(variable)} values."
            ) from exc

    def _cast_variable(self, position: int, value: Any) -> Any:
        """
        Convert a variable value with the type given in ``self.variable_type``.

        If ``self.variable_type`` is None, the value is returned unchanged.

        Raises
        ------
        PathResolutionError
            If the value cannot be converted to the wished type.
        """
        if self.variable_type is None:
            return value
        var_type = self.variable_type[position]
        ## bool("False") is True, so strings are read as F90/Python logicals.
        if var_type is bool and isinstance(value, str):
            logical = value.strip().strip(".").lower()
            if logical in ("true", "t", "1"):
                return True
            if logical in ("false", "f", "0"):
                return False
            raise PathResolutionError(
                f"Cannot convert {value!r} of '{self.variable_names[position]}' with bool."
            )
        try:
            return var_type(value)
        except (TypeError, ValueError) as exc:
            raise PathResolutionError(
                f"Cannot convert {value!r} of '{self.variable_names[position]}' "
                f"with {getattr(var_type, '__name__', var_type)}."
            ) from exc

    ################################
    ### Get paths
    def resolve_path(
        self,
        index: Union[List[int], Dict[str, int]],
        is_out: bool = False,
        starter: str = None,
        recursive: bool = False,
        immutable: bool = False,
    ):
        """
        Build the wished file path by substituting placeholders tokens with
        the variables selected by `index`.

        Parameters
        ----------
        index : List[int]
            For each placeholders, the index into `self.list_of_variables`
            of the value to use.
        is_out : bool
            If True, include `self.output_folder` in the path.
        starter : str, optional
            Prefix prepended before `self.general_path`.
        recursive : bool
            If True, substitution repeats until no placeholders token
            remains, so a variable's value may itself contain another
            placeholders token. If False (default), a single pass is applied.
        immutable : bool
            If True, makes this function immutable and the paths will not be saved in the class.

        Returns
        -------
        Path
            The resolved `self.current_path_file` or resolved `path_file`.
        """
        index = self._normalize_index(index)
        if len(index) != len(self.list_of_variables):
            raise PathResolutionError(
                f"Expected {len(self.list_of_variables)} indices, "
                f"received {len(index)}."
            )
        path, path_file = self._build_path(starter=starter, is_out=is_out)
        variables = [
            self._resolve_variable(variable, idx, index)
            for variable, idx in zip(self.list_of_variables, index)
        ]
        if recursive:
            self._check_loop_placeholders()
            path = self._resolve_recursive(path, variables)
            path_file = self._resolve_recursive(path_file, variables)
        else:
            path = self._apply_replacements(path, variables)
            path_file = self._apply_replacements(path_file, variables)
        if immutable:
            return Path(path_file)
        self.current_path = Path(path)
        self.current_path_file = Path(path_file)
        return self.current_path_file

    def resolve_values(
        self,
        list_of_var: List[List[str]],
        is_out: bool = False,
        starter: str = None,
        output_file: str = None,
        recursive: bool = False,
        immutable: bool = False,
    ):
        """
        Build the wished file path by substituting placeholders tokens with
        manually supplied values (bypasses `self.list_of_variables`).

        Parameters
        ----------
        list_of_var : List
            One value per placeholders, in the same order as `self.placeholders`.
        is_out : bool
            If True, include `self.output_folder` in the path.
        starter : str, optional
            Prefix prepended before `self.general_path`.
        output_file : str, optional
            Overrides `self.file` if provided.
        recursive : bool
            If True, substitution repeats until no placeholders token
            remains, so a value may itself contain another placeholders
            token. If False (default), a single pass is applied.
        immutable : bool
            If True, makes this function immutable and the paths will not be saved in the class.

        Returns
        -------
        Path
            The resolved `self.current_path_file` or resolved `path_file`.
        """
        if len(list_of_var) != len(self.list_of_variables):
            raise PathResolutionError(
                f"Expected {len(self.list_of_variables)} indices, "
                f"received {len(list_of_var)}."
            )
        path, path_file = self._build_path(
            starter=starter, is_out=is_out, output_file=output_file
        )
        if recursive:
            self._check_loop_placeholders([[v] for v in list_of_var])
            path = self._resolve_recursive(path, list_of_var)
            path_file = self._resolve_recursive(path_file, list_of_var)
        else:
            path = self._apply_replacements(path, list_of_var)
            path_file = self._apply_replacements(path_file, list_of_var)
        if immutable:
            return Path(path_file)
        self.current_path = Path(path)
        self.current_path_file = Path(path_file)
        return self.current_path_file

    def path_general_conversion(
        self, g_path: str, g_file: str, index: Union[List[int], Dict[str, int]]
    ) -> Dict[str, Any]:
        """
        Apply a single replacement pass to a given path/file string.

        Returns
        -------
        Dict[str, List[str]]
            `path`: resolved path.
            `path_file`: resolved path + file.
            `var_used`: placeholders tokens found before substitution.
        """
        index = self._normalize_index(index)
        if len(index) != len(self.list_of_variables):
            raise PathResolutionError(
                f"Expected {len(self.list_of_variables)} indices, "
                f"received {len(index)}."
            )
        # Take data
        variables = [
            self._resolve_variable(variable, idx, index)
            for variable, idx in zip(self.list_of_variables, index)
        ]
        g_path_file = g_path if g_file == "" else str(Path(g_path) / g_file)
        var_used = self.placeholders_used(g_path_file)
        return {
            "path": self._apply_replacements(g_path, variables),
            "path_file": self._apply_replacements(g_path_file, variables),
            "var_used": var_used,
        }

    def path_recursive_general_conversion(
        self, g_path: str, g_file: str, index: Union[List[int], Dict[str, int]]
    ) -> str:
        """
        Resolve a path/file string, repeating substitution until no
        placeholders token remains.

        Raises
        ------
        ValueError
            If the placeholders/variable configuration contains a dependency
            loop (see `_check_loop_placeholders`).
        Raises
        ------
        DependencyLoopError
        """
        index = self._normalize_index(index)
        if len(index) != len(self.list_of_variables):
            raise PathResolutionError(
                f"Expected {len(self.list_of_variables)} indices, "
                f"received {len(index)}."
            )
        self._check_loop_placeholders()
        variables = [
            self._resolve_variable(variable, idx, index)
            for variable, idx in zip(self.list_of_variables, index)
        ]
        return self._resolve_recursive(g_path + g_file, variables)

    def parse(
        self,
        path: Union[str, Path],
        is_out: bool = False,
        starter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract variable values from a concrete path.

        Parameters
        ----------
        path : str or Path
            Fully resolved path matching the combination of
            ``self.general_path`` and ``self.file``. Both are normalized
            first, so ``Li/300K`` matches the template ``./?/!K/``.
            A placeholders used several times must have the same value.
        is_out, starter
            Same as in ``resolve_path``, for paths built with them.

        Returns
        -------
        Dict[str, Any]
            Dictionary mapping variable names to the values extracted
            from the path (converted by ``variable_type`` if given).

        Raises
        ------
        PathResolutionError
            If the provided path does not match the template defined
            by this manager.

        Examples
        --------
        >>> gwpm.parse("./Li/300K/output.dat")
        {'element': 'Li', 'temperature': '300K'}
        """
        pattern = os.path.normpath(self._build_path(starter=starter, is_out=is_out)[1])
        path = os.path.normpath(str(path))
        ## Build the regex token by token: one group per variable (groups
        ## named g<position> as variable names may not be valid group names),
        ## and a back reference when a placeholders is used again.
        positions = {
            placeholders: position
            for position, placeholders in enumerate(self.placeholders)
        }
        regex = ""
        used = set()
        for token in re.split(f"({self._placeholders_regex().pattern})", pattern):
            if token in positions:
                position = positions[token]
                if position in used:
                    regex += f"(?P=g{position})"
                else:
                    regex += f"(?P<g{position}>.+)"
                    used.add(position)
            else:
                regex += re.escape(token)
        matching = re.match("^" + regex + "$", path)
        if matching is None:
            raise PathResolutionError(f"Path does not match template: {path}.")
        return {
            self.variable_names[position]: self._cast_variable(
                position, matching.group(f"g{position}")
            )
            for position in sorted(used)
        }

    def resolve(self, values: Optional[Dict[str, object]] = None, **kwargs) -> Path:
        """
        Resolve a path from variable values rather than indices.

        Parameters
        ----------
        values : dict, optional
            Mapping between variable names and either:

            - a variable value (compared after conversion by
              ``variable_type`` if given, else directly)
            - an integer index into the variable list, used only when
              the integer is not one of the variable's values.

            ``ReferenceVariable`` values are searched in the sub-list
            selected by the referenced variable.

        **kwargs
            Alternative way of supplying variable values.

        Returns
        -------
        pathlib.Path
            Fully resolved path.

        Raises
        ------
        KeyError
        PathResolutionError

        Examples
        --------
        >>> gwpm.resolve(
        ...     element="Li",
        ...     temperature="300K"
        ... )
        PosixPath('Li/300K/output.dat')
        """
        values = {**(values or {}), **kwargs}
        indices = []
        for position, (name, variable) in enumerate(
            zip(self.variable_names, self.list_of_variables)
        ):
            if name not in values:
                raise KeyError(f"Missing variable '{name}'.")
            value = values[name]
            if isinstance(variable, ReferenceVariable):
                ref_idx = indices[variable.reference_position]
                try:
                    candidates = variable.values[ref_idx]
                except IndexError as exc:
                    raise ReferenceResolutionError(
                        f"ReferenceVariable '{name}' has no values for reference={ref_idx}."
                    ) from exc
            else:
                candidates = variable
            ## First the values, then the integer as an index.
            matches = [
                i
                for i, candidate in enumerate(candidates)
                if self._cast_variable(position, candidate) == value
            ]
            if matches:
                indices.append(matches[0])
            elif isinstance(value, int) and not isinstance(value, bool):
                if not -len(candidates) <= value < len(candidates):
                    raise PathResolutionError(
                        f"{value} is neither a value nor a valid index for {name}."
                    )
                indices.append(value)
            else:
                raise PathResolutionError(f"{value!r} not available for {name}.")
        return self.resolve_path(indices, immutable=True)

    ################################
    ### Get the data from the gwpm.
    def get_placeholder_series(
        self,
        starter: str = None,
        is_out: bool = False,
        placeholder: Optional[str] = None,
        use_current: bool = True,
        path: Optional[Union[str, Path]] = None,
    ):
        """
        Create a placeholder series from a resolved path.

        Parameters
        ----------
        starter : str, optional
            Prefix added before the path (only with ``use_current=False``).
        is_out : bool, default=False
            If True, append ``output_folder`` (only with ``use_current=False``).
        placeholder : str, optional
            Placeholder delimiter used by ``PlaceholderSeries``, by
            default ``self.series_placeholder`` ("<ID>").
        use_current : bool, default=True
            If True, use the path of the last ``resolve_path``.
            ``use_current=False`` (the unresolved template) is deprecated:
            its folder still contains the placeholders, so no file is found.
        path : str or Path, optional
            Resolved path of the series, e.g. from ``all_paths`` or
            ``all_paths_and_variables``. Used instead of the current path.

        Returns
        -------
        PlaceholderSeries
            Series object configured from the resolved path.

        Examples
        --------
        >>> for variables, path in gwpm.all_paths_and_variables():
        ...     series = gwpm.get_placeholder_series(path=path)
        """
        if path is None and not use_current:
            warnings.warn(
                "use_current=False is deprecated: the template still contains "
                "the placeholders, so no file can be found. Give the resolved "
                "path instead, e.g. get_placeholder_series(path=path) with a "
                "path from all_paths_and_variables().",
                DeprecationWarning,
                stacklevel=2,
            )
        return self._placeholder_series(starter, is_out, placeholder, use_current, path)

    def _placeholder_series(
        self,
        starter: Optional[str],
        is_out: bool,
        placeholder: Optional[str],
        use_current: bool,
        path: Optional[Union[str, Path]],
    ) -> PlaceholderSeries:
        """
        Build the series of ``get_placeholder_series`` (without the
        deprecation warning, so callers can raise it at their own level).
        """
        if placeholder is None:
            placeholder = self.series_placeholder
        if path is not None:
            path_file = str(path)
            if self.contains_placeholders(path_file):
                raise PathResolutionError(
                    f"The path still contains placeholders "
                    f"{self.placeholders_used(path_file)}: {path_file}."
                )
        elif use_current:
            if self.current_path_file is None:
                raise PathResolutionError("No current path available.")
            path_file = str(self.current_path_file)
        else:
            _, path_file = self._build_path(
                starter=starter,
                is_out=is_out,
            )
        return PlaceholderSeries(
            path_file,
            placeholder=placeholder,
        )

    def read_placeholder_series(
        self,
        reader: BaseSeriesReader,
        starter: str = None,
        is_out: bool = False,
        is_merged: bool = True,
        use_current: bool = True,
        placeholder: Optional[str] = None,
        path: Optional[Union[str, Path]] = None,
    ):
        """
        Read the files of a placeholder series.

        Parameters
        ----------
        reader : BaseSeriesReader
            Reader implementation used to process the series.
        starter : str, optional
            Prefix added before the path (only with ``use_current=False``).
        is_out : bool, default=False
            If True, append ``output_folder`` (only with ``use_current=False``).
        is_merged : bool, default=True
            If True, return the merged result from all matched files.
            Otherwise return the individual results.
        use_current : bool, default=True
            If True, use the path of the last ``resolve_path``.
            ``use_current=False`` is deprecated (see ``get_placeholder_series``).
        placeholder : str, optional
            Placeholder delimiter used by ``PlaceholderSeries``, by
            default ``self.series_placeholder`` ("<ID>").
        path : str or Path, optional
            Resolved path of the series, e.g. from ``all_paths`` or
            ``all_paths_and_variables``. Used instead of the current path.

        Returns
        -------
        Any
            Result returned by the selected reader implementation.

        Examples
        --------
        >>> for variables, path in gwpm.all_paths_and_variables():
        ...     atoms = gwpm.read_placeholder_series(ASEReader(), path=path)
        """
        if path is None and not use_current:
            warnings.warn(
                "use_current=False is deprecated: the template still contains "
                "the placeholders, so no file can be found. Give the resolved "
                "path instead, e.g. read_placeholder_series(reader, path=path) "
                "with a path from all_paths_and_variables().",
                DeprecationWarning,
                stacklevel=2,
            )
        series = self._placeholder_series(
            starter, is_out, placeholder, use_current, path
        )
        return reader.read_merged(series) if is_merged else reader.read_all(series)
