# gwpm — GeneralWorkPathManager

[![Python package](https://github.com/Lorentyfle/gwpm/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/Lorentyfle/gwpm/actions/workflows/python-package.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://github.com/Lorentyfle/gwpm/blob/main/setup.py)
[![License: MIT](https://img.shields.io/github/license/Lorentyfle/gwpm)](https://github.com/Lorentyfle/gwpm/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

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
        atoms = gwpm.read_placeholder_series(ASEReader(index=":"))
        # Return the atoms file of all the 000X.xyz files in the current folder.
```

### Simple example usage of the recursivity

```python
from gwpm import GeneralWorkPathManager

struct       = ["Li2O", "Li2S"]
temperatures = ["simulations/?/300K/", "simulations/?/600K/", "simulations/?/900K/"]

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        struct,
        temperatures,
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    path="./",
    placeholders=["?", "!"],
)

gwpm.resolve_path({"structure": 0, "temperature": 1})
# './simulations/Li2O/600K/'
for struct_idx in range(len(struct)):
    for temperature_idx in range(len(temperatures)):
        gwpm.resolve_path({"structure": struct_idx, "temperature": temperature_idx})
        print(gwpm.current_path)
```

### Simple example usage of `all_paths_and_variables` (one single loop)

Instead of nesting one `for` loop per variable and calling `resolve_path` with indices, `all_paths_and_variables` returns every path together with the variables used to build it. One loop is then enough, even with a `ReferenceVariable`.

The optional `variable_type` gives the type of each variable (in the order of `list_of_variables`). The missing ones are kept as `str`, so here only `temperature` needs a type.

```python
from gwpm import GeneralWorkPathManager, ReferenceVariable

struct       = ["Li2O", "Li2S"]
temperatures = [["300", "600"], ["900"]]

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        struct,
        ReferenceVariable(temperatures, 0),
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    variable_type=[str, int],
    path="./simulations/?/!K/",
    file="struct.xyz",
    placeholders=["?", "!"],
)

for variables, path in gwpm.all_paths_and_variables():
    print(variables, path)
# {'structure': 'Li2O', 'temperature': 300} simulations/Li2O/300K/struct.xyz
# {'structure': 'Li2O', 'temperature': 600} simulations/Li2O/600K/struct.xyz
# {'structure': 'Li2S', 'temperature': 900} simulations/Li2S/900K/struct.xyz
```

You can also `parse` a given path to recover the variables used inside:

```python
gwpm.parse("./simulations/Li2S/900K/struct.xyz")
# {'structure': 'Li2S', 'temperature': 900}
```

## Real life example: an MD study with shephex

This example puts the pieces above together (`ReferenceVariable`, `variable_type`, `all_paths_and_variables`, `PlaceholderSeries` and `ASEReader`) in a complete workflow.

gwpm and [shephex](https://pypi.org/project/shephex/) fit well together: shephex runs each function in its own experiment folder, while gwpm describes the whole layout in a single template, from the simulation folders to the shephex experiment folder and the file series written inside it.

Here, an MD of bulk Cu and Al is run at several temperatures (depending on the metal), saved as a series of restartable trajectory segments `md_0000.traj`, `md_0001.traj`, ...:

- the template `./runs/?/!K/md-exp/md_<ID>.traj` is the only place where the layout is written. shephex's `directory` and `identifier` are taken from it, and `run_md` receives the series pattern `gwpm.file`.
- since `variable_names` are the arguments of `run_md`, the typed variables are given directly with `**variables`.
- if the run is relaunched (e.g. with more segments, or after a crash), `run_md` finds the last segment with `PlaceholderSeries` and restarts from it.
- the analysis reads every series back with `gwpm.read_placeholder_series(ASEReader(...), path=path)`, from the same template.

```python
from ase.build import bulk
from ase.calculators.emt import EMT
from ase.io import read
from ase.io.trajectory import Trajectory
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase import units
import numpy as np
import shephex

from gwpm import (
    GeneralWorkPathManager,
    ReferenceVariable,
    PlaceholderSeries,
    ASEReader,
    variable_to_string,
)


@shephex.hexperiment()
def run_md(element: str, temperature: int, traj: str, n_segments: int = 4, n_steps: int = 200):
    """
    Langevin MD of a bulk metal, saved as a series of trajectory segments
    following the pattern ``traj`` (e.g. md_<ID>.traj -> md_0000.traj, md_0001.traj, ...).

    Run by shephex inside its own folder. If segments already exist, the MD
    restarts from the last frame of the last segment.
    """
    series = PlaceholderSeries(traj)
    if series.last is None:
        atoms = bulk(element, cubic=True).repeat(3)
        MaxwellBoltzmannDistribution(atoms, temperature_K=temperature)
    else:
        atoms = read(series.last, index=-1)
    atoms.calc = EMT()
    for segment in range(len(series), n_segments):
        ## Each segment starts with its initial frame, so it can be restarted from.
        dyn = Langevin(atoms, 2 * units.fs, temperature_K=temperature, friction=0.02)
        with Trajectory(traj.replace(series.placeholder, variable_to_string(segment, leading_zero=4)), "w", atoms) as writer:
            dyn.attach(writer.write, interval=10)
            dyn.run(n_steps)
    return atoms.get_temperature()


def shephex_location(path):
    """Split <directory>/<identifier>-exp/<file> into shephex's directory and identifier."""
    folder = path.parent
    return folder.parent, folder.name.removesuffix(f"-{shephex.Experiment.extension}")


if __name__ == "__main__":
    elements     = ["Cu", "Al"]
    temperatures = [["300", "600", "900"], ["300", "600"]]  # Al melts at 933 K.

    gwpm = GeneralWorkPathManager(
        list_of_variables=[
            elements,
            ReferenceVariable(temperatures, 0),
        ],
        ## Same names as the arguments of run_md.
        variable_names=[
            "element",
            "temperature",
        ],
        variable_type=[str, int],
        ## The whole layout, including the shephex experiment folder and the trajectory series.
        path="./runs/?/!K/md-exp/",
        file="md_<ID>.traj",
        placeholders=["?", "!"],
    )

    ## Setup and launch: one experiment per (element, temperature).
    experiments = []
    for variables, path in gwpm.all_paths_and_variables():
        directory, identifier = shephex_location(path)
        experiments.append(
            run_md(**variables, traj=gwpm.file, directory=directory, identifier=identifier)
        )
    shephex.LocalExecutor().execute(experiments)

    ## Analysis: read each series of segments, without the repeated first frame of each segment.
    reader = ASEReader(index="1:")
    for variables, path in gwpm.all_paths_and_variables():
        traj = gwpm.read_placeholder_series(reader, path=path)
        n_segments = len(gwpm.get_placeholder_series(path=path))
        e_pot = np.mean([a.get_potential_energy() / len(a) for a in traj[len(traj) // 2 :]])
        print(f"{variables['element']:>2} {variables['temperature']:>4} K  {n_segments} segments, {len(traj)} frames, <E_pot> = {e_pot:.4f} eV/atom")
```

```
runs/
├── Al/
│   ├── 300K/md-exp/
│   │   ├── md_0000.traj
│   │   ├── ...
│   │   ├── md_0003.traj
│   │   └── shephex/
│   └── 600K/md-exp/...
└── Cu/
    ├── 300K/md-exp/...
    ├── 600K/md-exp/...
    └── 900K/md-exp/...
```

Each segment starts with its initial frame (so it can be read or restarted on its own), hence `ASEReader(index="1:")` to skip it when merging. To run on a cluster, `shephex.LocalExecutor()` can be swapped for `shephex.SlurmExecutor(...)` without changing the loops. The full script is in `examples/13_shephex_md.py`.



## API reference

See the docstrings of `GeneralWorkPathManager`,`ReferenceVariable`, `PlaceholderSeries`, and the reader classes for full API documentation.

## Examples

Runnable examples for both usage patterns live in `examples/`.
