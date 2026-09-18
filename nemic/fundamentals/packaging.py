"""Portable correction packages with unchanged reload predictions; research only."""
import json
import shutil
from pathlib import Path

import joblib
import numpy as np

from nemic.experiments.core import digest
from nemic.production.registry import validate_package
from .tracking import atomic


def export_model(folder,destination,band):
    folder,destination=Path(folder),Path(destination)
    if destination.exists():raise ValueError('Immutable package destination already exists')
    bundle=joblib.load(folder/'model.joblib')
    destination.mkdir(parents=True)
    shutil.copyfile(folder/'model.joblib',destination/'model.joblib')
    lo,hi=((1,12),(13,48),(49,144),(145,336))[band]
    manifest=dict(id=f"{bundle['connector'].lower()}-fundamentals-{bundle['target']}-band{band}",version=digest(folder/'model.joblib')[:12],
        connectors=[bundle['connector']],target=bundle['target'],lead_min=lo,lead_max=hi,resolution_minutes=30,
        adapter='fundamentals-v3',recipe='fundamentals-v3',features=bundle['columns'],status='research',
        training_cutoff=bundle['training_cutoff'],calibration_end=bundle['calibration_end'],
        evaluation='Chronological retrospective development; acceptance and source-vintage gates remain explicit',
        dependencies={'methodology':bundle['methodology'],'feature_version':bundle['feature_version']},
        artifacts={'model.joblib':digest(destination/'model.joblib')})
    atomic(destination/'manifest.json',json.dumps(manifest,indent=2));validate_package(destination)
    return destination


def predict(bundle,features):
    if list(features)!=bundle['columns']:raise ValueError('Ordered feature schema mismatch')
    if 'own_anchor' not in features or not np.isfinite(features.own_anchor).all():raise ValueError('Finite target anchor required')
    point=features.own_anchor.to_numpy()+bundle['model'].predict(features)
    adjustments=np.asarray(bundle['adjustments'],dtype=float)
    if adjustments.ndim!=1 or len(adjustments)!=len(bundle['levels']) or not np.isfinite(adjustments).all() or (np.diff(adjustments)<0).any():
        raise ValueError('Invalid calibrated interval contract')
    if not np.isfinite(point).all():raise ValueError('Non-finite model predictions')
    return point,point[:,None]+adjustments
