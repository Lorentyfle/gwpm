from gwpm import GeneralWorkPathManager

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O"],
        ["600"],
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    placeholders=["?", "!"],
    path="./simulations/?/!K/",
)

print(gwpm.parse("./simulations/Li2O/600K/"))
