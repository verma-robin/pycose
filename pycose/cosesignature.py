from typing import Optional, Union

from pycose import crypto
from pycose.attributes import CoseAlgorithm
from pycose.basicstructure import BasicCoseStructure
from pycose.cosekey import EC2, OKP


class CoseSignature(BasicCoseStructure):
    context = "Signature"

    @classmethod
    def from_signature_obj(cls, cose_signature_obj: list):
        msg = super().from_cose_obj(cose_signature_obj)
        msg.signature = cose_signature_obj.pop()
        return msg

    def __init__(self,
                 phdr: Optional[dict],
                 uhdr: Optional[dict],
                 signature: Optional[bytes] = b'',
                 external_aad: Optional[bytes] = b'',
                 key: Optional[Union[EC2, OKP]] = None):
        super().__init__(phdr=phdr, uhdr=uhdr)
        self.external_aad = external_aad
        self.key = key
        self.signature = signature

    @classmethod
    def compute_signature(cls,
                          to_sign: bytes,
                          alg: Optional[CoseAlgorithm] = None,
                          key: Optional[Union[EC2, OKP]] = None):

        return crypto.ec_sign_wrapper(key, to_sign, alg)

    def encode(self, signature: Optional[bytes]) -> list:

        if signature:
            message = [self.encode_phdr(), self.encode_uhdr(), signature]
        else:
            message = [self.encode_phdr(), self.encode_uhdr()]

        return message

    def __repr__(self) -> str:
        pass


class CounterSignature(CoseSignature):
    context = "CounterSignature"