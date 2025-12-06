d = {"x":5,"y":15}
s=0
for v in d.values():
    s += v if v > 10 else 2
print(s)