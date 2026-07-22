"""Ensemble of exceptions used by the gwpm library"""

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
class PlaceHolderSeriesError(Exception):
    """Raised when a Placeholder series fails."""
    pass
class BaseSeriesReaderError(Exception):
    """Raised when a BaseSeriesReader fails to read the file."""
    pass