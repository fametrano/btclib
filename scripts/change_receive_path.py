# -*- coding: utf-8 -*-
"""
Created on Mon Nov 20 12:26:47 2017

@author: dfornaro
"""

from bip39 import from_mnemonic_to_seed
from bip32_functions import bip32_master_key, bip32_xprvtoxpub, bip32_parse_xkey, bip32_ckd
from base58 import b58encode_check
import hashlib

def h160(inp):
  h1 = hashlib.sha256(inp).digest()
  return hashlib.new('ripemd160', h1).digest()

def public_key_to_bc_address(inp, version=b'\x00'):
  vh160 = version + h160(inp)
  return b58encode_check(vh160)

def path(xprv, index_child, version=b'\x00'):
  xprv = bip32_ckd(xprv, index_child[0])
  if index_child[1:] == []:
    xpub = bip32_xprvtoxpub(xprv)
    info_xpub = bip32_parse_xkey(xpub)
    return public_key_to_bc_address(info_xpub['key'], version)
  else:
    return path(xprv, index_child[1:], version)
  

### Electrum path derivation (bip39)

mnemonic = 'army van defense carry jealous true garbage claim echo media make crunch'
passphrase = ''
receive = 'VTpEhLjvGYE16pLcNrMY53gQB9bbhn581W'
change = 'VRtaZvAe4s29aB3vuXyq7GYEpahsQet2B1'

version = 0x46.to_bytes(1, 'big')

seed = from_mnemonic_to_seed(mnemonic, passphrase)
seed = int(seed, 16)
seed_bytes = 64
xprv = bip32_master_key(seed, seed_bytes)

index_child = [0x80000000, 0, 0]
assert path(xprv, index_child, version) == receive

index_child = [0x80000000, 1, 0]
assert path(xprv, index_child, version) == change

### Bitcoin-core path derivation

xprv = 'xprv9s21ZrQH143K2oxHiQ5f7D7WYgXD9h6HAXDBuMoozDGGiYHWsq7TLBj2yvGuHTLSPCaFmUyN1v3fJRiY2A4YuNSrqQMPVLZKt76goL6LP7L'
receive = 'VUqyLGVdUADWEqDqL2DeUBAcbPQwZfWDDY' # "hdkeypath": "m/0'/0'/5'"
change = 'VMg6DpX7SQUsoECdpXJ8Bv6R7p11PfwHwy' # "hdkeypath": "m/0'/1'/1'"

index_child = [0x80000000, 0x80000000, 0x80000005]
assert path(xprv, index_child, version) == receive

index_child = [0x80000000, 0x80000001, 0x80000001]
assert path(xprv, index_child, version) == change






















