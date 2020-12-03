#!/usr/bin/env python3

# Copyright (C) 2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"""Partially Signed Bitcoin Transaction Output.

https://github.com/bitcoin/bips/blob/master/bip-0174.mediawiki
"""

from dataclasses import InitVar, dataclass, field
from typing import Dict, List, Tuple, Type, TypeVar

from dataclasses_json import DataClassJsonMixin, config

from . import varbytes
from .bip32 import (
    bytes_from_bip32_path,
    indexes_from_bip32_path,
    str_from_bip32_path,
)
from .exceptions import BTClibTypeError, BTClibValueError
from .utils import bytes_from_octets


def _encode_dict_bytes_bytes(d: Dict[bytes, bytes]) -> Dict[str, str]:
    "Return the json representation of the dataclass element."
    return {k.hex(): v.hex() for k, v in d.items()}


def _decode_dict_bytes_bytes(d: Dict[str, str]) -> Dict[bytes, bytes]:
    "Return the dataclass element from its json representation."
    return {bytes.fromhex(k): bytes.fromhex(v) for k, v in d.items()}


def _serialize_dict_bytes_bytes(type_: bytes, d: Dict[bytes, bytes]) -> bytes:
    "Return the binary representation of the dataclass element."

    return b"".join(
        [
            varbytes.serialize(type_ + k) + varbytes.serialize(v)
            for k, v in sorted(d.items())
        ]
    )


def _serialize_bytes(type_: bytes, value: bytes) -> bytes:
    "Return the binary representation of the dataclass element."
    return varbytes.serialize(type_) + varbytes.serialize(value)


def _deserialize_bytes(k: bytes, v: bytes, type_: str) -> bytes:
    "Return the dataclass element from its binary representation."

    if len(k) != 1:
        err_msg = f"invalid {type_} key length: {len(k)}"
        raise BTClibValueError(err_msg)
    return v


def _assert_valid_redeem_script(redeem_script: bytes) -> None:
    "Raise an exception if the dataclass element is not valid."
    if not isinstance(redeem_script, bytes):
        raise BTClibTypeError("invalid redeem script")


def _assert_valid_witness_script(witness_script: bytes) -> None:
    "Raise an exception if the dataclass element is not valid."
    if not isinstance(witness_script, bytes):
        raise BTClibTypeError("invalid witness script")


def _encode_hd_keypaths(d: Dict[bytes, bytes]) -> List[Dict[str, str]]:
    "Return the json representation of the dataclass element."

    result: List[Dict[str, str]] = []
    for k, v in d.items():
        d_str_str: Dict[str, str] = {
            "pubkey": k.hex(),
            "master_fingerprint": v[:4].hex(),
            "path": str_from_bip32_path(v[4:], "little"),
        }
        result.append(d_str_str)
    return result


def _decode_hd_keypath(new_element: Dict[str, str]) -> Tuple[bytes, bytes]:
    v = bytes_from_octets(new_element["master_fingerprint"], 4)
    v += bytes_from_bip32_path(new_element["path"], "little")
    # TODO: check the SEC / XPUB key
    k = bytes_from_octets(new_element["pubkey"])
    return k, v


def _decode_hd_keypaths(list_of_dict: List[Dict[str, str]]) -> Dict[bytes, bytes]:
    "Return the dataclass element from its json representation."

    return dict([_decode_hd_keypath(item) for item in list_of_dict])


def _deserialize_hd_keypaths(k: bytes, v: bytes, type_: str) -> Dict[bytes, bytes]:
    "Return the dataclass element from its binary representation."

    allowed_lengths = (78,) if type_ == "Psbt BIP32 xkey" else (33, 65)
    if len(k) - 1 not in allowed_lengths:
        err_msg = f"invalid {type_} length"
        err_msg += f": {len(k)-1} instead of {allowed_lengths}"
        raise BTClibValueError(err_msg)
    return {k[1:]: v}


def _assert_valid_hd_keypaths(hd_keypaths: Dict[bytes, bytes]) -> None:
    "Raise an exception if the dataclass element is not valid."

    for _, v in hd_keypaths.items():
        # FIXME
        # point_from_pubkey(k)
        indexes_from_bip32_path(v, "little")


def _assert_valid_unknown(data: Dict[bytes, bytes]) -> None:
    "Raise an exception if the dataclass element is not valid."

    for key, value in data.items():
        if not isinstance(key, bytes):
            raise BTClibTypeError("invalid key in unknown")
        if not isinstance(value, bytes):
            raise BTClibTypeError("invalid value in unknown")


PSBT_OUT_REDEEM_SCRIPT = b"\x00"
PSBT_OUT_WITNESS_SCRIPT = b"\x01"
PSBT_OUT_BIP32_DERIVATION = b"\x02"
# 0xfc is reserved for proprietary
# explicit code support for proprietary (and por) is unnecessary
# see https://github.com/bitcoin/bips/pull/1038
# PSBT_OUT_PROPRIETARY = b"\xfc"


_PsbtOut = TypeVar("_PsbtOut", bound="PsbtOut")


@dataclass
class PsbtOut(DataClassJsonMixin):
    redeem_script: bytes = field(
        default=b"", metadata=config(encoder=lambda v: v.hex(), decoder=bytes.fromhex)
    )
    witness_script: bytes = field(
        default=b"", metadata=config(encoder=lambda v: v.hex(), decoder=bytes.fromhex)
    )
    hd_keypaths: Dict[bytes, bytes] = field(
        default_factory=dict,
        metadata=config(
            field_name="bip32_derivs",
            encoder=_encode_hd_keypaths,
            decoder=_decode_hd_keypaths,
        ),
    )
    unknown: Dict[bytes, bytes] = field(
        default_factory=dict,
        metadata=config(
            encoder=_encode_dict_bytes_bytes, decoder=_decode_dict_bytes_bytes
        ),
    )
    check_validity: InitVar[bool] = True

    def __post_init__(self, check_validity: bool) -> None:
        if check_validity:
            self.assert_valid()

    def assert_valid(self) -> None:
        "Assert logical self-consistency."
        _assert_valid_redeem_script(self.redeem_script)
        _assert_valid_witness_script(self.witness_script)
        _assert_valid_hd_keypaths(self.hd_keypaths)
        _assert_valid_unknown(self.unknown)

    def serialize(self, assert_valid: bool = True) -> bytes:

        if assert_valid:
            self.assert_valid()

        out = b""

        if self.redeem_script:
            out += _serialize_bytes(PSBT_OUT_REDEEM_SCRIPT, self.redeem_script)
        if self.witness_script:
            out += _serialize_bytes(PSBT_OUT_WITNESS_SCRIPT, self.witness_script)
        if self.hd_keypaths:
            out += _serialize_dict_bytes_bytes(
                PSBT_OUT_BIP32_DERIVATION, self.hd_keypaths
            )
        if self.unknown:
            out += _serialize_dict_bytes_bytes(b"", self.unknown)

        return out

    @classmethod
    def deserialize(
        cls: Type[_PsbtOut], output_map: Dict[bytes, bytes], assert_valid: bool = True
    ) -> _PsbtOut:
        "Return a PsbtOut by parsing binary data."

        # FIX deserialize must use BinaryData
        out = cls(check_validity=False)
        for k, v in output_map.items():
            if k[0:1] == PSBT_OUT_REDEEM_SCRIPT:
                out.redeem_script = _deserialize_bytes(k, v, "redeem script")
            elif k[0:1] == PSBT_OUT_WITNESS_SCRIPT:
                out.witness_script = _deserialize_bytes(k, v, "witness script")
            elif k[0:1] == PSBT_OUT_BIP32_DERIVATION:
                out.hd_keypaths.update(
                    _deserialize_hd_keypaths(k, v, "PsbtOut BIP32 pubkey")
                )
            else:  # unknown
                out.unknown[k] = v

        if assert_valid:
            out.assert_valid()
        return out
