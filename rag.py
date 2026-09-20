"""Minimal RAG: embed documents, retrieve top-k, generate an answer with Claude."""
import os
import numpy as np
import anthropic
from sentence_transformers import SentenceTransformer

_embedder = None
SYSTEM = ("You are a careful weather assistant for India. Answer ONLY from the provided data snippets, which may "
          "cover several cities or states; compare them when asked. Give concrete numbers, dates and place names, "
          "state uncertainty for later days, and say so if the data does not cover the question. "
          "Forecasts come from numerical models that assimilate satellite data.")


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


class VectorStore:
    def __init__(self, docs, tags):
        self.docs, self.tags = docs, [t.lower() for t in tags]  # tag = city name of each doc
        self.vecs = embedder().encode(docs, normalize_embeddings=True)

    def search(self, query, k=6):
        q = embedder().encode([query], normalize_embeddings=True)[0]
        scores = self.vecs @ q
        ql = query.lower()
        scores = scores + np.array([0.3 if t in ql else 0.0 for t in self.tags])  # boost cities named in the question
        return [self.docs[i] for i in np.argsort(-scores)[:k]]


def answer(store, scope, question, k=8):
    hits = store.search(question, k)
    context = "\n".join(f"- {h}" for h in hits)
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    msg = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5"), max_tokens=900, system=SYSTEM,
        messages=[{"role": "user", "content": f"Scope: {scope}\n\nData:\n{context}\n\nQuestion: {question}"}])
    return msg.content[0].text, hits
