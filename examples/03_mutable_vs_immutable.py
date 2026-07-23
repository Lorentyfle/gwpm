from gwpm import GeneralWorkPathManager

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O"],
        ["300", "600"],
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    placeholders=["?", "!"],
    path="./?/!K/",
)

path = gwpm.resolve_path(
    {
        "structure": 0,
        "temperature": 1,
    },
    immutable=True,
)

print(path)

gwpm.resolve_path(
    {
        "structure": 0,
        "temperature": 1,
    }
)

print(gwpm.current_path)
print(gwpm.current_path_file)