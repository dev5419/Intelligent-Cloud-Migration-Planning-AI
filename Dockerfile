FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/huggingface \
    COPILOT_EMBEDDING_MODEL_PATH=/opt/models/all-MiniLM-L6-v2

RUN dnf install -y libgomp && dnf clean all

COPY backend/lambda-requirements.txt /tmp/requirements.txt

RUN pip install \
    --no-cache-dir \
    --default-timeout=1000 \
    --retries=10 \
    -r /tmp/requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2').save('/opt/models/all-MiniLM-L6-v2')" \
    && rm -rf "${HF_HOME}"

ENV TRANSFORMERS_OFFLINE=1

COPY . ${LAMBDA_TASK_ROOT}

CMD ["backend.app.main.handler"]