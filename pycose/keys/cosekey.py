import base64
from abc import ABCMeta, abstractmethod
from enum import IntEnum, unique
from typing import List, Union, Dict, Optional, TypeVar, TYPE_CHECKING, Type, Callable

import dataclasses
from dataclasses import dataclass

from pycose.algorithms import CoseAlgorithms
from pycose.exceptions import CoseIllegalKeyOps

if TYPE_CHECKING:
    from pycose.keys.ec import EC2
    from pycose.keys.okp import OKP


@unique
class KTY(IntEnum):
    """ The different COSE key types. """

    RESERVED = 0
    OKP = 1
    EC2 = 2
    SYMMETRIC = 4


@unique
class KeyOps(IntEnum):
    """ Supported COSE key operations. """

    SIGN = 1
    VERIFY = 2
    ENCRYPT = 3
    DECRYPT = 4
    WRAP = 5
    UNWRAP = 6
    DERIVE_KEY = 7
    DERIVE_BITS = 8
    MAC_CREATE = 9
    MAC_VERIFY = 10


@unique
class EllipticCurveType(IntEnum):
    """ The (elliptic) curves supported by COSE. """

    RESERVED = 0
    P_256 = 1
    P_384 = 2
    P_521 = 3
    X25519 = 4
    X448 = 5
    ED25519 = 6
    ED448 = 7
    SECP256K1 = 8


