# coxph | visits=123 | age=all | imp=median | fe=score2_lp | log=hdl_cholesterol | scale=standard | {"alpha": 0.1, "ties": "efron"}
# status=ok cv_auc=0.6911997646252847

def build_pipeline():
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer, KNNImputer
    from sklearn.preprocessing import (StandardScaler, RobustScaler, QuantileTransformer,
                                       SplineTransformer, OneHotEncoder)
    from pipeline_lib_pl import FeatureEngineer
    from surv_models import SurvivalModel

    features = FeatureEngineer(ops=['score2_lp'], log_cols=['hdl_cholesterol'], drop_cols=[])
    preprocess = ColumnTransformer([
        ('continuous', Pipeline([('impute', SimpleImputer(strategy='median', add_indicator=True)), ('scale', StandardScaler())]), ['age', 'systolic_bp', 'total_cholesterol', 'hdl_cholesterol', 'score2_lp']),
        ('binary', SimpleImputer(strategy='most_frequent'), ['is_male', 'current_smoker']),
        ('multicat', SimpleImputer(strategy='most_frequent'), []),
    ], remainder='drop').set_output(transform='pandas')
    model = SurvivalModel(family='coxph', params={'alpha': 0.1, 'ties': 'efron'}, monotone=False, n_jobs=-1)
    return Pipeline([('features', features), ('preprocess', preprocess), ('model', model)])
