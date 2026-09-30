from pathlib import Path

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import faiss


DOCUMENTS_DIR = Path(__file__).parent / "documents"
VECTORSTORE_DIR = Path(__file__).parent / "vectorstore"

MODEL_NAME = "all-MiniLM-L6-v2"


def load_pdf(pdf_path):
    reader = PdfReader(str(pdf_path))

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


def split_text(text, chunk_size=500, overlap=100):
    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def main():
    pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found.")
        return

    all_chunks = []
    sources = []

    for pdf_file in pdf_files:
        print(f"Reading: {pdf_file.name}")

        text = load_pdf(pdf_file)

        chunks = split_text(text)

        all_chunks.extend(chunks)
        sources.extend([pdf_file.name] * len(chunks))

    print(f"Created {len(all_chunks)} text chunks.")

    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    print("Creating embeddings...")
    embeddings = model.encode(
        all_chunks,
        convert_to_numpy=True,
        show_progress_bar=True,
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    VECTORSTORE_DIR.mkdir(exist_ok=True)

    faiss.write_index(
        index,
        str(VECTORSTORE_DIR / "migration.index"),
    )

    with open(VECTORSTORE_DIR / "chunks.txt", "w", encoding="utf-8") as f:
        for source, chunk in zip(sources, all_chunks):
            f.write(f"SOURCE: {source}\n")
            f.write(chunk.replace("\n", " "))
            f.write("\n---CHUNK---\n")

    print()
    print("FAISS knowledge base created successfully.")
    print(f"Documents: {len(pdf_files)}")
    print(f"Chunks: {len(all_chunks)}")
    print(f"Vector dimension: {dimension}")


if __name__ == "__main__":
    main()