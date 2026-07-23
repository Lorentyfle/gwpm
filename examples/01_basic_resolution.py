from gwpm import GeneralWorkPathManager

struct      = ["Li2O", "Li2S"]
temperature = ["300", "600", "900"]
gwpm = GeneralWorkPathManager(
    list_of_variables=[
        struct,
        temperature,
    ],
    placeholders=["?", "!"],
    path="./simulations/?/!K/",
)

print(
    gwpm.resolve_path(
        [0, 1],
        immutable=True,
    )
)
for i in range(len(struct)):
    for j in range(len(temperature)):
        print(gwpm.resolve_path([i,j]))