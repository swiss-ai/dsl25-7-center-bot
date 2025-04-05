import os
import chromadb
from chromadb.config import Settings

# Load path from .env or use default
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")

client = chromadb.PersistentClient(
    path=CHROMA_PERSIST_DIRECTORY,
    settings=Settings(anonymized_telemetry=False)
)

collection = client.get_or_create_collection("drive_chunks")

def store_chunks(file_id, file_name, chunks):
    for i, chunk in enumerate(chunks):
        chunk_id = f"{file_id}_{i}"
        metadata = {
            "file_name": file_name,
            "chunk_index": i
        }
        collection.add(
            ids=[chunk_id],
            documents=[chunk],
            metadatas=[metadata]
        )

# import os

# OUTPUT_DIR = "./output_files"
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# def store_chunks(file_id, file_name, chunks):
#     base_name = f"{file_id}_{file_name}".replace("/", "_").replace("\\", "_")
#     for i, chunk in enumerate(chunks):
#         file_path = os.path.join(OUTPUT_DIR, f"{base_name}_chunk{i}.txt")
#         with open(file_path, "w", encoding="utf-8") as f:
#             f.write(chunk)