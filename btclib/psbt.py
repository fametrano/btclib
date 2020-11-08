#!/usr/bin/env python3

# Copyright (C) 2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"""Partially Signed Bitcoin Transaction.

https://en.bitcoin.it/wiki/BIP_0174
"""

from base64 import b64decode, b64encode
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Type, TypeVar, Union, cast

from dataclasses_json import DataClassJsonMixin, config

from . import der, script, varint
from .alias import Octets, ScriptToken, String
from .bip32 import (
    BIP32KeyData,
    BIP32Path,
    bytes_from_bip32_path,
    str_from_bip32_path,
)
from .der import DERSig
from .scriptpubkey import payload_from_scriptPubKey
from .secpoint import bytes_from_point
from .to_pubkey import PubKey
from .tx import Tx
from .tx_in import witness_deserialize, witness_serialize
from .tx_out import TxOut
from .utils import (
    bytes_from_octets,
    hash160,
    sha256,
    token_or_string_to_hex_string,
    token_or_string_to_printable,
)


def _pubkey_to_hex_string(pubkey: PubKey) -> str:
    if isinstance(pubkey, tuple):
        return bytes_from_point(pubkey).hex()
    elif isinstance(pubkey, BIP32KeyData):
        return (pubkey.key).hex()
    elif isinstance(pubkey, str):
        return pubkey

    return pubkey.hex()


@dataclass
class HdKeyPaths(DataClassJsonMixin):
    hd_keypaths: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def add_hd_keypath(self, key: PubKey, fingerprint: Octets, path: BIP32Path) -> None:

        key_str = _pubkey_to_hex_string(key)
        # assert key_str == pubkeyinfo_from_key(key)[0].hex()

        fingerprint_str = bytes_from_octets(fingerprint, 4).hex()
        path_str = str_from_bip32_path(path, "little")

        self.hd_keypaths[key_str] = {
            "fingerprint": fingerprint_str,
            "derivation_path": path_str,
        }

    def get_hd_keypath(self, key: PubKey) -> Tuple[str, str]:

        # key_str = pubkeyinfo_from_key(key)[0].hex()
        key_str = _pubkey_to_hex_string(key)

        entry = self.hd_keypaths[key_str]
        return entry["fingerprint"], entry["derivation_path"]


@dataclass
class PartialSigs(DataClassJsonMixin):
    sigs: Dict[str, str] = field(default_factory=dict)

    def add_sig(self, key: PubKey, sig: DERSig):

        # key_str = pubkeyinfo_from_key(key)[0].hex()
        key_str = _pubkey_to_hex_string(key)

        r, s, sighash = der.deserialize(sig)
        sig_str = der.serialize(r, s, sighash).hex()

        self.sigs[key_str] = sig_str

    def get_sig(self, key: PubKey) -> str:

        # key_str = pubkeyinfo_from_key(key)[0].hex()
        key_str = _pubkey_to_hex_string(key)

        return self.sigs[key_str]


_PsbtIn = TypeVar("_PsbtIn", bound="PsbtIn")


@dataclass
class PsbtIn(DataClassJsonMixin):
    non_witness_utxo: Optional[Tx] = None
    witness_utxo: Optional[TxOut] = None
    partial_sigs: PartialSigs = field(default_factory=PartialSigs)
    sighash: Optional[int] = 0
    redeem_script: List[ScriptToken] = field(
        default_factory=list, metadata=config(encoder=token_or_string_to_printable)
    )
    witness_script: List[ScriptToken] = field(
        default_factory=list, metadata=config(encoder=token_or_string_to_printable)
    )
    hd_keypaths: HdKeyPaths = field(default_factory=HdKeyPaths)
    final_script_sig: List[ScriptToken] = field(
        default_factory=list, metadata=config(encoder=token_or_string_to_printable)
    )
    final_script_witness: List[String] = field(
        default_factory=list, metadata=config(encoder=token_or_string_to_printable)
    )
    por_commitment: Optional[str] = None
    proprietary: Dict[int, Dict[str, str]] = field(default_factory=dict)
    unknown: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def deserialize(
        cls: Type[_PsbtIn], input_map: Dict[bytes, bytes], assert_valid: bool = True
    ) -> _PsbtIn:
        non_witness_utxo = None
        witness_utxo = None
        partial_sigs = PartialSigs()
        sighash = 0
        redeem_script = []
        witness_script = []
        hd_keypaths = HdKeyPaths()
        final_script_sig = []
        final_script_witness = []
        por_commitment = None
        proprietary: Dict[int, Dict[str, str]] = {}
        unknown: Dict[str, str] = {}
        for key, value in input_map.items():
            if key[0] == 0x00:
                assert len(key) == 1
                non_witness_utxo = Tx.deserialize(value)
            elif key[0] == 0x01:
                assert len(key) == 1
                witness_utxo = TxOut.deserialize(value)
            elif key[0] == 0x02:
                assert len(key) == 33 + 1
                partial_sigs.add_sig(key[1:], value)
            elif key[0] == 0x03:
                assert len(key) == 1
                assert len(value) == 4
                sighash = int.from_bytes(value, "little")
            elif key[0] == 0x04:
                assert len(key) == 1
                redeem_script = script.deserialize(value)
            elif key[0] == 0x05:
                assert len(key) == 1
                witness_script = script.deserialize(value)
            elif key[0] == 0x06:
                if len(key) != 33 + 1:
                    raise ValueError(f"invalid key lenght: {len(key)-1}")
                hd_keypaths.add_hd_keypath(key[1:], value[:4], value[4:])
            elif key[0] == 0x07:
                assert len(key) == 1
                final_script_sig = script.deserialize(value)
            elif key[0] == 0x08:
                assert len(key) == 1
                final_script_witness = witness_deserialize(value)
            elif key[0] == 0x09:
                assert len(key) == 1
                por_commitment = value.hex()  # TODO: bip127
            elif key[0] == 0xFC:  # proprietary use
                prefix = varint.decode(key[1:])
                if prefix not in proprietary.keys():
                    proprietary[prefix] = {}
                key = key[1 + len(varint.encode(prefix)) :]
                proprietary[prefix][key.hex()] = value.hex()
            else:  # unkown keys
                unknown[key.hex()] = value.hex()

        out = cls(
            non_witness_utxo=non_witness_utxo,
            witness_utxo=witness_utxo,
            partial_sigs=partial_sigs,
            sighash=sighash,
            redeem_script=redeem_script,
            witness_script=witness_script,
            hd_keypaths=hd_keypaths,
            final_script_sig=final_script_sig,
            final_script_witness=final_script_witness,
            por_commitment=por_commitment,
            proprietary=proprietary,
            unknown=unknown,
        )
        if assert_valid:
            out.assert_valid()
        return out

    def serialize(self, assert_valid: bool = True) -> bytes:

        if assert_valid:
            self.assert_valid()

        out = b""
        if self.non_witness_utxo:
            out += b"\x01\x00"
            utxo = self.non_witness_utxo.serialize()
            out += varint.encode(len(utxo)) + utxo
        if self.witness_utxo:
            out += b"\x01\x01"
            utxo = self.witness_utxo.serialize()
            out += varint.encode(len(utxo)) + utxo
        if self.partial_sigs:
            for key, value in self.partial_sigs.sigs.items():
                out += b"\x22\x02" + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.sighash:
            out += b"\x01\x03\x04"
            out += self.sighash.to_bytes(4, "little")
        if self.redeem_script:
            out += b"\x01\x04"
            s = script.serialize(self.redeem_script)
            out += varint.encode(len(s)) + s
        if self.witness_script:
            out += b"\x01\x05"
            s = script.serialize(self.witness_script)
            out += varint.encode(len(s)) + s
        if self.hd_keypaths:
            for xpub, hd_keypath in self.hd_keypaths.hd_keypaths.items():
                out += b"\x22\x06" + bytes.fromhex(xpub)
                keypath = bytes.fromhex(hd_keypath["fingerprint"])
                keypath += bytes_from_bip32_path(
                    hd_keypath["derivation_path"], "little"
                )
                out += varint.encode(len(keypath)) + keypath
        if self.final_script_sig:
            out += b"\x01\x07"
            s = script.serialize(self.final_script_sig)
            out += varint.encode(len(s)) + s
        if self.final_script_witness:
            out += b"\x01\x08"
            wit = witness_serialize(self.final_script_witness)
            out += varint.encode(len(wit)) + wit
        if self.por_commitment:  # TODO
            out += b"\x01\x09"
            c = bytes.fromhex(self.por_commitment)
            out += varint.encode(len(c)) + c
        if self.proprietary:
            for (owner, dictionary) in self.proprietary.items():
                for key, value in dictionary.items():
                    key_bytes = b"\xfc" + varint.encode(owner) + bytes.fromhex(key)
                    out += varint.encode(len(key_bytes)) + key_bytes
                    out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.unknown:
            for key, value in self.unknown.items():
                out += varint.encode(len(key) // 2) + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        return out

    def assert_valid(self) -> None:
        pass

    def add_unknown(self, key: String, val: Octets):

        key_str = token_or_string_to_hex_string(key)

        self.unknown[key_str] = bytes_from_octets(val).hex()

    def get_unknown(self, key: String) -> str:

        key_str = token_or_string_to_hex_string(key)

        return self.unknown[key_str]


_PsbtOut = TypeVar("_PsbtOut", bound="PsbtOut")


@dataclass
class PsbtOut(DataClassJsonMixin):
    redeem_script: List[ScriptToken] = field(
        default_factory=list, metadata=config(encoder=token_or_string_to_printable)
    )
    witness_script: List[ScriptToken] = field(
        default_factory=list, metadata=config(encoder=token_or_string_to_printable)
    )
    hd_keypaths: HdKeyPaths = field(default_factory=HdKeyPaths)
    proprietary: Dict[int, Dict[str, str]] = field(default_factory=dict)
    unknown: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def deserialize(
        cls: Type[_PsbtOut], output_map: Dict[bytes, bytes], assert_valid: bool = True
    ) -> _PsbtOut:
        redeem_script = []
        witness_script = []
        hd_keypaths = HdKeyPaths()
        proprietary: Dict[int, Dict[str, str]] = {}
        unknown: Dict[str, str] = {}
        for key, value in output_map.items():
            if key[0] == 0x00:
                assert len(key) == 1
                redeem_script = script.deserialize(value)
            elif key[0] == 0x01:
                assert len(key) == 1
                witness_script = script.deserialize(value)
            elif key[0] == 0x02:
                if len(key) != 33 + 1:
                    raise ValueError(f"invalid key lenght: {len(key)-1}")
                hd_keypaths.add_hd_keypath(key[1:], value[:4], value[4:])
            elif key[0] == 0xFC:  # proprietary use
                prefix = varint.decode(key[1:])
                if prefix not in proprietary.keys():
                    proprietary[prefix] = {}
                key = key[1 + len(varint.encode(prefix)) :]
                proprietary[prefix][key.hex()] = value.hex()
            else:  # unkown keys
                unknown[key.hex()] = value.hex()

        out = cls(
            redeem_script=redeem_script,
            witness_script=witness_script,
            hd_keypaths=hd_keypaths,
            proprietary=proprietary,
            unknown=unknown,
        )
        if assert_valid:
            out.assert_valid()
        return out

    def serialize(self, assert_valid: bool = True) -> bytes:

        if assert_valid:
            self.assert_valid()

        out = b""
        if self.redeem_script:
            out += b"\x01\x00"
            s = script.serialize(self.redeem_script)
            out += varint.encode(len(s)) + s
        if self.witness_script:
            out += b"\x01\x01"
            s = script.serialize(self.witness_script)
            out += varint.encode(len(s)) + s
        if self.hd_keypaths:
            for xpub, hd_keypath in self.hd_keypaths.hd_keypaths.items():
                out += b"\x22\x02" + bytes.fromhex(xpub)
                keypath = bytes.fromhex(hd_keypath["fingerprint"])
                keypath += bytes_from_bip32_path(
                    hd_keypath["derivation_path"], "little"
                )
                out += varint.encode(len(keypath)) + keypath
        if self.proprietary:
            for (owner, dictionary) in self.proprietary.items():
                for key, value in dictionary.items():
                    key_bytes = b"\xfc" + varint.encode(owner) + bytes.fromhex(key)
                    out += varint.encode(len(key_bytes)) + key_bytes
                    out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.unknown:
            for key, value in self.unknown.items():
                out += varint.encode(len(key) // 2) + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        return out

    def assert_valid(self) -> None:
        pass

    def add_unknown(self, key: String, val: Octets):

        key_str = token_or_string_to_hex_string(key)

        self.unknown[key_str] = bytes_from_octets(val).hex()

    def get_unknown(self, key: String) -> str:

        key_str = token_or_string_to_hex_string(key)

        return self.unknown[key_str]


_PSbt = TypeVar("_PSbt", bound="Psbt")


@dataclass
class Psbt(DataClassJsonMixin):
    tx: Tx
    inputs: List[PsbtIn]
    outputs: List[PsbtOut]
    version: Optional[int] = 0
    hd_keypaths: HdKeyPaths = field(default_factory=HdKeyPaths)
    proprietary: Dict[int, Dict[str, str]] = field(default_factory=dict)
    unknown: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def deserialize(cls: Type[_PSbt], string: str, assert_valid: bool = True) -> _PSbt:
        data = b64decode(string)

        magic_bytes = data[:5]
        assert magic_bytes == b"psbt\xff", "Malformed psbt: missing magic bytes"

        data = data[5:]

        global_map, data = deserialize_map(data)
        version = 0
        hd_keypaths = HdKeyPaths()
        proprietary: Dict[int, Dict[str, str]] = {}
        unknown: Dict[str, str] = {}
        for key, value in global_map.items():
            if key[0] == 0x00:
                assert len(key) == 1
                tx = Tx.deserialize(value)
            elif key[0] == 0x01:
                # TODO add test case
                # why extended key here?
                assert len(key) == 78 + 1, f"invalid key lenght: {len(key)-1}"
                hd_keypaths.add_hd_keypath(key[1:], value[:4], value[4:])
            elif key[0] == 0xFB:
                assert len(value) == 4
                version = int.from_bytes(value, "little")
            elif key[0] == 0xFC:
                prefix = varint.decode(key[1:])
                if prefix not in proprietary.keys():
                    proprietary[prefix] = {}
                key = key[1 + len(varint.encode(prefix)) :]
                proprietary[prefix][key.hex()] = value.hex()
            else:  # unkown keys
                unknown[key.hex()] = value.hex()

        input_len = len(tx.vin)
        output_len = len(tx.vout)

        inputs = []
        for _ in range(input_len):
            input_map, data = deserialize_map(data)
            inputs.append(PsbtIn.deserialize(input_map))

        outputs = []
        for _ in range(output_len):
            output_map, data = deserialize_map(data)
            outputs.append(PsbtOut.deserialize(output_map))

        psbt = cls(
            tx=tx,
            inputs=inputs,
            outputs=outputs,
            version=version,
            hd_keypaths=hd_keypaths,
            proprietary=proprietary,
            unknown=unknown,
        )
        if assert_valid:
            psbt.assert_valid()
        return psbt

    def serialize(self, assert_valid: bool = True) -> str:

        if assert_valid:
            self.assert_valid()

        out = bytes.fromhex("70736274ff")
        out += b"\x01\x00"
        tx = self.tx.serialize()
        out += varint.encode(len(tx)) + tx
        if self.hd_keypaths:
            for xpub, hd_keypath in self.hd_keypaths.hd_keypaths.items():
                out += b"\x4f\x01" + bytes.fromhex(xpub)
                keypath = bytes.fromhex(hd_keypath["fingerprint"])
                keypath += bytes_from_bip32_path(
                    hd_keypath["derivation_path"], "little"
                )
                out += varint.encode(len(keypath)) + keypath
        if self.version:
            out += b"\x01\xfb\x04"
            out += self.version.to_bytes(4, "little")
        if self.proprietary:
            for (owner, dictionary) in self.proprietary.items():
                for key, value in dictionary.items():
                    key_bytes = b"\xfc" + varint.encode(owner) + bytes.fromhex(key)
                    out += varint.encode(len(key_bytes)) + key_bytes
                    out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.unknown:
            for key, value in self.unknown.items():
                out += varint.encode(len(key) // 2) + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        out += b"\x00"
        for input_map in self.inputs:
            out += input_map.serialize() + b"\x00"
        for output_map in self.outputs:
            out += output_map.serialize() + b"\x00"
        return b64encode(out).decode("ascii")

    def assert_valid(self) -> None:
        for vin in self.tx.vin:
            assert vin.scriptSig == []
            assert vin.txinwitness == []
        for input_map in self.inputs:
            input_map.assert_valid()
        for output_map in self.outputs:
            output_map.assert_valid()

    def assert_signable(self) -> None:

        for i, tx_in in enumerate(self.tx.vin):

            non_witness_utxo = self.inputs[i].non_witness_utxo
            witness_utxo = self.inputs[i].witness_utxo

            if non_witness_utxo:
                txid = tx_in.prevout.hash
                assert isinstance(non_witness_utxo, Tx)
                assert non_witness_utxo.txid == txid

            if witness_utxo:
                assert isinstance(witness_utxo, TxOut)
                scriptPubKey = witness_utxo.scriptPubKey
                script_type = payload_from_scriptPubKey(scriptPubKey)[0]
                if script_type == "p2sh":
                    scriptPubKey = self.inputs[i].redeem_script
                script_type = payload_from_scriptPubKey(scriptPubKey)[0]
                assert script_type in ["p2wpkh", "p2wsh"]

            if self.inputs[i].redeem_script:
                if non_witness_utxo:
                    scriptPubKey = non_witness_utxo.vout[tx_in.prevout.n].scriptPubKey
                elif witness_utxo:
                    scriptPubKey = witness_utxo.scriptPubKey
                hash = hash160(script.serialize(self.inputs[i].redeem_script))
                assert hash == payload_from_scriptPubKey(scriptPubKey)[1]

            if self.inputs[i].witness_script:
                if non_witness_utxo:
                    scriptPubKey = non_witness_utxo.vout[tx_in.prevout.n].scriptPubKey
                elif witness_utxo:
                    scriptPubKey = witness_utxo.scriptPubKey
                if self.inputs[i].redeem_script:
                    scriptPubKey = self.inputs[i].redeem_script

                hash = sha256(script.serialize(self.inputs[i].witness_script))
                assert hash == payload_from_scriptPubKey(scriptPubKey)[1]

    def add_unknown(self, key: String, val: Octets):

        key_str = token_or_string_to_hex_string(key)

        self.unknown[key_str] = bytes_from_octets(val).hex()

    def get_unknown(self, key: String) -> str:

        key_str = token_or_string_to_hex_string(key)

        return self.unknown[key_str]


def deserialize_map(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    assert len(data) != 0, "Malformed psbt: at least a map is missing"
    partial_map: Dict[bytes, bytes] = {}
    while True:
        if data[0] == 0:
            data = data[1:]
            return partial_map, data
        key_len = varint.decode(data)
        data = data[len(varint.encode(key_len)) :]
        key = data[:key_len]
        data = data[key_len:]
        value_len = varint.decode(data)
        data = data[len(varint.encode(value_len)) :]
        value = data[:value_len]
        data = data[value_len:]
        assert key not in partial_map.keys(), "Malformed psbt: duplicate keys"
        partial_map[key] = value


def psbt_from_tx(tx: Tx) -> Psbt:
    tx = deepcopy(tx)
    for input in tx.vin:
        input.scriptSig = []
        input.txinwitness = []
    inputs = [PsbtIn() for _ in tx.vin]
    outputs = [PsbtOut() for _ in tx.vout]
    return Psbt(tx=tx, inputs=inputs, outputs=outputs, unknown={})


def _combine_field(
    psbt_map: Union[PsbtIn, PsbtOut, Psbt], out: Union[PsbtIn, PsbtOut, Psbt], key: str
) -> None:
    item = getattr(psbt_map, key)
    a = getattr(out, key)
    if isinstance(item, dict) and a and isinstance(a, dict):
        a.update(item)
    elif isinstance(item, dict) or item and not a:
        setattr(out, key, item)
    elif isinstance(item, PartialSigs) and isinstance(a, PartialSigs):
        a.sigs.update(item.sigs)
    elif isinstance(item, HdKeyPaths) and isinstance(a, HdKeyPaths):
        a.hd_keypaths.update(item.hd_keypaths)
    elif item:
        assert item == a, key


def combine_psbts(psbts: List[Psbt]) -> Psbt:
    final_psbt = psbts[0]
    txid = psbts[0].tx.txid
    for psbt in psbts[1:]:
        assert psbt.tx.txid == txid

    for psbt in psbts[1:]:

        for x in range(len(final_psbt.inputs)):
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "non_witness_utxo")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "witness_utxo")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "partial_sigs")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "sighash")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "redeem_script")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "witness_script")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "hd_keypaths")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "final_script_sig")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "final_script_witness")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "por_commitment")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "proprietary")
            _combine_field(psbt.inputs[x], final_psbt.inputs[x], "unknown")

        for _ in final_psbt.outputs:
            _combine_field(psbt.outputs[x], final_psbt.outputs[x], "redeem_script")
            _combine_field(psbt.outputs[x], final_psbt.outputs[x], "witness_script")
            _combine_field(psbt.outputs[x], final_psbt.outputs[x], "hd_keypaths")
            _combine_field(psbt.outputs[x], final_psbt.outputs[x], "proprietary")
            _combine_field(psbt.outputs[x], final_psbt.outputs[x], "unknown")

        _combine_field(psbt, final_psbt, "tx")
        _combine_field(psbt, final_psbt, "version")
        _combine_field(psbt, final_psbt, "hd_keypaths")
        _combine_field(psbt, final_psbt, "proprietary")
        _combine_field(psbt, final_psbt, "unknown")

    return final_psbt


def finalize_psbt(psbt: Psbt) -> Psbt:
    psbt = deepcopy(psbt)
    for psbt_in in psbt.inputs:
        assert psbt_in.partial_sigs, "Missing signatures"
        if psbt_in.witness_script:
            psbt_in.final_script_sig = [
                script.serialize(psbt_in.redeem_script).hex().upper()
            ]
            psbt_in.final_script_witness = list(psbt_in.partial_sigs.sigs.values())
            psbt_in.final_script_witness += [
                script.serialize(psbt_in.witness_script).hex()
            ]
            if len(psbt_in.partial_sigs.sigs) > 1:
                psbt_in.final_script_witness = [
                    cast(String, "")
                ] + psbt_in.final_script_witness
        else:
            psbt_in.final_script_sig = [
                a.upper() for a in list(psbt_in.partial_sigs.sigs.values())
            ]
            psbt_in.final_script_sig += [
                script.serialize(psbt_in.redeem_script).hex().upper()
            ]
            # https://github.com/bitcoin/bips/blob/master/bip-0147.mediawiki#motivation
            if len(psbt_in.partial_sigs.sigs) > 1:
                dummy_element: List[ScriptToken] = [0]
                psbt_in.final_script_sig = dummy_element + psbt_in.final_script_sig
        psbt_in.partial_sigs = PartialSigs()
        psbt_in.sighash = 0
        psbt_in.redeem_script = []
        psbt_in.witness_script = []
        psbt_in.hd_keypaths = HdKeyPaths()
        psbt_in.por_commitment = None
    return psbt


def extract_tx(psbt: Psbt) -> Tx:
    tx = psbt.tx
    for i, vin in enumerate(tx.vin):
        vin.scriptSig = psbt.inputs[i].final_script_sig
        if psbt.inputs[i].final_script_witness:
            vin.txinwitness = psbt.inputs[i].final_script_witness
    return tx
