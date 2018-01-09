from __future__ import division, print_function
import numpy as np
from scipy.signal import fftconvolve
from . import utils, prbs
from . import theory
#TODO: refactor to use remove all unneeded functions

class DataSyncError(Exception):
    pass

def find_sequence_offset(data_tx, data_rx, show_cc=False):
    """
    Find the offset of the transmitted data sequence inside the received data, which
    might contain errors, using cross-correlation between data_rx and data_tx.
    Calculates np.fftconvolve(data_rx, data_tx, 'same'). This assumes that len(data_rx) >= len(data_tx) and that
    data_tx is at least once inside data_rx.

    Parameters
    ----------

    data_tx : array_like
            the known input data sequence.

    data_rx : array_like
        the received data sequence which might contain errors.

    show_cc : bool, optional
        if true return the calculated crosscorrelation

    Returns
    -------
    offset index : int
        the index where data_tx starts in data_rx
    crosscorrelation: array_like, optional
        the autocorrelation
    """
    # needed to convert bools to integers
    tx = 1.*data_tx
    rx = 1.*data_rx
    N_rx = rx.shape[0]
    N_tx = tx.shape[0]
    assert not N_tx > N_rx, "length of data tx must be shorter or equal to length of data_rx"
    if tx.dtype==np.complex128:
        ac = fftconvolve(np.angle(rx), np.angle(tx)[::-1], 'same')
    else:
        ac = fftconvolve(rx, tx[::-1], 'same')
    if N_rx == N_tx:
        idx = abs(ac).argmax()-N_tx//2
        if idx < 0:
            idx += N_tx
    elif N_rx > N_tx:
        idx = abs(ac).argmax() - N_tx//2
    if show_cc is True:
        return idx, ac
    else:
        return idx

def find_sequence_offset_complex(data_tx, data_rx):
    """
    Find the offset of one sequence in the other even if both sequences are complex.

    Parameters
    ----------
    data_tx : array_like
        transmitted data sequence
    data_rx : array_like
        received data sequence

    Returns
    -------
    idx : integer
        offset index
    tx : array_like
        tx array possibly rotated to correct 1.j**i for complex arrays
    """
    acm = 0.
    try:
        data_tx.imag
        data_rx.imag
    except:
        return find_sequence_offset(data_tx, data_rx), data_tx
    for i in range(4):
        tx = data_tx*1.j**i
        idx, ac = find_sequence_offset(tx, data_rx, show_cc=True)
        act = abs(ac).max()
        if act > acm:
            ii = i
            ix = idx
            acm = act
    return ix, data_tx*1.j**ii


def sync_and_adjust(data_tx, data_rx, adjust="tx"):
    """
    Synchronize and adjust length of received and transmitted data sequence. When the length
    differs between sequences the sequence length will be adjusted based on the adjust parameter
    and the length of the sequences. If the to adjusting sequence is shorter than the other sequence,
    we will assume that the pattern is repetitive and therefore pad the sequence. If it is longer than
    the other sequence we will truncate after adjusting the offset. Note that if sequences are complex we will
    rotate around the complex plane to remove abiguities.

    Parameters
    ----------
    data_tx : array_like
        transmitted symbol or bit sequence
    data_rx : array_like
        received symbol sequence can be noisy
    adjust : string, optional
        parameter that determines which data sequence to adjust. If "tx" truncate or extend data_tx
        if "rx" truncate or extend data_rx

    Returns
    -------
    tx : array_like
       (possibly adjusted) tx data
    rx : array_like
       (possibly adjusted) rx data
    """
    N_tx = data_tx.shape[0]
    N_rx = data_rx.shape[0]
    assert adjust is "tx" or adjust is "rx", "adjust need to be either 'tx' or 'rx'"
    if N_tx > N_rx:
        offset, rx = find_sequence_offset_complex(data_rx, data_tx)
        if adjust is "tx":
            tx = np.roll(data_tx, -offset)
            return adjust_data_length(tx, rx, method="truncate")
        elif adjust is "rx":
            tx, rx = adjust_data_length(data_tx, rx, method="extend")
            return tx, np.roll(rx, offset)
    elif N_tx < N_rx:
        offset, tx = find_sequence_offset_complex(data_tx, data_rx)
        if adjust is "tx":
            tx, rx = adjust_data_length(tx, data_rx, method="extend")
            return np.roll(tx, offset), rx
        elif adjust is "rx":
            rx = np.roll(data_rx, -offset)
            return adjust_data_length(tx, rx, method="truncate")
    else:
        offset, tx = find_sequence_offset_complex(data_tx, data_rx)
        if adjust is "tx":
            return np.roll(tx, offset), data_rx
        elif adjust is "rx":
            return tx, np.roll(data_rx, -offset)

def sync_rx2tx(data_tx, data_rx, Lsync, imax=200):
    """Sync the received data sequence to the transmitted data, which
    might contain errors. Starts to with data_rx[:Lsync] if it does not find
    the offset it will iterate through data[i*Lsync:Lsync*(i+1)] until offset is found
    or imax is reached.

    Parameters
    ----------
    data_tx : array_like
            the known input data sequence.
    data_rx : array_like
        the received data sequence which might contain errors.
    Lsync : int
        the number of elements to use for syncing.
    imax : imax, optional
        maximum number of tries before giving up (the default is 200).

    Returns
    -------
    offset index : int
        the index where data_rx starts in data_rx
    data_rx_sync : array_like
        data_rx which is synchronized to data_tx

    Raises
    ------
    DataSyncError
        If no position can be found.
    """
    for i in np.arange(imax)*Lsync:
        try:
            sequence = data_rx[i:i + Lsync]
            idx_offs = utils.find_offset(sequence, data_tx)
            idx_offs = idx_offs - i
            data_rx_synced = np.roll(data_rx, idx_offs)
            return idx_offs, data_rx_synced
        except ValueError:
            pass
    raise DataSyncError("maximum iterations exceeded")

