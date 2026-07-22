from typing import Union, Optional, Any, List, Tuple,  Dict
from dataclasses import dataclass
from itertools import product
from pathlib import Path
import re
import pandas as pd
import json
import pickle


from gwpm.utils import variable_to_string
from gwpm.series_reader import PlaceholderSeries,BaseSeriesReader

## Error classes
class GWPMError(Exception):
    """Base exception for all GWPM errors."""
    pass
class ReferenceResolutionError(GWPMError):
    """Raised when a ReferenceVariable cannot be resolved."""
    pass
class ReplacerConfigurationError(GWPMError):
    """Raised for invalid replacer configurations."""
    pass
class DependencyLoopError(GWPMError):
    """Raised when recursive replacer dependencies form a loop."""
    pass
class PathResolutionError(GWPMError):
    """Raised when path generation fails."""
    pass
class SerializationError(GWPMError):
    """Raised during save/load operations."""
    pass
#####

@dataclass
class ReferenceVariable():
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
    values:List[List[Any]]
    reference_position : int

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"reference_position={self.reference_position})"
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
            "__type__" : self.__class__.__name__,
            "values": self.values,
            "reference_position": self.reference_position,
        }
    @classmethod
    def from_dict(cls, data):
        return cls(
            values=data["values"],
            reference_position=data[
                "reference_position"
            ]
        )


