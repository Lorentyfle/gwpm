from gwpm import CSVReader

reader = CSVReader()
df = reader.read("data.csv")
print(df.head())
