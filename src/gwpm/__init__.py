"""
General Work Path Manager (GWPM).

Utilities for placeholder-based path generation and
series-based file reading.
"""

from ._version import __version__

# Path manager
from .path_manager import (
    GeneralWorkPathManager,
    ReferenceVariable,
    GWPMError,
    ReferenceResolutionError,
    ReplacerConfigurationError,
    DependencyLoopError,
    PathResolutionError,
    SerializationError,
)

# Series API
from .series_reader import (
    PlaceholderSeries,
    BaseSeriesReader,
    CSVReader,
    ASEReader,
    LammpsDumpReader,
    LammpsLogReader,
    FunctionReader,
    ThermoLogReader,
    PlaceHolderSeriesError,
    BaseSeriesReaderError,
)

__all__ = [
    "__version__",

    # Main GWPM classes
    "GeneralWorkPathManager",
    "ReferenceVariable",

    # Series objects
    "PlaceholderSeries",

    # Readers
    "BaseSeriesReader",
    "CSVReader",
    "ASEReader",
    "LammpsDumpReader",
    "LammpsLogReader",
    "FunctionReader",
    "ThermoLogReader",

    # GWPM exceptions
    "GWPMError",
    "ReferenceResolutionError",
    "ReplacerConfigurationError",
    "DependencyLoopError",
    "PathResolutionError",
    "SerializationError",

    # Series exceptions
    "PlaceHolderSeriesError",
    "BaseSeriesReaderError",
]
