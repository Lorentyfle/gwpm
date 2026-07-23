from gwpm import ASEReader

reader = ASEReader(index=":")
atoms = reader.read("trajectory.xyz")
print(len(atoms))
