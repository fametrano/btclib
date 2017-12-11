# -*- coding: utf-8 -*-
"""
Created on Mon Nov 20 12:26:47 2017

@author: dfornaro
"""

from bip39 import from_mnemonic_to_seed
from electrum_seed import from_mnemonic_to_seed_eletrcum
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
    if xprv[:4] == 'xprv':
      xpub = bip32_xprvtoxpub(xprv)
    elif xprv[:4] == 'xpub':
      xpub = xprv
    else:
      assert False
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

### Bitcoin-core path derivation (VE)

xprv = 'xprv9s21ZrQH143K2oxHiQ5f7D7WYgXD9h6HAXDBuMoozDGGiYHWsq7TLBj2yvGuHTLSPCaFmUyN1v3fJRiY2A4YuNSrqQMPVLZKt76goL6LP7L'
receive = 'VUqyLGVdUADWEqDqL2DeUBAcbPQwZfWDDY' # "hdkeypath": "m/0'/0'/5'"
change = 'VMg6DpX7SQUsoECdpXJ8Bv6R7p11PfwHwy' # "hdkeypath": "m/0'/1'/1'"

index_child = [0x80000000, 0x80000000, 0x80000005]
assert path(xprv, index_child, version) == receive

index_child = [0x80000000, 0x80000001, 0x80000001]
assert path(xprv, index_child, version) == change


### Electrum standard path derivation

mnemonic = 'clay abstract easily position index taxi arrange ecology hobby digital turtle feel'
xpub = 'xpub661MyMwAqRbcFMYjmw8C6dJV97a4oLss6hb3v9wTQn2X48msQB61RCaLGtNhzgPCWPaJu7SvuB9EBSFCL43kTaFJC3owdaMka85uS154cEh'
passphrase = ''

seed = from_mnemonic_to_seed_eletrcum(mnemonic, passphrase)
seed = int(seed, 16)
seed_bytes = 64
xprv = bip32_master_key(seed, seed_bytes)

assert xpub == bip32_xprvtoxpub(xprv)

receive0 = '1FcfDbWwGs1PmyhMVpCAhoTfMnmSuptH6g'
index_child = [0, 0]
assert path(xprv, index_child) == receive0

receive1 = '1K5GjYkZnPFvMDTGaQHTrVnd8wjmrtfR5x'
index_child = [0, 1]
assert path(xprv, index_child) == receive1

receive2 = '1PQYX2uN7NYFd7Hq22ECMzfDcKhtrHmkfi'
index_child = [0, 2]
assert path(xprv, index_child) == receive2

change0 = '1BvSYpojWoWUeaMLnzbkK55v42DbizCoyq'
index_child = [1, 0]
assert path(xprv, index_child) == change0

change1 = '1NXB59hF4QzYpFrB7o6usLBjbk2D3ZqxAL'
index_child = [1, 1]
assert path(xprv, index_child) == change1

change2 = '16NLYkKtvYhW1Jp86tbocku3gxWcvitY1w'
index_child = [1, 2]
assert path(xprv, index_child) == change2



### Bitcoin-core path derivation

xprv = 'xprv9s21ZrQH143K2ZP8tyNiUtgoezZosUkw9hhir2JFzDhcUWKz8qFYk3cxdgSFoCMzt8E2Ubi1nXw71TLhwgCfzqFHfM5Snv4zboSebePRmLS'
add1 = '1DyfBWxhVLmrJ7keyiHeMbt7N3UdeGU4G5' # hdkeypath=m/0'/0'/0'
add2 = '11x2mn59Qy43DjisZWQGRResjyQmgthki' # hdkeypath=m/0'/0'/267'

index_child = [0x80000000, 0x80000000, 0x80000000+463]
print( path(xprv, index_child) == add1)

index_child = [0x80000000, 0x80000000, 0x80000000 + 267]
print(path(xprv, index_child) == add2)
















