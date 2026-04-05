from pathlib import Path
from rdflib import Graph
import sys

p = Path(__file__).resolve().parent
fmt = (sys.argv[1] if len(sys.argv) > 1 else "turtle").lower()

ext = {"turtle": "ttl", "ttl": "ttl", "json-ld": "jsonld", "jsonld": "jsonld"}
ser = {"turtle": "turtle", "ttl": "turtle", "json-ld": "json-ld", "jsonld": "json-ld"}

if fmt not in ser:
    raise SystemExit("usage: python merge.py [turtle|json-ld]")

dest = p / f"all.{ext[fmt]}"
g = Graph()

for f in p.glob("*.ttl"):
    if f == dest:
        continue
    print(f)
    g.parse(f)

g.serialize(dest, format=ser[fmt], indent=2)
