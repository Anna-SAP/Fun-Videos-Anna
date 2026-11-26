"""Traditional -> simplified for matching transcriptions to the lyrics (the transcriber drifts into traditional)."""
import opencc
_cc = opencc.OpenCC('t2s')


def t2s(s):
    return _cc.convert(s)
