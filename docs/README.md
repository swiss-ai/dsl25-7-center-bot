# 🤖 ETH AI Center Chatbot

Under the Swiss AI Initiative, this project implements a ChatBot integrated to Slack.
The goal is to build an agent which facilitate workflows/tasks people carry out at the ETH AI Center.

---

## Directory Structure

- `config/` - Configuration files, credentials, and environment settings
- `db/` - Database files including SQLite and ChromaDB vector store
- `docker/` -  Includes Dockerfiles and related resources for containerizing the application
- `docs/` - Contains documentation files, which may include usage guides, API references, and system architecture details.
- `scripts/` - Utility scripts to manually update the database, search it, etc..
- `src/` - Main application source code (go to each subfolder to have more information about each component)
- `tests/ and test_bot` - Test files and test bot implementation

---

## 🌐 Data Source Integrations

- **Airtable**: Structured project or research metadata
- **Notion**: Personal or institutional pages and databases
- **Google Drive**: Syncs and indexes files from shared drives or folders
- **Web Scraping**: Crawls and extracts content from predefined URLs
- **Slack**: Previous messages in a channel

---

# 🧰 Technologies Used


This project brings together multiple cutting-edge technologies to build a modular AI assistant. In particular, it leverages Retrieval-Augmented Generation (RAG) and Model Context Protocol (MCP) tools.


## An LLM-powered ChatBot:

Uses an LLM API from Anthropic. More specifically, we query the following model **claude-3-5-sonnet-2024062**. It was released in 2024 and has offers the following features:

- High-quality long-context understanding
- Strong reasoning and summarization abilities

## 🧾 Chroma DB (Vector Database)

- Used to store and retrieve document embeddings.
- Supports fast approximate nearest neighbor (ANN) search for similarity-based retrieval.
- Enables scalable document indexing from diverse sources like Notion, web, and Google Drive.

## 🔍 Retrieval-Augmented Generation (RAG)

- Combines a language model with a retrieval system to answer queries using **external knowledge**.
- Embeddings are generated from various data sources (web pages, Airtable, Notion, Google Drive, etc.) and stored in a **vector database (Chroma DB)**.
- During query time, the system retrieves the most relevant documents from the vector DB and passes them to the LLM as context.

### ✳️ Embedding Model
- Uses the `"all-MiniLM-L6-v2"` model from **SentenceTransformers**.
  - A lightweight, high-performance transformer optimized for semantic similarity tasks.
  - Converts text into dense vector representations for efficient retrieval.


## 🧠 MCP (Model Context Protocol)

MCP is an open protocol that standardizes how applications provide context to LLMs. Developers can create MCP tools along with descriptions, enabling the LLM to call these tools and obtain tailored context. This context can for instance come from an API call to an external data source or from a well-crafted prompt.
It can be more efficient and better suited for a specific prompt than querying an entire RAG database.
Here are a few examples where we used this protocol in the codebase:

- Access to Airtables 
- Access to Slack channel messages

---
## 🐳 Deployment & DevOps

- **Docker**: Containerization of services for reproducible builds and easy deployment.

TODO

---
# Axis of future improvements:

- Build profiles of ETH fellows (scraping more web sources)
- Build a reward model to align LLM answers with users' preferences (RHLF)