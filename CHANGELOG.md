# Changelog

## 1.1.0

Features:
- `variable_type` option of `GeneralWorkPathManager`: one type (callable) per variable, missing ones are `str`. Used by `iter_paths`, `to_dataframe`, `all_paths_and_variables` and `parse`.
- `GeneralWorkPathManager.all_paths_and_variables()`: return `(variables, path)` pairs to set up everything in a single loop (e.g. with shephex).
- `check_folder_parallel(folders, n_workers=8)`: create many folders in parallel (threads), each folder and parent once, level by level. Useful on Lustre/NFS.
- The default series placeholder is now `<ID>` (was `[`), set with the new `series_placeholder` option of `GeneralWorkPathManager` and used by `get_placeholder_series` / `read_placeholder_series`. A gwpm placeholder overlapping it (e.g. `<`, `ID`, `<ID>`) raises `ReplacerConfigurationError`.
- A `UserWarning` is raised when two template pieces (`starter`, `path`, `output_folder`, `file`) are joined without `/` (e.g. `./?/!K` + `out.dat` -> `./?/!Kout.dat`), as it may be unintended.
- `GeneralWorkPathManager.create_folders()`: create the folders of every combination with `check_folder_parallel`, using only the folder part of the template (`file` is never created as a folder).
- `get_placeholder_series` / `read_placeholder_series` take a `path=` argument: the resolved path of a series (e.g. from `all_paths_and_variables`), read without changing the current path. `use_current=False` is deprecated (`DeprecationWarning`), as the unresolved template cannot match any file.
- `iter_paths`, `all_paths` and `all_paths_and_variables` take the `is_out`, `starter` and `recursive` options of `resolve_path`; `parse` takes `is_out` and `starter`.

Fixes:
- Series readers raise `BaseSeriesReaderError` when the folder or the files of a series are not found, instead of returning empty data (#1).
- `LammpsLogReader` reads the columns from the `Step ...` header (any `thermo_style`), concatenates all the runs of a log, skips `WARNING` lines, and raises `BaseSeriesReaderError` when no thermo table is found, on a LAMMPS `ERROR`, on a table not closed by `Loop time` (crashed run) or on a line with a wrong number of values.
- `ASEReader.merge` works with an integer `index` (one `Atoms` per file) instead of splitting the structures into `Atom` objects.
- `LammpsDumpReader` raises `BaseSeriesReaderError` when `Z_of_type` is missing or when no structure is read (empty file, index out of range).
- `ThermoLogReader` raises `BaseSeriesReaderError` when the required columns are missing from the header.
- `PlaceholderSeries` builds the paths of existing files from their real names, so series without zero padding (`log_1`, `log_10`) are read correctly; it raises `PlaceHolderSeriesError` when a value is found twice (`1.txt` and `01.txt`) or when the placeholder is not in the last part of the pattern.
- `iter_paths` / `all_paths` / `to_dataframe` now follow the length of the selected sub-list of a `ReferenceVariable` (they used the number of sub-lists before).

Fixes from stress testing:
- `resolve` matches the values first (converted by `variable_type` if given), and uses an integer as an index only when it is not one of the variable's values. It now works with `ReferenceVariable` values and no longer modifies the given dict.
- `parse` accepts `Path` objects and normalized paths, so the paths of `all_paths` can be parsed back. It supports a placeholder used several times (same value required), overlapping placeholders (`?` and `??`) and any variable name.
- Without `recursive`, the replacement is done in a single pass: a value containing another placeholder is no longer replaced.
- Configuration errors raised for empty placeholders, `variable_names` of the wrong length or duplicated, and more placeholders than variables (they were silently dropped). `placeholders` may be given as a string for one variable.
- `variable_type=[bool]` reads `"False"`, `"0"`, `".FALSE."` as `False`.
- `__eq__` compares `variable_names` and `variable_type`.
- Index out of range raises `PathResolutionError`.
- numpy values (e.g. `np.arange`) are supported in paths and in `to_json`.
- `variable_to_string`: zeros after the sign for negative numbers (`-5` -> `-005`), `nan` and `inf` supported.
- `variable_to_string`: `trailing_zero` is the number of decimal digits for every float (`1.23` with `trailing_zero=6` -> `1.230000`, was `1.2300`); integers are no longer changed by it (`5` with `trailing_zero=3` was `500`).
- `PlaceholderSeries` reads its folder at each call (files written later are found), accepts `Path` patterns, and gives the right `names` for folder series.
- `LammpsLogReader` skips text lines inside a thermo table (e.g. `SHAKE stats`).
- `LammpsDumpReader`: correct structures when the number of atoms changes between frames, triclinic cells, scaled positions (`xs ys zs`), `element` column, string indices such as `"-1"`, and file name in the errors.
- `all_paths` / `iter_paths` are about 25% faster.
- A `ReferenceVariable` given with a negative `reference_position` is no longer modified, so it can be reused in another manager.
- `LammpsLogReader.merge` / `ThermoLogReader.merge` shift the steps only for a run that restarted its step count; runs that continue it (e.g. LAMMPS `read_restart`) are no longer counted twice.
- `PlaceHolderSeriesError` and `BaseSeriesReaderError` inherit from `GWPMError`.
- `FunctionReader` checks that `read_function` is callable.
- `file=None` is the same as `file=""`; tuple indices are accepted; `gwpm["name"]` works with variable names; `path_recursive_general_conversion` checks the number of indices.

## 1.0.0

Initial public release.

Features:
- `GeneralWorkPathManager`: build families of paths from a template (`path` + `file`) where placeholder tokens are replaced by the values of `list_of_variables`.
  - `resolve_path` from indices (list, or dict keyed by placeholders or `variable_names`), mutable (sets `current_path` / `current_path_file`) or immutable.
  - `resolve` from variable values, `resolve_values` from manually given values, `parse` to recover the variables from a resolved path.
  - Recursive placeholders (`recursive=True`): a value may contain other placeholders, with dependency-loop detection.
  - `starter` prefix and `output_folder` (`is_out=True`) to build related paths from the same template.
  - `iter_paths` / `all_paths` over every combination.
  - Serialization: `to_dict` / `from_dict`, `to_json` / `from_json`, `to_dataframe` / `from_dataframe`, `save` / `load` (pickle).
- `ReferenceVariable`: a variable whose values depend on the index chosen for a previous variable (e.g. temperatures per structure).
- `PlaceholderSeries`: series of numbered files or folders (restarts, segments, ...) found from a single placeholder in a file name.
- Readers for series (`read`, `read_all`, `read_merged`): `CSVReader`, `ASEReader`, `PymatgenReader`, `LammpsDumpReader`, `LammpsLogReader`, `ThermoLogReader`, `FunctionReader` (any user function), and the `BaseSeriesReader` base class for custom readers. Also available from a manager with `get_placeholder_series` / `read_placeholder_series`.
- Utilities: `check_folder`, `variable_to_string` (formatting of numbers, booleans, lists, matrices and ASE cells for paths and input files).
- Exceptions: `GWPMError` and its subclasses (`PathResolutionError`, `ReferenceResolutionError`, `ReplacerConfigurationError`, `DependencyLoopError`, `SerializationError`), `PlaceHolderSeriesError`, `BaseSeriesReaderError`.
