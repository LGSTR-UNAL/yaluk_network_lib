def lineparam_stub(cond, Xi, hm, rc):
    if cond <= 0: return [],[],[]
    Lm = [[0.0]*cond for _ in range(cond)]
    Cm = [[0.0]*cond for _ in range(cond)]
    Zc = [[0.0]*cond for _ in range(cond)]
    return Lm, Cm, Zc
