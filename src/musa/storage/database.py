import sqlite3
import json
import numpy as np
import faiss
from pathlib import Path

from musa.storage.models import Document


class Database:
    def __init__(self, path: str = "data/musa.db") -> None:
        self.path = Path(path)
        self.index_path = self.path.with_suffix(".index")

        # Make sure the data directory exists.
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # check_same_thread=False is required for Streamlit/Multi-threaded apps
        self.connection = sqlite3.connect(self.path, check_same_thread=False)

        self._create_tables()
        self._init_faiss_index()

    def _create_tables(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                description TEXT DEFAULT '',
                domain TEXT DEFAULT '',
                crawled_at TEXT NOT NULL,
                vector TEXT
            )
            """
        )

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_url TEXT NOT NULL,
                FOREIGN KEY (source_id)
                    REFERENCES documents(id)
            )
            """
        )

        # FTS5 Virtual Table for fast lexical search
        self.connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                title,
                content,
                description,
                content='documents',
                content_rowid='id'
            );
            """
        )

        # Triggers to keep FTS5 index in sync with documents table
        self.connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents
            BEGIN
                INSERT INTO documents_fts(rowid, title, content, description)
                VALUES (new.id, new.title, new.content, new.description);
            END;
            """
        )
        self.connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents
            BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, title, content, description)
                VALUES('delete', old.id, old.title, old.content, old.description);
            END;
            """
        )
        self.connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents
            BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, title, content, description)
                VALUES('delete', old.id, old.title, old.content, old.description);
                INSERT INTO documents_fts(rowid, title, content, description)
                VALUES (new.id, new.title, new.content, new.description);
            END;
            """
        )

        self.connection.commit()

    def _init_faiss_index(self) -> None:
        if self.index_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
            except Exception:
                self._rebuild_index()
        else:
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        cursor = self.connection.execute(
            "SELECT id, vector FROM documents WHERE vector IS NOT NULL"
        )
        rows = cursor.fetchall()

        if not rows:
            # Initialize an empty index with correct dimension (384 for all-MiniLM-L6-v2)
            dimension = 384
            index = faiss.IndexFlatIP(dimension)
            self.index = faiss.IndexIDMap(index)
            self._save_index()
            return

        ids = []
        vectors = []
        for row in rows:
            ids.append(row[0])
            vectors.append(json.loads(row[1]))

        vectors_np = np.array(vectors).astype("float32")
        faiss.normalize_L2(vectors_np)

        dimension = vectors_np.shape[1]
        index = faiss.IndexFlatIP(dimension)
        self.index = faiss.IndexIDMap(index)
        self.index.add_with_ids(vectors_np, np.array(ids).astype("int64"))
        self._save_index()

    def _save_index(self) -> None:
        faiss.write_index(self.index, str(self.index_path))

    def add_document(self, document: Document) -> int:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO documents
            (url, title, content, description, domain, crawled_at, vector)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.url,
                document.title,
                document.content,
                document.description,
                document.domain,
                document.crawled_at.isoformat()
                if document.crawled_at
                else None,
                json.dumps(document.vector) if document.vector else None,
            ),
        )

        self.connection.commit()

        cursor = self.connection.execute(
            "SELECT id FROM documents WHERE url = ?",
            (document.url,),
        )
        doc_id = cursor.fetchone()[0]

        # Update FAISS index if a vector is present
        if document.vector:
            vector_np = np.array([document.vector]).astype("float32")
            faiss.normalize_L2(vector_np)
            self.index.add_with_ids(vector_np, np.array([doc_id]).astype("int64"))
            self._save_index()

        return doc_id


    def add_link(
        self,
        source_id: int,
        target_url: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO links
            (source_id, target_url)
            VALUES (?, ?)
            """,
            (source_id, target_url),
        )

        self.connection.commit()




    def lexical_search(self, query: str, top_n: int = 5) -> list[Document]:
        cursor = self.connection.execute(
            """
            SELECT d.url, d.title, d.content, d.description, d.domain, d.crawled_at, bm25(documents_fts) as rank
            FROM documents d
            JOIN documents_fts f ON d.id = f.rowid
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, top_n),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                Document(
                    url=row[0],
                    title=row[1],
                    content=row[2],
                    description=row[3],
                    domain=row[4],
                    crawled_at=row[5],
                    score=row[6],
                )
            )

        return results

    def semantic_search(self, query_vector: list[float], top_n: int = 5) -> list[Document]:
        # Normalize the query vector for cosine similarity (Inner Product on normalized vectors)
        query_np = np.array([query_vector]).astype("float32")
        faiss.normalize_L2(query_np)

        # search returns distances and indices
        distances, indices = self.index.search(query_np, top_n)

        # FAISS may return -1 for indices if not enough results are found
        valid_indices = [idx for idx in indices[0] if idx != -1]

        if not valid_indices:
            return []

        # Fetch documents from SQLite for the retrieved IDs
        # Convert numpy int64 to python int for sqlite compatibility
        python_indices = [int(idx) for idx in valid_indices]
        placeholders = ",".join(["?"] * len(python_indices))
        cursor = self.connection.execute(
            f"SELECT id, url, title, content, description, domain, crawled_at FROM documents WHERE id IN ({placeholders})",
            python_indices,
        )

        docs_map = {}
        for row in cursor.fetchall():
            docs_map[row[0]] = Document(
                url=row[1],
                title=row[2],
                content=row[3],
                description=row[4],
                domain=row[5],
                crawled_at=row[6],
            )

        # Return documents in the order returned by FAISS
        results = []
        for idx in valid_indices:
            if idx in docs_map:
                doc = docs_map[idx]
                pos = indices[0].tolist().index(idx)
                doc.score = float(distances[0][pos])
                results.append(doc)

        return results

    def count_documents(self) -> int:


        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM documents"
        )

        return cursor.fetchone()[0]

    def close(self) -> None:
        self.connection.close()

    def clear_index(self) -> None:
        """Wipe all documents and reset the FAISS index."""
        self.connection.execute("DELETE FROM documents")
        self.connection.execute("DELETE FROM links")
        self.connection.execute("DELETE FROM documents_fts")
        self.connection.commit()

        if self.index_path.exists():
            self.index_path.unlink()

        self._rebuild_index()