class GeneralWorkPathManager():
    """
    Manage collections of related file paths that differ only by a set of
    placeholder variables.

    The class generates concrete paths by replacing user-defined placeholder
    tokens (``self.replacer``) with values selected from
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
    ...     replacer=["?", "!"],
    ... )

    >>> gwpm.path_conversion([0, 1])
    './Li/600K/'
    """
    __version__ : str = "1.3.0"
    def __init__(
        self,
        list_of_variables: List[Union[List[Any],ReferenceVariable]],
        replacer: List[str],
        path: str = "./",
        file: str = "",
        variable_names: Optional[List[str]]=None,
        output_folder: str = "./output/",
        verbose: bool = False,
        )->None:
        if replacer is None:
            raise ValueError("Replacer must be given.")
        if len(set(replacer)) != len(replacer):
            raise ValueError("Replacers must be unique.")
        if len(list_of_variables) == 1:
            replacer = [replacer[0]]
        if len(list_of_variables) != len(replacer):
            raise IndexError("The list of variables in the folder tree must be the same as the one of the replacer.")
        for i, variable in enumerate(list_of_variables):
            if isinstance(variable,ReferenceVariable):
                ref = variable.reference_position
                if ref < 0:
                    ref = i + ref
                if ref < 0 or ref >= len(list_of_variables):
                    raise IndexError("ReferenceVariable cannot reference itself.")
                if ref == i:
                    raise ValueError("ReferenceVariable cannot reference itself.")
                if ref > i:
                    raise ValueError(
                        "ReferenceVariable must reference a previous variable."
                    )
                variable.reference_position = ref
        if variable_names is None:
            variable_names = [
                f"var_{i}"
                for i in range(len(list_of_variables))
            ]
        self.list_of_variables  = list_of_variables
        self.replacer           = replacer
        self.variable_names     = variable_names
        self.general_path       = path
        ### I want this to become a Path object, and be setup once all replacements are done like this it works through all the OSes.
        self.current_path       = path
        self.current_path_file  = path + file
        self.file               = file
        self.output_folder      = output_folder
        self.verbose            = verbose
        if self.file.lower() == "none":
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
            f"file='{self.file}')")
    def __str__(self):
        return (
            f"{self.__class__.__name__}\n"
            f"├── general_path       : {self.general_path}\n"
            f"├── file               : {self.file}\n"
            f"├── current_path       : {self.current_path}\n"
            f"├── current_path_file  : {self.current_path_file}\n"
            f"├── output_folder      : {self.output_folder}\n"
            f"├── replacers          : {self.replacer}\n"
            f"└── n_variables        : {len(self.list_of_variables)}"
        )
    def __len__(self) -> int:
        return len(self.list_of_variables)
    def __iter__(self):
        return iter(zip(self.replacer,self.list_of_variables))
    def __getitem__(self, item):
        if isinstance(item, int):
            return self.list_of_variables[item]
        if isinstance(item, str):
            try:
                idx = self.replacer.index(item)
            except ValueError:
                raise KeyError(f"Unknown replacer '{item}'.")
            return self.list_of_variables[idx]
        raise TypeError("Item must be an integer or a replacer string.")
    def __contains__(self, item) -> bool:
        return item in self.replacer
    def __eq__(self, other) -> bool:
        if not isinstance(other,GeneralWorkPathManager):
            return False
        return (
            self.list_of_variables == other.list_of_variables
            and self.replacer == other.replacer
            and self.general_path == other.general_path
            and self.file == other.file
            and self.output_folder == other.output_folder
            )
    def keys(self):
        """
        Return all replacers.
        """
        return self.replacer
    def values(self):
        """
        Return all variables.
        """
        return self.list_of_variables
    def items(self):
        """
        Return (replacer, variable) pairs.
        """
        return list(zip(self.replacer,self.list_of_variables))
    @property
    def current(self)->Dict[str,str]:
        """
        Return the most recently resolved path information.

        Returns
        -------
        Dict[str, str]
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
    def replacer_used(self,text_to_test:str)->List[str]: 
        """
        Return the replacer tokens present in a string.

        Parameters
        ----------
        text_to_test : str
            Text to inspect.

        Returns
        -------
        List[str]
            List of replacer tokens found in the order defined by
            ``self.replacer``.
        """
        rep_used = []
        for r in self.replacer:
            if text_to_test.__contains__(r):
                rep_used.append(r)
        return rep_used
    def contains_replacer(self,text_to_test:str)->bool:
        """
        Check whether a string contains any replacer token.

        Parameters
        ----------
        text_to_test : str
            Text to inspect.

        Returns
        -------
        bool
            True if at least one replacer token is present, otherwise False.
        """
        for r in self.replacer:
            if text_to_test.__contains__(r):
                return True
        return False
    def iter_paths(self):
        """
        Iterate over all possible path combinations.
        
        Yields
        -------
        tuple
            (indices, resolved_path)
        """
        ranges = [ range(len(v)) for v in self.list_of_variables ]
        for index in product(*ranges):
            data = {
                name: self._resolve_variable(
                    variable,
                    index[i],
                    list(index),
                )
                for i, (name, variable) in enumerate(
                    zip(self.variable_names, self.list_of_variables)
                )
            }
            data["index"]   = list(index)
            data["path"]    = self.path_conversion(list(index),immutable=True)
            yield data
    ###################################################
    ### Save, load and return data.
    def all_paths(self):
        """Return all generated paths as a list."""
        return [item["path"] for item in self.iter_paths()]
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
            "list_of_variables":
                serialized_variables,
            "replacer":
                self.replacer,
            "variable_names":
                self.variable_names,
            "path":
                self.general_path,
            "file":
                self.file,
            "output_folder":
                self.output_folder,
            "verbose":
                self.verbose,
        }
    def to_dataframe(self) -> pd.DataFrame:
        """
        Export the manager configuration as a pandas DataFrame.
        """
        df = pd.DataFrame(self.iter_paths())
        df.attrs["gwpm_config"] = self.to_dict()
        return df
    def to_json(self,filename:str)->None:
        with open(filename,"w") as f:
            json.dump(self.to_dict(), f, indent=4)
        return
    def save(self,filename:str):
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
        with open(filename,"wb") as f:
            pickle.dump(self,f)
    @classmethod
    def from_dict(cls, data: dict):
        """
        Reconstruct a manager from a
        dictionary produced by ``to_dict``.
        """
        variables = []
        for var in data["list_of_variables"]:
            if ( isinstance(var, dict) and var.get("__type__") == "ReferenceVariable"):
                variables.append(ReferenceVariable.from_dict(var))
            else:
                variables.append(var)
        return cls(
            list_of_variables=variables,
            path=data["path"],
            file=data["file"],
            output_folder=data["output_folder"],
            replacer=data["replacer"],
            variable_names=data.get("variable_names"),
            verbose=data.get("verbose",False,)
            )
    @classmethod
    def from_dataframe(cls, data:pd.DataFrame):
        """
        Reconstruct a manager from a
        dictionary produced by ``to_dataframe``.
        """
        return cls.from_dict(data.attrs["gwpm_config"])
    @classmethod
    def from_json(cls, filename:str):
        with open(filename) as f:
            data = json.load(f)
        return cls.from_dict(data)
    @classmethod
    def load(cls,filename:str):
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
        with open(filename,'rb') as f:
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
        path = ""
        if starter is not None:
            path += starter
        path += self.general_path
        if is_out:
            path += self.output_folder
        file = self.file if output_file is None else output_file
        return path, path + file
    def _normalize_index(self,index:Union[List[int],Dict[str,int]]) -> List[int]:
        """
        Convert supported index representations to a list of indices.

        Parameters
        ----------
        index : List[int] or Dict[str, int]
            Index specification.

            If a list is provided, it is returned unchanged.

            If a dictionary is provided, keys must correspond to
            either all replacers or all variable names.

        Returns
        -------
        List[int]
            Normalized index list matching the order of
            ``self.list_of_variables``.

        Raises
        ------
        KeyError
            If required keys are missing or the dictionary keys do not
            match the manager configuration.
        """
        ## If a list is given this is fine.
        if isinstance(index,list):
            return index
        if isinstance(index,dict):
            keys = set(index)
            replacer_key = set(self.replacer)
            if self.variable_names is not None:
                variable_keys = set(self.variable_names)
            else:
                variable_keys = set()
            if keys <= replacer_key:
                missing = replacer_key - keys
                if missing:
                    raise PathResolutionError(f'Missing replacer(s): {missing}.')
                return [index[r] for r in self.replacer]
            if keys <= variable_keys:
                missing = variable_keys - keys
                if missing:
                    raise PathResolutionError(f'Missing variable(s): {missing}.')
                return [index[name] for name in self.variable_names]
            raise PathResolutionError("Index key must match either all replacers or all variable names.")
        raise PathResolutionError("Index given in a non known data type.")
    def _check_loop_replacers(self,variables:Optional[List[List[str]]]=None)->bool:
        """
        Check whether the replacer contains dependency loops.

        A dependency exists when a replacer's possible values contain
        another replacer.

        Example
        -------
        replacers = ["!", "?", "$"]

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
        if len(self.replacer) != len(list_of_variables):
            raise DependencyLoopError(
                "self.replacer and self.list_of_variables | variables must have the same length."
            )
        # Build the dependency graph.
        graph = {replacer: set() for replacer in self.replacer}
        for replacer, possible_values in zip(
            self.replacer,
            list_of_variables
            ):
            for value in possible_values:
                if isinstance(value,list):
                    values_to_test   = value
                else:
                    values_to_test  = [value]
                for subvalue in values_to_test:
                    for other_replacer in self.replacer:
                        if other_replacer in str(subvalue):
                            graph[replacer].add(other_replacer)
        visited         = set()
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
        for replacer in self.replacer:
            if dfs(replacer):
                raise DependencyLoopError(
                    f"Loop detected in replacer dependencies involving '{replacer}'."
                )
        return True
    def _apply_replacements(self,text: str, values:List[str]) -> str:
        """
        Replace every replacer token in `text` with its corresponding
        value from `values`, longest replacer token first (to avoid
        partial matches when one replacer is a substring of another,
        e.g. "$" inside "$$").

        Parameters
        ----------
        text : str
            Text containing replacer tokens.
        values : List[str]
            Resolved values, in the same order as `self.replacer`.

        Returns
        -------
        str
            `text` with all replacer tokens substituted.
        """
        for replacer, value in sorted(
            zip(self.replacer, values), key=lambda pair: len(pair[0]), reverse=True
        ):
            text = text.replace(replacer, variable_to_string(value))
        return text
    def _resolve_recursive(self,text: str, values:List[str],maximum_loop:int=1000) -> str:
        """
        Repeatedly apply `_apply_replacements` until no replacer token
        remains, allowing a variable's value to itself contain another
        replacer token.

        Assumes `_check_loop_replacers` has already been called by the
        caller, so no dependency loop exists (otherwise this loops forever).

        Parameters
        ----------
        text : str
            Text containing replacer tokens.
        values : List[str]
            Resolved values, in the same order as `self.replacer`.
        maximum_loop : int
            The number of loops to do before one consider the class trapped in an infinite loop.

        Returns
        -------
        str
            `text` fully resolved, with no replacer tokens left.
        """
        for _ in range(maximum_loop):
            if not self.contains_replacer(text):
                break
            new_text = self._apply_replacements(text,values)
            if new_text == text:
                raise PathResolutionError("Replacement process stalled.")
            text = new_text
        else:
            raise PathResolutionError(f"Maximum replacement depth of {maximum_loop} depth reached.")
        return text
    def _resolve_variable(
        self,
        variable: Union[List, ReferenceVariable],
        idx : int,
        all_indices : List[int],
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
        IndexError
            If a ``ReferenceVariable`` points to a valid variable but the
            resolved nested index does not exist.

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
        return variable[idx]
    ################################
    ### Get paths
    def path_conversion(
        self, 
        index: Union[List[int],Dict[str,int]], 
        is_out: bool = False, 
        starter: str = None, 
        recursive:bool=False,
        immutable:bool=False,):
        """
        Build the wished file path by substituting replacer tokens with
        the variables selected by `index`.

        Parameters
        ----------
        index : List[int]
            For each replacer, the index into `self.list_of_variables`
            of the value to use.
        is_out : bool
            If True, include `self.output_folder` in the path.
        starter : str, optional
            Prefix prepended before `self.general_path`.
        recursive : bool
            If True, substitution repeats until no replacer token
            remains, so a variable's value may itself contain another
            replacer token. If False (default), a single pass is applied.
        immutable : bool
            If True, makes this function immutable and the paths will not be saved in the class.
            
        Returns
        -------
        str
            The resolved `self.current_path_file` or resolved `path_file`.
        """
        index = self._normalize_index(index)
        if len(index) != len(self.list_of_variables):
            raise PathResolutionError(
                f"Expected {len(self.list_of_variables)} indices, "
                f"received {len(index)}."
            )
        if immutable:
            path = ""
            path_file = ""
            if starter is not None:
                path += starter
            path += self.general_path
            if is_out:
                path += self.output_folder
            path_file = path + self.file
            variables = [ self._resolve_variable(variable, idx, index) for variable, idx in zip(self.list_of_variables, index) ]
            if recursive:
                self._check_loop_replacers()
                path_file = self._resolve_recursive(path_file, variables)
            else:
                path_file = self._apply_replacements(path_file, variables)
            return path_file
        # Reinitialisation
        self.current_path = ""
        self.current_path_file = ""
        if starter is not None:
            self.current_path += starter
        self.current_path += self.general_path
        if is_out:
            self.current_path += self.output_folder
        self.current_path_file = self.current_path + self.file
        # Take data
        variables = [ self._resolve_variable(variable, idx, index) for variable, idx in zip(self.list_of_variables, index) ]
        # Replacing
        if recursive:
            self._check_loop_replacers()
            self.current_path = self._resolve_recursive(self.current_path,variables)
            self.current_path_file = self._resolve_recursive(self.current_path_file, variables)
        else:
            self.current_path = self._apply_replacements(self.current_path,variables)
            self.current_path_file = self._apply_replacements(self.current_path_file, variables)
        return self.current_path_file
    def path_manual_conversion(
        self,
        list_of_var: List[List[str]],
        is_out: bool = False,
        starter: str = None,
        output_file: str = None,
        recursive:bool=False,
        immutable:bool=False,):
        """
        Build the wished file path by substituting replacer tokens with
        manually supplied values (bypasses `self.list_of_variables`).

        Parameters
        ----------
        list_of_var : List
            One value per replacer, in the same order as `self.replacer`.
        is_out : bool
            If True, include `self.output_folder` in the path.
        starter : str, optional
            Prefix prepended before `self.general_path`.
        output_file : str, optional
            Overrides `self.file` if provided.
        recursive : bool
            If True, substitution repeats until no replacer token
            remains, so a value may itself contain another replacer
            token. If False (default), a single pass is applied.
        immutable : bool
            If True, makes this function immutable and the paths will not be saved in the class.
            
        Returns
        -------
        str
            The resolved `self.current_path_file` or resolved `path_file`.
        """
        if len(list_of_var) != len(self.list_of_variables):
            raise IndexError(
                f"Expected {len(self.list_of_variables)} indices, "
                f"received {len(list_of_var)}."
            )
        if immutable:
            path = ""
            path_file = ""
            if starter is not None:
                path += starter
            path += self.general_path
            if is_out:
                path += self.output_folder
            path_file = path + self.file
            if recursive:
                self._check_loop_replacers([[v] for v in list_of_var])
                path_file = self._resolve_recursive(path_file, list_of_var)
            else:
                path_file = self._apply_replacements(path_file, list_of_var)
            return path_file
        # Reinitialisation
        self.current_path = ""
        self.current_path_file = ""
        if len(list_of_var) != len(self.replacer):
            raise PathResolutionError(
                "The list of variables in the folder tree must be the same as the one of the replacer."
            )
        if starter is not None:
            self.current_path += starter
        self.current_path += self.general_path
        if is_out:
            self.current_path += self.output_folder
        if output_file is not None:
            self.current_path_file = self.current_path + output_file
        else:
            self.current_path_file = self.current_path + self.file
        # Replacing
        if recursive:
            self._check_loop_replacers([[v] for v in list_of_var])
            self.current_path = self._resolve_recursive(self.current_path, list_of_var)
            self.current_path_file = self._resolve_recursive(self.current_path_file, list_of_var)
        else:
            self.current_path = self._apply_replacements(self.current_path, list_of_var)
            self.current_path_file = self._apply_replacements(self.current_path_file, list_of_var)
        return self.current_path_file
    def path_general_conversion(
            self,
            g_path:str,
            g_file:str,
            index: Union[List[int],Dict[str,int]]
            )->Dict[ str, List[str] ]:
        """
        Apply a single replacement pass to a given path/file string.

        Returns
        -------
        Dict[str, List[str]]
            `path`: resolved path.
            `path_file`: resolved path + file.
            `var_used`: replacer tokens found before substitution.
        """
        index = self._normalize_index(index)
        if len(index) != len(self.list_of_variables):
            raise PathResolutionError(
                f"Expected {len(self.list_of_variables)} indices, "
                f"received {len(index)}."
            )
        # Take data
        variables = [ self._resolve_variable(variable, idx, index) for variable, idx in zip(self.list_of_variables, index) ]
        g_path_file = g_path if g_file == '' else str(Path(g_path) / g_file)
        var_used    = self.replacer_used(g_path_file)
        return {
                "path": self._apply_replacements(g_path, variables),
                "path_file": self._apply_replacements(g_path_file, variables),
                "var_used": var_used,
            }
    def path_recursive_general_conversion(
            self,
            g_path:str,
            g_file:str,
            index: Union[List[int],Dict[str,int]]
            )->str:
        """
        Resolve a path/file string, repeating substitution until no
        replacer token remains.

        Raises
        ------
        ValueError
            If the replacer/variable configuration contains a dependency
            loop (see `_check_loop_replacers`).
        """
        index = self._normalize_index(index)
        self._check_loop_replacers()
        variables = [ self._resolve_variable(variable, idx, index) for variable, idx in zip(self.list_of_variables, index) ]
        return self._resolve_recursive(g_path + g_file, variables)
    def parse(self,path:str)->Dict[str,str]:
        """
        Extract variable values from a concrete path.

        Parameters
        ----------
        path : str
            Fully resolved path matching the combination of
            ``self.general_path`` and ``self.file``.

        Returns
        -------
        Dict[str, str]
            Dictionary mapping variable names to the values extracted
            from the path.

        Raises
        ------
        ValueError
            If the provided path does not match the template defined
            by this manager.

        Examples
        --------
        >>> gwpm.parse("./Li/300K/output.dat")
        {'element': 'Li', 'temperature': '300K'}
        """
        pattern = (self.general_path + self.file)
        regex = re.escape(pattern)
        for replacer, name in zip(self.replacer,self.variable_names):
            regex = regex.replace(re.escape(replacer),f'(?P<{name}>.+)')
        matching = re.match("^" + regex + '$', path)
        if matching is None:
            raise PathResolutionError(f"Path does not match template: {path}.")
        return matching.groupdict()
    def resolve(self, values : Optional[Dict[str,object]] = None, **kwargs) -> Path:
        """
        Resolve a path from variable values rather than indices.

        Parameters
        ----------
        values : dict, optional
            Mapping between variable names and either:

            - a variable value
            - an integer index into the variable list

        **kwargs
            Alternative way of supplying variable values.

        Returns
        -------
        pathlib.Path
            Fully resolved path.

        Raises
        ------
        KeyError
            If a required variable is missing.

        ValueError
            If a supplied value does not exist in the corresponding
            variable list.

        Examples
        --------
        >>> gwpm.resolve(
        ...     element="Li",
        ...     temperature="300K"
        ... )
        PosixPath('Li/300K/output.dat')
        """
        if values is None:
            values = {}
        values.update(kwargs)
        resolved_values = []
        for name, variable in zip(self.variable_names,self.list_of_variables):
            if name not in values:
                raise KeyError(f"Missing variable '{name}'.")
            value = values[name]
            if isinstance(value,int):
                resolved_values.append(variable[value])
            else:
                if value not in variable:
                    raise PathResolutionError(f"{value} not available for {name}.")
                resolved_values.append(value)        
        return Path(self._apply_replacements(self.general_path+self.file,resolved_values))
    ################################
    ### Get the data from the gwpm.
    def get_placeholder_series(
        self,
        starter: str = None,
        is_out: bool = False,
        placeholder: str = "[",
        use_current: bool = True,
    ):
        """
        Create a placeholder series from the current path configuration.

        Parameters
        ----------
        starter : str, optional
            Prefix added before the path.
        is_out : bool, default=False
            If True, append ``output_folder``.
        placeholder : str, default="["
            Placeholder delimiter used by ``PlaceholderSeries``.
        use_current : bool, default=True
            Is the current placeholder tested is using current structure.

        Returns
        -------
        PlaceholderSeries
            Series object configured from the current path template.
        """
        path = ""
        if use_current:
            path += self.current_path_file
        else:
            if starter is not None:
                path += starter
            path += self.general_path
            if is_out:
                path += self.output_folder
            path += self.file
        return PlaceholderSeries(path,placeholder=placeholder,)
    def read_placeholder_series(
        self,
        reader:BaseSeriesReader,
        starter: str = None,
        is_out: bool = False,
        is_merged:bool= True,
        use_current: bool = True,
        placeholder: str = "["):
        """
        Read files matching the current placeholder pattern.

        Parameters
        ----------
        reader : BaseSeriesReader
            Reader implementation used to process the series.
        starter : str, optional
            Prefix added before the path.
        is_out : bool, default=False
            If True, append ``output_folder``.
        is_merged : bool, default=True
            If True, return the merged result from all matched files.
            Otherwise return the individual results.
        use_current : bool, default=True
            Is the current placeholder tested is using current structure.
        placeholder : str, default="["
            Placeholder delimiter used by ``PlaceholderSeries``.

        Returns
        -------
        Any
            Result returned by the selected reader implementation.
        """
        series = self.get_placeholder_series(
            starter=starter,
            is_out=is_out,
            placeholder=placeholder,
            use_current=use_current,
        ) 
        return ( reader.read_merged(series) if is_merged else reader.read_all(series) )
