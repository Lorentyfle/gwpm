from gwpm import GeneralWorkPathManager

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O", "Li2S"],
        ["300", "600", "900"],
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    placeholders=["?", "!"],
    path="./simulations/?/!K/",
)

path = gwpm.resolve(
    structure="Li2O",
    temperature="600",
)

print(path)