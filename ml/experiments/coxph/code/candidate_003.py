# coxph | visits=3 | age=all | imp=median | scale=standard | {"alpha": 0.1, "ties": "efron"}
# status=ok cv_auc=0.6867716304607321

def build_pipeline():
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer, KNNImputer
    from sklearn.preprocessing import (StandardScaler, RobustScaler, QuantileTransformer,
                                       SplineTransformer, OneHotEncoder)
    from pipeline_lib_pl import FeatureEngineer
    from surv_models import SurvivalModel

    features = FeatureEngineer(ops=[], log_cols=[], drop_cols=[])
    preprocess = ColumnTransformer([
        ('continuous', Pipeline([('impute', SimpleImputer(strategy='median', add_indicator=False)), ('scale', StandardScaler())]), ['age', 'systolic_bp', 'total_cholesterol', 'hdl_cholesterol']),
        ('binary', SimpleImputer(strategy='most_frequent'), ['is_male', 'current_smoker']),
        ('multicat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), []),
    ], remainder='drop').set_output(transform='pandas')
    model = SurvivalModel(family='coxph', params={'alpha': 0.1, 'ties': 'efron'}, monotone=False, n_jobs=-1)
    return Pipeline([('features', features), ('preprocess', preprocess), ('model', model)])
