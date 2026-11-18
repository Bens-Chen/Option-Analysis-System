import numpy as np


def _kind_to_mask(kind):
    lowered = np.char.lower(np.asarray(kind).astype(str))
    if not np.all(np.isin(lowered, ["call", "put", "c", "p"])):
        raise ValueError("kind must be 'call' or 'put'.")
    return np.isin(lowered, ["call", "c"])


def prepare(kind, *values):
    """Broadcast numeric inputs and kind ('call'/'put', str or array) together.

    Returns (is_call, *float_arrays), all with one common shape.
    """
    arrays = np.broadcast_arrays(_kind_to_mask(kind), *(np.asarray(v, dtype=float) for v in values))
    return arrays[0], *arrays[1:]


def maybe_scalar(result, *inputs):
    """Return a Python float when every input was a scalar."""
    if all(np.ndim(v) == 0 for v in inputs):
        return float(np.asarray(result).reshape(-1)[0])
    return result
