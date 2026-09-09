from __future__ import annotations

import json
import logging
import warnings
from functools import lru_cache

import joblib

from app.core.config import get_settings
from app.core.exceptions import ModelNotLoadedError
"""Loaders for the two sklearn artifacts behind the fertilizer and crop tools."""

logger = logging.getLogger(__name__)

# Column order the estimators were fit on. Inputs are numpy rows, not DataFrames.
FERTILIZER_FEATURES = ("moist", "soilT", "EC", "airT", "airH", "Fase_Tanam")
CROP_FEATURES = ("N", "P", "K", "temperature", "humidity", "ph", "rainfall")
PLANT_HEALTH_FEATURES  =['Soil_Moisture', 'Ambient_Temperature',
       'Soil_Temperature', 'Humidity', 'Light_Intensity', 'Soil_pH',
       'Nitrogen_Level', 'Phosphorus_Level', 'Potassium_Level',
       'Chlorophyll_Content', 'Electrochemical_Signal']

FERTILIZER_LABELS = ("Flushing Air", "KCl", "NPK 15-10-12", "SP-36", "Urea", "ZA")
CROP_CLASS_COUNT = 22
RICE_CLASS = 20
PLANT_HEALTH_CLASS_COUNT = 11
PLANT_HEALTH_TARGET_CLASS = 3


def _load(path):
    if not path.exists():
        raise ModelNotLoadedError(f"model file not found at {path}")
    # Trained on sklearn 1.6.1, served on a newer minor. Tree pickles are stable
    # across minors and predictions were verified identical on sample rows.
    with warnings.catch_warnings():
        
        warnings.simplefilter("ignore")
        model = joblib.load(path)
        
    logger.info("loaded %s", path.name)
    
    return model


@lru_cache
def get_fertilizer_model():
    model = _load(get_settings().fertilizer_model_path)
    
    if model.n_features_in_ != len(FERTILIZER_FEATURES):
        
        
        raise ModelNotLoadedError(f"fertilizer model expects {model.n_features_in_} features, want 6")
    if tuple(model.classes_) != FERTILIZER_LABELS:
        
        raise ModelNotLoadedError(f"fertilizer model classes {list(model.classes_)} differ from the known labels")
    
    return model


@lru_cache
def get_crop_model():
    
    model = _load(get_settings().crop_model_path)
    
    if model.n_features_in_ != len(CROP_FEATURES):
        
        raise ModelNotLoadedError(f"crop model expects {model.n_features_in_} features, want 7")
    if len(model.classes_) != CROP_CLASS_COUNT:
        
        raise ModelNotLoadedError(f"crop model has {len(model.classes_)} classes, want {CROP_CLASS_COUNT}")
    
    return model


@lru_cache
def get_crop_classes() -> dict[int, str]:
    """int class -> crop name, from the LabelEncoder mapping saved next to the model."""
    path = get_settings().crop_class_path
    
    if not path.exists():
        
        raise ModelNotLoadedError(f"crop class map not found at {path}")
    with path.open(encoding="utf-8") as fh:
        
        raw = json.load(fh)
        
    classes = {int(k): str(v) for k, v in raw.items()}
    
    if len(classes) != CROP_CLASS_COUNT or classes.get(RICE_CLASS) != "rice":
        raise ModelNotLoadedError("crop_class.json must hold 22 classes with rice at 20")
    
    return classes


def quiet_predict(method, row):
    """Run predict/predict_proba on a numpy row without the feature-names warning.

    Both estimators were fit on DataFrames; we feed arrays in the same column
    order on purpose, so the warning is noise."""
    with warnings.catch_warnings():
        
        warnings.simplefilter("ignore", UserWarning)
        return method(row)


def is_fertilizer_model_available() -> bool:
    
    try:
        get_fertilizer_model()
        return True
    
    except Exception:
        return False


def is_crop_model_available() -> bool:
    try:
        get_crop_model()
        get_crop_classes()
        
        return True
    
    except Exception:
        
        return False
