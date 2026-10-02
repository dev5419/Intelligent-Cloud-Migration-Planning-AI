FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/huggingface \
    COPILOT_EMBEDDING_MODEL_PATH=/opt/models/all-MiniLM-L6-v2

RUN dnf install -y libgomp && dnf clean all

COPY aws-lambda/copilot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/app/copilot_main.py ./backend/app/copilot_main.py
COPY backend/app/copilot_service.py ./backend/app/copilot_service.py
COPY backend/app/models.py ./backend/app/models.py
COPY backend/app/config.py ./backend/app/config.py
COPY copilot/llm.py ./copilot/llm.py
COPY copilot/rag.py ./copilot/rag.py
COPY copilot/vectorstore/chunks.txt ./copilot/vectorstore/chunks.txt
COPY copilot/vectorstore/migration.index ./copilot/vectorstore/migration.index

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2').save('/opt/models/all-MiniLM-L6-v2')"

ENV TRANSFORMERS_OFFLINE=1

CMD ["backend.app.copilot_main.handler"]