@dataclass(init=False)
class CoseKey(metaclass=ABCMeta):
    """ Abstract base class for all key type in COSE. """

    _kty: Optional[KTY]
    _kid: Optional[Union[int, bytes]]
    _alg: Optional[CoseAlgorithms]
    _key_ops: Optional[KeyOps]
    _base_iv: Optional[bytes]

    _KTY = {}

    class Common(IntEnum):
        """ Common COSE key parameters. """
        KTY = 1
        KID = 2
        ALG = 3
        KEY_OPS = 4
        BASE_IV = 5

    def __init__(self, kty, kid, alg, key_ops, base_iv):
        self.kty = kty
        self.kid = kid
        self.alg = alg
        self.key_ops = key_ops
        self.base_iv = base_iv

    @classmethod
    def record_kty(cls, kty_id: int) -> Callable[[Type['CoseKey']], Type['CoseKey']]:
        """
        Decorator to record all the COSE key types dynamically.

        :param kty_id: Integer identifying the COSE key type (see RFC 8152)
        :raises ValueError: Checks if the decorated class is of type 'CoseKey'
        :return: Decorator function
        """

        def decorator(the_class: Type['CoseKey']) -> Type['CoseKey']:
            if not issubclass(the_class, CoseKey):
                raise ValueError("Can only decorate subclass of CoseKey")
            cls._KTY[kty_id] = the_class
            return the_class

        return decorator

    @classmethod
    def decode(cls, received: dict):
        """
        Decoding function for COSE key objects.

        :param received: Dictionary must contain the KTY element otherwise the key object cannot be decoded properly.
        :raises KeyError: Decoding function fails when KTY parameter is not found or has an invalid value.
        """
        try:
            return cls._KTY[received[cls.Common.KTY]].from_cose_key_obj(received)
        except KeyError as e:
            raise KeyError("Key type identifier is not recognized", e)

    @staticmethod
    def base64decode(to_decode: str) -> bytes:
        """
        Decodes BASE64 encoded keys to bytes.
        :param to_decode: base64 encoded key.
        :return: key as bytes.
        """
        to_decode = to_decode.replace('-', '+')
        to_decode = to_decode.replace('_', '/')

        if len(to_decode) % 4 == 0:
            return base64.b64decode(to_decode)
        if len(to_decode) % 4 == 2:
            to_decode = to_decode + "=="
            return base64.b64decode(to_decode)
        if len(to_decode) % 4 == 3:
            to_decode = to_decode + "="
            return base64.b64decode(to_decode)

    @staticmethod
    def base64encode(to_encode: bytes) -> str:
        """
        Encodes key bytes as a string.
        :param to_encode: bytes
        :return: base64 encoding.
        """
        return base64.b64encode(to_encode).decode("utf-8")

    @property
    def kty(self) -> KTY:
        return self._kty

    @kty.setter
    def kty(self, new_kty: KTY) -> None:
        _ = KTY(new_kty)  # check if the new value is a known COSE KTY, should never be None!
        self._kty = new_kty

    @property
    def alg(self) -> Optional[CoseAlgorithms]:
        return self._alg

    @alg.setter
    def alg(self, new_alg: CoseAlgorithms) -> None:
        if new_alg is not None:
            _ = CoseAlgorithms(new_alg)  # check if the new value is a known COSE Algorithm
            self._alg = CoseAlgorithms(new_alg)
        else:
            self._alg = None

    @property
    def kid(self) -> Optional[bytes]:
        return self._kid

    @kid.setter
    def kid(self, new_kid: bytes) -> None:
        if type(new_kid) is not bytes and new_kid is not None:
            raise ValueError("kid attribute must be of type 'bytes'")
        self._kid = new_kid

    @property
    def key_ops(self) -> Optional[KeyOps]:
        return self._key_ops

    @key_ops.setter
    def key_ops(self, new_key_ops: Optional[KeyOps]) -> None:
        if new_key_ops is not None:
            _ = KeyOps(new_key_ops)  # check if the new value is a known COSE key operation
        self._key_ops = new_key_ops

    @property
    def base_iv(self) -> Optional[bytes]:
        return self._base_iv

    @base_iv.setter
    def base_iv(self, new_base_iv: bytes) -> None:
        if new_base_iv is not None and not isinstance(new_base_iv, bytes):
            raise ValueError("base_iv attribute must be of type 'bytes'")
        self._base_iv = new_base_iv

    def encode(self, *argv) -> Dict[int, Union[int, bytes]]:
        key_words = ["_kty"]

        for kw in argv:
            if kw.upper() in self.Common.__members__:
                key_words.append(kw)

        return {self.Common[kw[1:].upper()]: dataclasses.asdict(self)[kw] for kw in key_words}

    def _check_key_conf(self,
                        algorithm: CoseAlgorithms,
                        key_operation: KeyOps,
                        peer_key: Optional[Union['EC2', 'OKP']] = None,
                        curve: Optional[EllipticCurveType] = None):
        """ Helper function that checks the configuration of the COSE key object. """

        if self.alg is not None and algorithm is not None and CoseAlgorithms(self.alg) != CoseAlgorithms(algorithm):
            raise ValueError("COSE key algorithm does not match with parameter 'algorithm'.")

        if algorithm is not None:
            self.alg = algorithm

        if self.alg is None:
            raise ValueError("Selected COSE algorithm cannot be 'None'")

        if peer_key is not None:
            if peer_key.alg is not None and self.alg != peer_key.alg:
                raise ValueError("Algorithms for private and public key do not match")
            else:
                peer_key.alg = self.alg

        if hasattr(self, "crv"):
            if self.crv is not None and curve is not None and self.crv != curve:
                raise ValueError("Curve in COSE key clashes with parameter 'curve'.")

            if curve is not None:
                self.crv = curve

        if peer_key is not None:
            if peer_key.crv is not None and self.crv != peer_key.crv:
                raise ValueError("Curve parameter for private and public key do not match")
            else:
                peer_key.crv = self.crv

        if self.key_ops is not None and key_operation is not None and self.key_ops != key_operation:
            raise CoseIllegalKeyOps(f"COSE key operation should be {key_operation.name}, instead {self.key_ops.name}")

        if key_operation is not None:
            self.key_ops = key_operation

        if peer_key is not None:
            if peer_key.key_ops is not None and self.key_ops != peer_key.key_ops:
                raise ValueError("Key operation for private and public key do not match")
            else:
                peer_key.key_ops = self.key_ops

    @abstractmethod
    def __repr__(self):
        raise NotImplementedError


CK = TypeVar('CK', bound=CoseKey)


class CoseKeySet:
    def __init__(self, cose_keys: List[CK] = None):
        if cose_keys is None:
            self.cose_keys = []
        else:
            self.cose_keys = cose_keys
