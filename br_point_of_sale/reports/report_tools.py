# --*-- coding: utf-8 --*--
import math

def round_down(f, n):
    """
    Truncates/pads a float f to n decimal places without rounding
    @param f: float
    @param n:
    @return: float
    """
    s = '%.12f' % f
    i, p, d = s.partition('.')
    return float('.'.join([i, (d + '0' * n)[:n]]))