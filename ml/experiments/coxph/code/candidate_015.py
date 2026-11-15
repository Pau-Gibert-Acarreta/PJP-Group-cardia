# coxph | visits=3 | age=40-69 | imp=median | fe=ratio_tc_hdl,age_x_sbp | scale=standard | splines | {"alpha": 0.1, "ties": "efron"}
# status=ok cv_auc=0.6789636307979066

def build_pipeline():
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer, KNNImputer
    from sklearn.preprocessing import (StandardScaler, RobustScaler, QuantileTransformer,
                                       SplineTransformer, OneHotEncoder)
    from pipeline_lib_pl import FeatureEngineer
    from surv_models import SurvivalModel

    features = FeatureEngineer(ops=['ratio_tc_hdl', 'age_x_sbp'], log_cols=[], drop_cols=[])
    preprocess = ColumnTransformer([
        ('continuous', Pipeline([('impute', SimpleImputer(strategy='median', add_indicator=False)), ('scale', StandardScaler()), ('spline', SplineTransformer(n_knots=4, degree=3))]), ['age', 'systolic_bp', 'total_cholesterol', 'hdl_cholesterol', 'ratio_tc_hdl', 'age_x_sbp']),
        ('binary', SimpleImputer(strategy='most_frequent'), ['is_male', 'current_smoker']),
        ('multicat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), []),
    ], remainder='drop').set_output(transform='pandas')
    model = SurvivalModel(family='coxph', params={'alpha': 0.1, 'ties': 'efron'}, monotone=False, n_jobs=-1)
    return Pipeline([('features', features), ('preprocess', preprocess), ('model', model)])
