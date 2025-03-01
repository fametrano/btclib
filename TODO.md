# TODO

- enable flake8 max-complexity
- improve sphinx documentation
- network as global variable
- synch (ec, hf) according to network
- add AuthProxy for full node interaction (blockexplorer fall-back)
- descriptors
- miniscript (?)
- block creation (toy mining)
- hash rate extimation
- difficulty adjustment
- add wallet infrastructure
- add sign(address, msg) using wallet infrastrucure
- isinstance(entr, bytearray) or isinstance(entr, bytes)
- optimizations:
    - <https://en.wikipedia.org/wiki/Elliptic_curve_point_multiplication>
    - <https://cryptojedi.org/peter/data/eccss-20130911b.pdf>
    - <https://arxiv.org/abs/1801.08589>
    - <https://ecc2017.cs.ru.nl/slides/ecc2017school-castryck.pdf>
    - <https://hal.archives-ouvertes.fr/hal-00932199/document>
    - <https://iacr.org/workshops/ches/ches2006/presentations/Douglas%20Stebila.pdf>
    - <https://eprint.iacr.org/2005/419.pdf>
    - <https://www.esat.kuleuven.be/cosic/publications/article-2293.pdf>
- better mimic of electrum entropy search, they probably have the words inverted
- BIP44 in address_from...
- primitives for interactive threshold and musig
- borromean references
- generalize ec, hf in borromean
- Edwards curve (Curve25519)
- BLS
- remove sign_to_contract, adding commit to dsa and ssa
- compare with test_framework

- report test vectors from P. Todd's library
- report trailing/leading blank trimming in Electrum message signing
- report BIP39 whitespaces
- SSA: ask about checking e=0
- SSA: ask about why e=e(k), making impossible to select e, k indipendently
- SSA: ask about benefit of removing 02/03 from pub_key
- SSA: suggest better k
