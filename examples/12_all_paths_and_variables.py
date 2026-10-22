from gwpm import GeneralWorkPathManager, variable_to_string

xs = [100, 500, 600, 41]
s = ["bbb", "vMc"]

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        [variable_to_string(x, leading_zero=4) for x in xs],
        s,
    ],
    variable_names=[
        "structure",
        "temperature",
    ],
    ## Missing types are str, so "temperature" stays a str.
    variable_type=[int],
    path="./t?/s!/",
    placeholders=["?", "!"],
)

for variables, path in gwpm.all_paths_and_variables():
    print(variables, path)
# {'structure': 100, 'temperature': 'bbb'} t0100/sbbb
# ...

print(gwpm.parse("./t0041/svMc/"))
# {'structure': 41, 'temperature': 'vMc'}
