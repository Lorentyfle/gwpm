from setuptools import setup, find_packages
from pathlib import Path

# See https://packaging.python.org/guides/single-sourcing-package-version/
version_dict = {}
with open(Path(__file__).parents[0] / "src/gwpm/_version.py") as fp:
    exec(fp.read(), version_dict)
version = version_dict["__version__"]
del version_dict

setup(
    name="gwpm",
    version=version,
    author="Timothée Jamin",
    author_email="timotheejamin17@gmail.com",
    description="Build families of related file paths from reusable templates.",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/Lorentyfle/gwpm",
    project_urls={
        "Bug Tracker": "https://github.com/Lorentyfle/gwpm/issues",
    },
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_data={"gwpm": ["py.typed"]},
    install_requires=[
        "numpy",
        "pandas",
    ],
    extras_require={
        # Only needed if StructureIO or specific series_reader are used.
        "structures": ["ase", "pymatgen"],
        "test": ["pytest", "ase", "pymatgen"],
        "dev": ["pytest", "black", "ruff", "ase", "pymatgen"],
    },
    zip_safe=False,
    include_package_data=True,
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords=[
        "path",
        "path-management",
        "templating",
        "workflow",
        "simulation",
        "materials-science",
        "lammps",
        "ase",
        "pymatgen",
    ],
    python_requires=">=3.10",
)
