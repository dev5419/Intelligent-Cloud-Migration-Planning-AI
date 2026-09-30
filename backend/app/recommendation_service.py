from __future__ import annotations

import os
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import HTTPException, status

from .config import settings
from .data_loader import get_application_by_id, get_applications
from .models import Application, RecommendationResponse

NUM_FEATURES = [
    "cpu_usage",
    "memory_usage",
    "age_years",
    "dependency_count",
    "resource_intensity",
    "coupling_to_age",
]
ORD_FEATURES = ["criticality"]
BIN_FEATURES = ["compliance_flag"]
MODEL_FEATURES = NUM_FEATURES + ORD_FEATURES + BIN_FEATURES


def _build_model_feature_row(application: Application) -> dict[str, Any]:
    cpu_usage = float(application.cpu_usage) if application.cpu_usage is not None else 0.0
    memory_usage = float(application.memory_usage) if application.memory_usage is not None else 0.0
    age_years = float(application.age_years) if application.age_years is not None else 0.0
    dependency_count = int(application.dependency_count or 0)
    criticality = application.criticality or "Medium"
    compliance_flag = int(application.compliance_flag) if application.compliance_flag is not None else 0

    return {
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "age_years": age_years,
        "dependency_count": dependency_count,
        "criticality": criticality,
        "compliance_flag": compliance_flag,
        "resource_intensity": cpu_usage * memory_usage,
        "coupling_to_age": dependency_count / (age_years + 1),
    }


class RecommendationAdapter:
    """Adapter boundary for the real Member 3 6R model."""

    def __init__(self) -> None:
        self.model_path = settings.recommendation_model_path
        self.label_encoder_path = settings.recommendation_label_encoder_path
        self.model_loaded = False
        self.pipeline = None
        self.label_encoder = None
        self.load_error: str | None = None
        self._load_model()

    def _load_model(self) -> None:
        if not self.model_path or not os.path.exists(self.model_path):
            self.load_error = "Model artifact is missing: missing recommendation model file."
            return
        if not self.label_encoder_path or not os.path.exists(self.label_encoder_path):
            self.load_error = "Model artifact is missing: missing label encoder file."
            return

        try:
            self.pipeline = joblib.load(self.model_path)
            self.label_encoder = joblib.load(self.label_encoder_path)
            self.model_loaded = True
            self.load_error = None
        except Exception as exc:  # pragma: no cover - surfaced via HTTP error
            self.pipeline = None
            self.label_encoder = None
            self.model_loaded = False
            self.load_error = f"Unable to load Member 3 recommendation model: {exc}"

    def _ensure_loaded(self) -> None:
        if not self.model_loaded or self.pipeline is None or self.label_encoder is None:
            raise RuntimeError(self.load_error or "Recommendation model is unavailable.")

    def predict(self, application: Application) -> dict[str, Any]:
        self._ensure_loaded()
        return self._predict_with_model(application)

    def _predict_with_model(self, application: Application) -> dict[str, Any]:
        row = _build_model_feature_row(application)
        df = pd.DataFrame([row], columns=MODEL_FEATURES)

        preprocessor = self.pipeline.named_steps["preprocessor"]
        classifier = self.pipeline.named_steps["classifier"]
        X_t = preprocessor.transform(df)

        probas = classifier.predict_proba(X_t)[0]
        pred_idx = int(np.argmax(probas))
        pred_label = self.label_encoder.inverse_transform([pred_idx])[0]

        top_contributors: list[dict[str, str]] = []
        shap_available = False
        shap_summary = "SHAP values not available for this prediction."
        try:
            shap_values = shap.TreeExplainer(classifier).shap_values(X_t)
            if isinstance(shap_values, list):
                shap_for_pred = shap_values[pred_idx][0]
            else:
                shap_for_pred = shap_values[0, :, pred_idx]
            top_indices = np.argsort(np.abs(shap_for_pred))[::-1][:2]
            for idx in top_indices:
                feature_name = MODEL_FEATURES[idx]
                original_value = df.iloc[0][feature_name]
                top_contributors.append(
                    {
                        "feature": feature_name,
                        "impact": f"{shap_for_pred[idx]:+.2f}",
                        "value": str(original_value),
                    }
                )
            shap_available = True
            summary_parts = []
            for contributor in top_contributors:
                direction = "positive" if float(contributor["impact"]) > 0 else "negative"
                summary_parts.append(
                    f"{contributor['feature']}={contributor['value']} had a {direction} SHAP contribution"
                )
            shap_summary = f"Recommended for {pred_label}; the largest SHAP contributions were {' and '.join(summary_parts)}."
        except Exception:
            shap_available = False
            shap_summary = "SHAP was available in the model artifact but could not be generated for this request."

        probability_map = {
            str(cls): round(float(probas[i]), 2) for i, cls in enumerate(self.label_encoder.classes_)
        }

        explanation = {
            "model": "member_3_6r_xgboost",
            "source": self.model_path,
            "features": row,
            "top_features": [contributor["feature"] for contributor in top_contributors],
            "top_contributors": top_contributors,
            "probabilities": probability_map,
            "summary": shap_summary,
            "shap": {
                "available": shap_available,
                "top_contributors": top_contributors,
                "summary": shap_summary,
                "note": "Actual SHAP values generated from the trained Member 3 model." if shap_available else "SHAP generation failed for this request.",
            },
        }

        return {
            "recommendation": str(pred_label),
            "confidence": float(round(float(probas[pred_idx]), 2)),
            "explanation": explanation,
        }


adapter = RecommendationAdapter()


def get_recommendation(application_id: str) -> RecommendationResponse:
    try:
        application = get_application_by_id(application_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application not found: {application_id}",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application dataset is missing or unreadable.",
        ) from exc

    try:
        prediction = adapter.predict(application)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - surfaced via HTTP error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation service failed while generating the model result.",
        ) from exc

    return RecommendationResponse(
        app_id=application.id,
        application_id=application.id,
        recommendation=prediction["recommendation"],
        confidence=float(prediction["confidence"]),
        explanation=prediction["explanation"],
    )


def get_application_listing() -> list[Application]:
    return get_applications()
