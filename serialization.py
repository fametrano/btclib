
import json
from btclib.ec import EC
from btclib.ecurves import NIST_curves

ecdata: dict = {}
ecdata['ec'] = []
for ec in NIST_curves:
    ecdata['ec'].append({
        'name': "test",
        'p': (ec._p),
        'a': (ec._a),
        'b': (ec._b),
        'Gx': (ec.G[0]),
        'Gy': (ec.G[1]),
        'n': (ec.n),
        'h': (ec.h),
        't': (ec.t)
    })

filename = 'curves.json'
with open(filename, 'w') as outfile:
     json.dump(ecdata, outfile, indent = 2)
outfile.closed

with open(filename, 'r') as infile:
     ecdata = json.load(infile)
infile.closed
print(ecdata[0])
for ec in ecdata['ec']:
    str(ec['name']) = EC(ec['p'], ec['a'], ec['b'], (ec['Gx'], ec['Gy']), ec['n'], ec['h'], ec['t'])
