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
    ReferenceResolutionError,
    ReplacerConfigurationError,
    DependencyLoopError,
    PathResolutionError,
)

# Series API
from .series_reader import (
    PlaceholderSeries,
    BaseSeriesReader,
    CSVReader,
    ASEReader,
    PymatgenReader,
    LammpsDumpReader,
    LammpsLogReader,
    FunctionReader,
    ThermoLogReader,
    PlaceHolderSeriesError,
    BaseSeriesReaderError,
)

from .utils import check_folder, variable_to_string


from .exception import (
    GWPMError,
    #    PathResolutionError,
    #    ReferenceResolutionError,
    #    ReplacerConfigurationError,
    #    DependencyLoopError,
    SerializationError,
    #    PlaceHolderSeriesError,
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
    "PymatgenReader",
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
    ## Utils functions
    "check_folder",
    "variable_to_string",
]
