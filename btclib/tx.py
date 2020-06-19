#!/usr/bin/env python3

# Copyright (C) 2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"""Bitcoin Transaction.

https://en.bitcoin.it/wiki/Transaction
https://learnmeabitcoin.com/guide/coinbase-transaction
https://bitcoin.stackexchange.com/questions/20721/what-is-the-format-of-the-coinbase-transaction
"""

from typing import List, TypeVar, Type
from dataclasses import dataclass

from . import varint
from .alias import Octets
from .tx_in import TxIn, witness_serialize, witness_deserialize
from .tx_out import TxOut
from .utils import bytes_from_octets, hash256

_Tx = TypeVar("_Tx", bound="Tx")


@dataclass
class Tx:
    nVersion: int
    nLockTime: int
    vin: List[TxIn]
    vout: List[TxOut]

    @classmethod
    def deserialize(cls: Type[_Tx], data: Octets) -> _Tx:

        data = bytes_from_octets(data)

        nVersion = int.from_bytes(data[:4], "little")
        data = data[4:]

        witness_flag = False
        if data[:2] == b"\x00\x01":
            witness_flag = True
            data = data[2:]

        input_count = varint.decode(data)
        data = data[len(varint.encode(input_count)) :]
        vin: List[TxIn] = []
        for _ in range(input_count):
            tx_input = TxIn.deserialize(data)
            vin.append(tx_input)
            data = data[len(tx_input.serialize()) :]

        output_count = varint.decode(data)
        data = data[len(varint.encode(output_count)) :]
        vout: List[TxOut] = []
        for _ in range(output_count):
            tx_output = TxOut.deserialize(data)
            vout.append(tx_output)
            data = data[len(tx_output.serialize()) :]

        if witness_flag:
            for tx_input in vin:
                witness = witness_deserialize(data)
                data = data[len(witness_serialize(witness)) :]
                tx_input.txinwitness = witness

        nLockTime = int.from_bytes(data[:4], "little")

        tx = cls(nVersion=nVersion, nLockTime=nLockTime, vin=vin, vout=vout)

        tx.assert_valid()
        return tx

    def serialize(self, include_witness: bool = True) -> bytes:
        out = self.nVersion.to_bytes(4, "little")

        witness_flag = False
        out += varint.encode(len(self.vin))
        for tx_input in self.vin:
            out += tx_input.serialize()
            if tx_input.txinwitness != []:
                witness_flag = True

        out += varint.encode(len(self.vout))
        for tx_output in self.vout:
            out += tx_output.serialize()

        if witness_flag and include_witness:
            for tx_input in self.vin:
                out += witness_serialize(tx_input.txinwitness)

        out += self.nLockTime.to_bytes(4, "little")

        if witness_flag and include_witness:
            out = out[:4] + b"\x00\x01" + out[4:]

        return out

    @property
    def txid(self) -> str:
        return hash256(self.serialize(False))[::-1].hex()

    @property
    def hash_value(self) -> str:
        return hash256(self.serialize())[::-1].hex()

    def assert_valid(self) -> None:
        pass
