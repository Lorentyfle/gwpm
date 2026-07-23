from gwpm import GeneralWorkPathManager

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O", "Li2S"],
        ["300", "600"],
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    placeholders=["?", "!"],
    path="./?/!K/",
)

for item in gwpm.iter_paths():
    print(item)
