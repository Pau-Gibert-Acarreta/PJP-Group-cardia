"""Survival model wrappers with a common scikit-learn interface.

y passed to fit() is a 2-column array/DataFrame: [event (0/1), time (days, truncated at 10 y)].
predict(X) returns a RISK SCORE: higher = higher risk = shorter expected survival.
Every wrapper checks the orientation on its own training data once (deterministic)
so that all families return risk in the same direction.
"""
import sys, types
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin

# scikit-survival imports `ecos` only for MinlipSurvivalAnalysis / NaiveSurvivalSVM, which are
# not used here. On Windows + Python 3.13 ecos has no prebuilt wheel, so sksurv is installed
# with --no-deps; this placeholder lets `sksurv.svm` import without it.
try:
    import ecos  # noqa: F401
except ImportError:
    sys.modules['ecos'] = types.ModuleType('ecos')

# expected direction of each predictor on risk (used for monotone constraints)
MONOTONE_SIGN = {
    'age': 1, 'systolic_bp': 1, 'diastolic_bp': 1, 'total_cholesterol': 1, 'hdl_cholesterol': -1,
    'ldl_cholesterol': 1, 'current_smoker': 1, 'cigarettes_per_day': 1, 'glucose': 1,
    'previous_hypertension': 1, 'is_male': 1,
    'ratio_tc_hdl': 1, 'non_hdl': 1, 'age_x_sbp': 1, 'ratio_ldl_hdl': 1, 'pulse_pressure': 1,
    'mean_art_pressure': 1, 'score2_lp': 1,
}


def harrell_c(event, time, risk):
    """Harrell's concordance index for right-censored data (ties in risk count 0.5)."""
    event = np.asarray(event).astype(bool); time = np.asarray(time, float); risk = np.asarray(risk, float)
    conc = disc = tied = 0.0
    for i in np.where(event)[0]:
        comparable = time > time[i]          # j still at risk when i had the event
        if not comparable.any():
            continue
        r = risk[comparable]
        conc += np.sum(r < risk[i]); disc += np.sum(r > risk[i]); tied += np.sum(r == risk[i])
    total = conc + disc + tied
    return float((conc + 0.5 * tied) / total) if total else float('nan')


def _split_y(y):
    y = np.asarray(y, dtype=float)
    return y[:, 0].astype(bool), y[:, 1]


def _structured(event, time):
    out = np.empty(len(event), dtype=[('event', bool), ('time', float)])
    out['event'] = event; out['time'] = time
    return out


def _feature_names(X, n):
    names = list(getattr(X, 'columns', [f'f{i}' for i in range(n)]))
    return [str(c).split('__')[-1] for c in names]


def monotone_vector(X, sign=1):
    names = _feature_names(X, X.shape[1])
    return tuple(int(sign * MONOTONE_SIGN.get(n, 0)) for n in names)


class SurvivalModel(RegressorMixin, BaseEstimator):
    """family in {coxph, coxnet, rsf, extra_trees, gbsa, svm, xgb_cox, xgb_aft, catboost_cox}."""

    def __init__(self, family='coxph', params=None, monotone=False, n_jobs=-1, random_state=42):
        self.family = family
        self.params = params
        self.monotone = monotone
        self.n_jobs = n_jobs
        self.random_state = random_state

    # ------------------------------------------------------------------ fit
    def fit(self, X, y):
        event, time = _split_y(y)
        p = dict(self.params or {})
        Xn = np.asarray(X, dtype=float)
        f = self.family
        if f == 'coxph':
            from sksurv.linear_model import CoxPHSurvivalAnalysis
            self.model_ = CoxPHSurvivalAnalysis(**p).fit(Xn, _structured(event, time))
        elif f == 'coxnet':
            from sksurv.linear_model import CoxnetSurvivalAnalysis
            alpha = p.pop('alpha')
            self.model_ = CoxnetSurvivalAnalysis(alphas=[alpha], **p).fit(Xn, _structured(event, time))
        elif f == 'rsf':
            from sksurv.ensemble import RandomSurvivalForest
            self.model_ = RandomSurvivalForest(**p, low_memory=True, n_jobs=self.n_jobs, random_state=self.random_state
                                               ).fit(Xn, _structured(event, time))
        elif f == 'extra_trees':
            from sksurv.ensemble import ExtraSurvivalTrees
            if p.get('max_samples') is not None:
                p['bootstrap'] = True        # max_samples only applies with bootstrap
            self.model_ = ExtraSurvivalTrees(**p, low_memory=True, n_jobs=self.n_jobs, random_state=self.random_state
                                             ).fit(Xn, _structured(event, time))
        elif f == 'gbsa':
            from sksurv.ensemble import GradientBoostingSurvivalAnalysis
            self.model_ = GradientBoostingSurvivalAnalysis(loss='coxph', **p, random_state=self.random_state
                                                           ).fit(Xn, _structured(event, time))
        elif f == 'svm':
            from sksurv.svm import FastSurvivalSVM   # rank_ratio=1 -> optimises concordance directly
            self.model_ = FastSurvivalSVM(**p, rank_ratio=1.0, max_iter=200, random_state=self.random_state
                                          ).fit(Xn, _structured(event, time))
        elif f == 'xgb_cox':
            from xgboost import XGBRegressor
            mono = monotone_vector(X, +1) if self.monotone else None
            self.model_ = XGBRegressor(objective='survival:cox', eval_metric='cox-nloglik', tree_method='hist',
                                       monotone_constraints=mono, n_jobs=self.n_jobs,
                                       random_state=self.random_state, verbosity=0, **p)
            self.model_.fit(Xn, np.where(event, time, -time))   # negative = censored
        elif f == 'xgb_aft':
            import xgboost as xgb
            dist = p.pop('distribution'); scale = p.pop('sigma'); rounds = p.pop('n_estimators')
            d = xgb.DMatrix(Xn)
            d.set_float_info('label_lower_bound', time)
            d.set_float_info('label_upper_bound', np.where(event, time, np.inf))
            params = {'objective': 'survival:aft', 'eval_metric': 'aft-nloglik', 'tree_method': 'hist',
                      'aft_loss_distribution': dist, 'aft_loss_distribution_scale': scale,
                      'nthread': self.n_jobs if self.n_jobs and self.n_jobs > 0 else 0,
                      'seed': self.random_state, 'verbosity': 0, **p}
            if self.monotone:   # AFT predicts survival TIME -> opposite sign
                params['monotone_constraints'] = '(' + ','.join(map(str, monotone_vector(X, -1))) + ')'
            self.model_ = xgb.train(params, d, num_boost_round=rounds)
        elif f == 'catboost_cox':
            from catboost import CatBoostRegressor
            self.model_ = CatBoostRegressor(loss_function='Cox', thread_count=self.n_jobs,
                                            random_seed=self.random_state, verbose=0,
                                            allow_writing_files=False, **p)
            self.model_.fit(Xn, np.where(event, time, -time))
        else:
            raise ValueError(f)
        # orientation check on TRAIN data only: risk must be concordant with early events
        raw = self._raw(Xn)
        self.sign_ = 1.0 if harrell_c(event, time, raw) >= 0.5 else -1.0
        return self

    def _raw(self, Xn):
        if self.family == 'xgb_aft':
            import xgboost as xgb
            return -self.model_.predict(xgb.DMatrix(Xn))   # long predicted time = low risk
        return np.asarray(self.model_.predict(Xn), dtype=float)

    def predict(self, X):
        return self.sign_ * self._raw(np.asarray(X, dtype=float))

    def score(self, X, y):
        event, time = _split_y(y)
        return harrell_c(event, time, self.predict(X))