def sync_tx2rx(data_tx, data_rx, Lsync, imax=200):
    """Sync the transmitted data sequence to the received data, which
    might contain errors. Starts to with data_rx[:Lsync] if it does not find
    the offset it will iterate through data[i:Lsync+i] until offset is found
    or imax is reached.

    Parameters
    ----------
    data_tx : array_like
            the known input data sequence.
    data_rx : array_like
        the received data sequence which might contain errors.
    Lsync : int
        the number of elements to use for syncing.
    imax : imax, optional
        maximum number of tries before giving up (the default is 200).

    Returns
    -------
    offset index : int
        the index where data_rx starts in data_tx
    data_tx_sync : array_like
        data_tx which is synchronized to data_rx

    Raises
    ------
    DataSyncError
        If no position can be found.
    """
    for i in np.arange(imax)*Lsync:
        try:
            sequence = data_rx[i:i + Lsync]
            idx_offs = utils.find_offset(sequence, data_tx)
            idx_offs = idx_offs - i
            data_tx_synced = np.roll(data_tx, -idx_offs)
            return idx_offs, data_tx_synced
        except ValueError:
            pass
    raise DataSyncError("maximum iterations exceeded")

def adjust_data_length(data_tx, data_rx, method=None):
    """Adjust the length of data_tx to match data_rx, either by truncation
    or repeating the data.

    Parameters
    ----------
    data_tx, data_rx : array_like
        known input data sequence, received data sequence

    method : string, optional
        method to use for adjusting the length. This can be either None, "extend" or "truncate".
        Description:
            "extend"   - pad the short array with its data from the beginning. This assumes that the data is periodic
            "truncate" - cut the shorter array to the length of the longer one
            None       - (default) either truncate or extend data_tx 

    Returns
    -------
    data_tx_new, data_rx_new : array_like
        adjusted data sequences
    """
    if method is None:
        if len(data_tx) > len(data_rx):
            return data_tx[:len(data_rx)], data_rx
        elif len(data_tx) < len(data_rx):
            data_tx = _extend_by(data_tx, data_rx.shape[0]-data_tx.shape[0])
            return data_tx, data_rx
        else:
            return data_tx, data_rx
    elif method is "truncate":
        if len(data_tx) > len(data_rx):
            return data_tx[:len(data_rx)], data_rx
        elif len(data_tx) < len(data_rx):
            return data_tx, data_rx[:len(data_tx)]
        else:
            return data_tx, data_rx
    elif method is "extend":
        if len(data_tx) > len(data_rx):
            data_rx = _extend_by(data_rx, data_tx.shape[0]-data_rx.shape[0])
            return data_tx, data_rx
        elif len(data_tx) < len(data_rx):
            data_tx = _extend_by(data_tx, data_rx.shape[0]-data_tx.shape[0])
            return data_tx, data_rx
        else:
            return data_tx, data_rx

def _extend_by(data, N):
    L = data.shape[0]
    K = N//L
    rem = N%L
    data = np.hstack([data for i in range(K+1)])
    data = np.hstack([data, data[:rem]])
    return data

def cal_ber_syncd(data_rx, data_tx, threshold=0.2):
    """Calculate the bit-error rate (BER) between two synchronised binary data
    signals in linear units.

    Parameters
    ----------
    data_tx : array_like
            the known input data sequence.
    data_rx : array_like
        the received data signal stream
    threshold : float, optional
       threshold BER value. If calculated BER is larger than the threshold, an
       error is return as this likely indicates a wrong sync (default is 0.2).

    Returns
    -------
    ber : float
        bit-error rate in linear units
    errs : int
        number of counted errors.
    N : int
        length of data_tx

    Raises
    ------
    ValueError
        if ber>threshold, as this indicates a sync error.
    """
    errs = np.count_nonzero(data_rx != data_tx)
    N = len(data_tx)
    ber = errs / N
    if ber > threshold:
        raise ValueError("BER is over %.1f, this is probably a wrong sync" %
                         threshold)
    return ber, errs, N


def cal_ber_nosyncd(data_rx, data_tx):
    """
    Calculate the BER between a received bit stream and a known
    bit sequence which is not synchronised. If data_tx is shorter than data_rx it is assumed
    that data_rx is repetitive. This function automatically inverts the data if
    it fails to sync.

    Parameters
    ----------
    data_tx : array_like
        the known input data sequence.
    data_rx : array_like
        the received data sequence which might contain errors.
    Lsync : int
        the number of elements to use for syncing.
    imax : imax, optional
        maximum number of tries before giving up (the default is 200).

    Returns
    -------
    ber : float
        bit error rate in linear units
    errs : int
        number of counted errors
    N : int
        length of data
    """
    try:
        idx, data_tx_sync = find_sequence_offset(data_tx, data_rx)
    except DataSyncError:
        # if we cannot sync try to use inverted data
        idx, data_tx_sync = find_sequence_offset(-data_tx, data_rx)
    data_tx_sync = adjust_data_length(data_tx_sync, data_rx)
    #TODO this still returns a slightly smaller value, as if there would be
    # one less error, maybe this happens in the adjust_data_length
    return cal_ber_syncd(data_rx, data_tx_sync)
