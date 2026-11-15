"""Polars version of the feature engineering step.

sklearn passes a pandas DataFrame into the pipeline; every operation is done in
Polars and the result is converted back with .to_pandas() before it reaches the
ColumnTransformer / model.
"""
import math
import polars as pl
from sklearn.base import BaseEstimator, TransformerMixin

from pipeline_lib import FeatureEngineer as _Spec  # pure-python column bookkeeping only

_a = (pl.col('age') - 60) / 5
_sm = pl.col('current_smoker').fill_null(0)
_sb = (pl.col('systolic_bp') - 120) / 20
_tc = pl.col('total_cholesterol') - 6
_hd = (pl.col('hdl_cholesterol') - 1.3) / 0.5
# SCORE2 (2021) published coefficients, no diabetes -> log 10-y cumulative hazard (fixed formula)
SCORE2_LOG_CUMHAZ = pl.when(pl.col('is_male') == 1).then(
    0.3742*_a + 0.6012*_sm + 0.2777*_sb + 0.1458*_tc - 0.2698*_hd
    - 0.0755*_a*_sm - 0.0255*_a*_sb - 0.0281*_a*_tc + 0.0426*_a*_hd + math.log(-math.log(0.9605))
).otherwise(
    0.4648*_a + 0.7744*_sm + 0.3131*_sb + 0.1002*_tc - 0.2606*_hd
    - 0.1088*_a*_sm - 0.0277*_a*_sb - 0.0226*_a*_tc + 0.0613*_a*_hd + math.log(-math.log(0.9776)))

OPS = {
    'ratio_tc_hdl': (('total_cholesterol', 'hdl_cholesterol'), pl.col('total_cholesterol') / pl.col('hdl_cholesterol')),
    'non_hdl': (('total_cholesterol', 'hdl_cholesterol'), pl.col('total_cholesterol') - pl.col('hdl_cholesterol')),
    'age_x_sbp': (('age', 'systolic_bp'), pl.col('age') * pl.col('systolic_bp') / 100.0),
    'age_x_smoke': (('age', 'current_smoker'), pl.col('age') * pl.col('current_smoker')),
    'age_x_male': (('age', 'is_male'), pl.col('age') * pl.col('is_male')),
    'pulse_pressure': (('systolic_bp', 'diastolic_bp'), pl.col('systolic_bp') - pl.col('diastolic_bp')),
    'mean_art_pressure': (('systolic_bp', 'diastolic_bp'), (pl.col('systolic_bp') + 2 * pl.col('diastolic_bp')) / 3.0),
    'ratio_ldl_hdl': (('ldl_cholesterol', 'hdl_cholesterol'), pl.col('ldl_cholesterol') / pl.col('hdl_cholesterol')),
    'score2_lp': (('age', 'is_male', 'current_smoker', 'systolic_bp', 'total_cholesterol', 'hdl_cholesterol'), SCORE2_LOG_CUMHAZ),
}


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Stateless row-wise feature engineering in Polars (no fitted statistics -> no leakage)."""

    def __init__(self, ops=(), log_cols=(), drop_cols=()):
        self.ops = ops
        self.log_cols = log_cols
        self.drop_cols = drop_cols

    available_ops = staticmethod(lambda columns: _Spec.available_ops(columns))
    output_columns = staticmethod(lambda *a: _Spec.output_columns(*a))

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        d = pl.from_pandas(X)                       # pandas -> polars
        cols = list(d.columns)
        if 'sex' in cols:
            d = d.with_columns((pl.col('sex').cast(pl.Utf8) == 'male').cast(pl.Float64).alias('is_male'))
            cols = ['is_male' if c == 'sex' else c for c in cols]
        if self.ops:
            d = d.with_columns([OPS[o][1].cast(pl.Float64).alias(o) for o in self.ops])
        if self.log_cols:
            d = d.with_columns([pl.col(c).cast(pl.Float64).clip(lower_bound=0).log1p().alias(c)
                                for c in self.log_cols if c in d.columns])
        out = [c for c in cols + list(self.ops) if c not in set(self.drop_cols)]
        d = d.select(out)
        floats = [c for c, t in zip(d.columns, d.dtypes) if t in (pl.Float32, pl.Float64)]
        if floats:  # inf (e.g. division by 0) -> null, imputed later inside the CV fold
            d = d.with_columns([pl.when(pl.col(c).is_infinite()).then(None).otherwise(pl.col(c)).alias(c)
                                for c in floats])
        return d.to_pandas()                         # polars -> pandas for the model
