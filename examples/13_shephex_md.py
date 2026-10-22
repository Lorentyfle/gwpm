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
def run_md(
    element: str, temperature: int, traj: str, n_segments: int = 4, n_steps: int = 200
):
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
        with Trajectory(
            traj.replace(
                series.placeholder, variable_to_string(segment, leading_zero=4)
            ),
            "w",
            atoms,
        ) as writer:
            dyn.attach(writer.write, interval=10)
            dyn.run(n_steps)
    return atoms.get_temperature()


def shephex_location(path):
    """Split <directory>/<identifier>-exp/<file> into shephex's directory and identifier."""
    folder = path.parent
    return folder.parent, folder.name.removesuffix(f"-{shephex.Experiment.extension}")


if __name__ == "__main__":
    elements = ["Cu", "Al"]
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
            run_md(
                **variables, traj=gwpm.file, directory=directory, identifier=identifier
            )
        )
    shephex.LocalExecutor().execute(experiments)

    ## Analysis: read each series of segments, without the repeated first frame of each segment.
    reader = ASEReader(index="1:")
    for variables, path in gwpm.all_paths_and_variables():
        traj = gwpm.read_placeholder_series(reader, path=path)
        n_segments = len(gwpm.get_placeholder_series(path=path))
        e_pot = np.mean(
            [a.get_potential_energy() / len(a) for a in traj[len(traj) // 2 :]]
        )
        print(
            f"{variables['element']:>2} {variables['temperature']:>4} K  {n_segments} segments, {len(traj)} frames, <E_pot> = {e_pot:.4f} eV/atom"
        )
