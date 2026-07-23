from gwpm import GeneralWorkPathManager

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O"],
        ["900"],
        ["?_!K.xyz"],
    ],
    placeholders=["?", "!", "$"],
    path="./",
    file="$",
)

print(gwpm.resolve_path([0, 0, 0],recursive=True,immutable=True))