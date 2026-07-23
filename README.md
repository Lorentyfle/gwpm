# gwpm — GeneralWorkPathManager

This library aims to provide a common and reusable way to manage path templates, while remaining straightforward, lightweight, and robust.

Indeed, everyone has their own solution to construct paths and folder systems. The goal is to adapt to existing workflows while keeping path generation straightforward and less error-prone.

It can handle simple problems that can be described into a for loop like `f"{base}/{struct}/{family}/{temp}K/..."`, but GWPM can also take care of very complex filesystem layouts by allowing one to attach dependencies on said entries.

For example, if your temperature ranges depend on your structure you can use a `ReferenceVariable` object to attach your temperature list to your structure, allowing you to throw away your worries on this side.


GWPM extends the simple idea of placeholder replacement by supporting variables whose values can themselves contain placeholders, allowing  recursive path and filename generation.

Paths can be generated either mutably (updating the manager's current path state) or immutably (returning a Path object without changing the manager), making GWPM suitable for both iterative workflows and one-off path generation.

GWPM also provides a lightweight reader framework for working with file series such as simulation restarts, trajectories, logs, and tabulated data through CSV, ASE, Pymatgen, LAMMPS, and custom readers.

## Installation

For a simple installation simply do:

```bash
pip install gwpm
```

However, if you wish to also install the dependencies to use gwpm for Material Science it is recommended to use:
```bash
pip install gwpm[structures]
```

## How to use it?

### Simple usage example.

```python
from gwpm import GeneralWorkPathManager

struct       = ["Li2O", "Li2S"]
temperatures = ["300", "600", "900"]

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        struct,
        temperatures,
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    path="./simulations/?/!K/",
    placeholders=["?", "!"],
)

gwpm.resolve_path({"structure": 0, "temperature": 1})
# './simulations/Li2O/600K/'
for struct_idx in range(len(struct)):
    for i, temp in enumerate(temperatures):
        gwpm.resolve_path({"structure": struct_idx, "temperature": i})
        print(gwpm.current_path)
```

### Simple example usage of `ReferenceVariable`.

```python
from gwpm import GeneralWorkPathManager, ReferenceVariable

struct       = ["Li2O", "Li2S"]
temperatures = [["300", "600", "900"],["1100","1200","900"]]

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        struct,
        ReferenceVariable(temperatures,0),
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    file="struct.xyz",
    path="./simulations/?/!K/",
    placeholders=["?", "!"],
)

gwpm.resolve_path({"structure": 0, "temperature": 1})
# './simulations/Li2O/600K/'
gwpm.resolve_path({"structure": 1, "temperature": 1})
# './simulations/Li2S/1200K/'
for struct_idx in range(len(struct)):
    for i, temp in enumerate(temperatures):
        ## gwpm can be view index locally if you wish to be less verbose.
        gwpm.resolve_path([struct_idx,i])
        read(gwpm.current_path_file)
```

### Simple example usage of `SeriesReader`

```python
from gwpm import GeneralWorkPathManager
from gwpm import ASEReader

struct       = ["Li2O", "Li2S"]
temperatures = ["300", "600", "900"]

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        struct,
        temperatures,
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    path="./simulations/?/!K/",
    file="<ID>.xyz",
    placeholders=["?", "!"],
)

gwpm.resolve_path({"structure": 0, "temperature": 1})
# './simulations/Li2O/600K/'
for struct_idx in range(len(struct)):
    for i, temp in enumerate(temperatures):
        gwpm.resolve_path({"structure": struct_idx, "temperature": i})
        atoms = gwpm.read_placeholder_series(ASEReader(index=":"),placeholder="<ID>")
        # Return the atoms file of all the 000X.xyz files in the current folder.
```


## API reference

See the docstrings of `GeneralWorkPathManager`,`ReferenceVariable`, `PlaceholderSeries`, and the reader classes for full API documentation.

## Examples

Runnable examples for both usage patterns live in `examples/`.
