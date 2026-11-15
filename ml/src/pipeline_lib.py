"""Building blocks used by the code the agent generates."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


def _score2_log_cumhaz(d):
    """SCORE2 (2021) published coefficients, no diabetes: log 10-y cumulative hazard
    = linear predictor + log(-log S0_sex). Fixed formula (nothing fitted -> no leakage)."""
    a = (d.age - 60) / 5; sm = d.current_smoker.fillna(0); sb = (d.systolic_bp - 120) / 20
    tc = d.total_cholesterol - 6; hd = (d.hdl_cholesterol - 1.3) / 0.5
    m = (0.3742*a + 0.6012*sm + 0.2777*sb + 0.1458*tc - 0.2698*hd
         - 0.0755*a*sm - 0.0255*a*sb - 0.0281*a*tc + 0.0426*a*hd + np.log(-np.log(0.9605)))
    f = (0.4648*a + 0.7744*sm + 0.3131*sb + 0.1002*tc - 0.2606*hd
         - 0.1088*a*sm - 0.0277*a*sb - 0.0226*a*tc + 0.0613*a*hd + np.log(-np.log(0.9776)))
    return np.where(d.is_male == 1, m, f)


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Stateless, row-wise feature engineering (no leakage: no fitted statistics)."""

    OPS = {
        'ratio_tc_hdl': (('total_cholesterol', 'hdl_cholesterol'), lambda d: d.total_cholesterol / d.hdl_cholesterol),
        'non_hdl': (('total_cholesterol', 'hdl_cholesterol'), lambda d: d.total_cholesterol - d.hdl_cholesterol),
        'age_x_sbp': (('age', 'systolic_bp'), lambda d: d.age * d.systolic_bp / 100.0),
        'age_x_smoke': (('age', 'current_smoker'), lambda d: d.age * d.current_smoker),
        'age_x_male': (('age', 'is_male'), lambda d: d.age * d.is_male),
        'pulse_pressure': (('systolic_bp', 'diastolic_bp'), lambda d: d.systolic_bp - d.diastolic_bp),
        'mean_art_pressure': (('systolic_bp', 'diastolic_bp'), lambda d: (d.systolic_bp + 2 * d.diastolic_bp) / 3.0),
        'ratio_ldl_hdl': (('ldl_cholesterol', 'hdl_cholesterol'), lambda d: d.ldl_cholesterol / d.hdl_cholesterol),
        'score2_lp': (('age', 'is_male', 'current_smoker', 'systolic_bp', 'total_cholesterol', 'hdl_cholesterol'),
                      lambda d: _score2_log_cumhaz(d)),
    }

    def __init__(self, ops=(), log_cols=(), drop_cols=()):
        self.ops = ops
        self.log_cols = log_cols
        self.drop_cols = drop_cols

    @classmethod
    def available_ops(cls, columns):
        cols = set(columns) | {'is_male'}
        return [k for k, (req, _) in cls.OPS.items() if set(req) <= cols]

    @classmethod
    def output_columns(cls, columns, ops, log_cols, drop_cols):
        out = ['is_male' if c == 'sex' else c for c in columns]
        out += [o for o in ops]
        return [c for c in out if c not in drop_cols]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        d = X.copy()
        if 'sex' in d:
            d['is_male'] = (d.pop('sex').astype(str) == 'male').astype(float)
            cols = ['is_male' if c == 'sex' else c for c in X.columns]
            d = d[cols]
        for op in self.ops:
            d[op] = self.OPS[op][1](d).astype(float)
        for c in self.log_cols:
            if c in d:
                d[c] = np.log1p(d[c].clip(lower=0))
        d = d.drop(columns=[c for c in self.drop_cols if c in d])
        return d.replace([np.inf, -np.inf], np.nan)
