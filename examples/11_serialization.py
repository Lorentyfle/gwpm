from gwpm import GeneralWorkPathManager

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O"],
        ["600"],
    ],
    placeholders=["?", "!"],
)

gwpm.to_json("gwpm.json")
loaded = GeneralWorkPathManager.from_json("gwpm.json")
print(loaded)
