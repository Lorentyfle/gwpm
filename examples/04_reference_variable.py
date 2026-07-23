from gwpm import (
    GeneralWorkPathManager,
    ReferenceVariable,
)

temperatures = ReferenceVariable(
    [
        ["900", "950", "1000"],
        ["700", "750", "800"],
    ],
    reference_position=0,
)

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O", "Li2S"],
        temperatures,
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    placeholders=["?", "!"],
    path="./?/!K/",
)

print(gwpm.resolve_path({"structure": 1, "temperature": 0}, immutable=True))
