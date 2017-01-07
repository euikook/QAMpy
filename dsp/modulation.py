from __future__ import division
import numpy as np
from .utils import bin2gray
from bitarray import bitarray



def calculate_MQAM_symbols(M):
    """
    Generate the symbols on the constellation diagram for M-QAM
    """
    if np.log2(M)%2 > 0.5:
        return calculate_cross_QAM_symbols(M)
    else:
        return calculate_square_QAM_symbols(M)

def calculate_square_QAM_symbols(M):
    """
    Generate the symbols on the constellation diagram for square M-QAM
    """
    qam = np.mgrid[-(2 * np.sqrt(M) / 2 - 1):2 * np.sqrt(
        M) / 2 - 1:1.j * np.sqrt(M), -(2 * np.sqrt(M) / 2 - 1):2 * np.sqrt(M) /
                   2 - 1:1.j * np.sqrt(M)]
    return (qam[0] + 1.j * qam[1]).flatten()

def calculate_cross_QAM_symbols(M):
    """
    Generate the symbols on the constellation diagram for non-square (cross) M-QAM
    """
    N = (np.log2(M)-1)/2
    s = 2**(N-1)
    rect = np.mgrid[
        -(2**(N+1) - 1) : 2**(N+1) - 1: 1.j*2**(N+1),
        -(2**N - 1) : 2**N - 1: 1.j*2**N
    ]
    qam = rect[0] + 1.j*rect[1]
    idx1 = np.where((abs(qam.real) > 3*s)&(abs(qam.imag) > s))
    idx2 = np.where((abs(qam.real) > 3*s)&(abs(qam.imag) <= s))
    qam[idx1] = np.sign(qam[idx1].real)*(abs(qam[idx1].real)-2*s) + 1.j*(np.sign(qam[idx1].imag)*(4*s-abs(qam[idx1].imag)))
    qam[idx2] = np.sign(qam[idx2].real)*(4*s-abs(qam[idx2].real)) + 1.j*(np.sign(qam[idx2].imag)*(abs(qam[idx2].imag)+2*s))
    return qam.flatten()

def gray_code_for_qam(M):
    """
    Generate gray code map for M-QAM constellations
    """
    Nbits = int(np.log2(M))
    if Nbits%2 == 0:
        N = Nbits//2
        idx = np.mgrid[
            0 : 2**N : 1,
            0 : 2**N : 1
        ]
    else:
        N = (Nbits - 1)//2
        idx = np.mgrid[
            0 : 2**(N+1): 1,
            0 : 2**N: 1
        ]
    gidx = bin2gray(idx)
    return ((gidx[0] << N)| gidx[1] ).flatten()


class QAMModulator(object):

    def __init__(self, M, coding=None):
        self.M = M
        self.symbols = calculate_MQAM_symbols(M)
        self.coding = None
        self._graycode = gray_code_for_qam(M)
        self.gray_coded_symbols = self.symbols[self._graycode]
        self._encoding = dict([(s[i].tobytes(), self._graycode[i]) for i in range(len(self._graycode))])

    @property
    def bits(self):
        return int(np.log2(self.M))

    def modulate(self, data):
        rem  = len(data)%M
        if rem > 0:
            data = data[:-rem]
        datab = bitarray()
        datab.pack(data.tobytes())
        # the below is not really the fastest method but easy encoding/decoding is possible
        return np.frombytes(b''.join(datab.encode(self._encoding)), dtype=np.complex128)

    def decode(self, symbols):
        bt = bitarray()
        bt.encodode(self._encoding, symbols)
        return np.frombytes(bt.unpack, dtype=np.bool)


