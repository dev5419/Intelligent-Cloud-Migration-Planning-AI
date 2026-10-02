FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN dnf install -y libgomp && dnf clean all

COPY aws-lambda/core/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/app ./backend/app
COPY Wave_Planner/wave_planner ./Wave_Planner/wave_planner
COPY ["Cost and Risk/cost.py", "Cost and Risk/cost.py"]
COPY data/processed/application_portfolio_1000.csv ./data/processed/application_portfolio_1000.csv
COPY notebook/model.joblib ./notebook/model.joblib
COPY notebook/label_encoder.joblib ./notebook/label_encoder.joblib

CMD ["backend.app.main.handler"]