import os
import time
from typing import List, Dict, Any, Tuple, Optional
from openai import OpenAI
from neo4j import GraphDatabase, Transaction, Session

# =========================
# CONFIG
# =========================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "ADD_YOUR_PASSWORD_HERE"  # Replace with your actual password


EMBEDDING_MODEL = "text-embedding-ada-002"
MODEL_DIMS = 1536

BATCH_PULL = 1100
BATCH_EMBED = 1100
REEMBED = False

NODE_LABELS = [
    ("Title", "titleEmbeddingIndex"),
    ("AbstractSentence", "abstractSentenceEmbeddingIndex"),
    ("Table", "tableEmbeddingIndex"),
    ("Author", "authorEmbeddingIndex"),
    ("Advisor", "advisorEmbeddingIndex"),
    ("Topic", "topicEmbeddingIndex"),
    ("Department", "departmentEmbeddingIndex"),
    ("University", "universityEmbeddingIndex"),
    ("Degree", "degreeEmbeddingIndex"),
    ("Figure", "figureEmbeddingIndex"),
]

RELATIONSHIP_LABELS = [
    "hasAuthor",
    "authorOf",
    "hasTitle",
    "titleOf",
    "academicAdvisor",
    "academicAdvisorOf",
    "publishedBy",
    "hasPublished",
    "issuedYear",
    "degreeType",
    "hasTopic",
    "academicDiscipline",
    "academicDisciplineOf",
    "topicOf",
    "hasFigure",
    "figureOf",
    "hasTable",
    "tableOf",
    "hasSentence",
    "sentenceOf",
]


REL_VECTOR_INDEX_NAME = "relEmbeddingIndex"
REL_TYPEONLY_VECTOR_INDEX_NAME = "relTypeOnlyEmbeddingIndex"

client = OpenAI(api_key="ADD_YOUR_OPENAI_API_KEY_HERE")  # or set directly
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# =========================
# OpenAI embedding helper
# =========================
def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    
    # clean_texts = []
    # for t in texts:
    #     if t is None:
    #         continue
    #     if len(t) == 0:
    #         continue
    #     if not t:
    #         continue
    #     if not isinstance(t, str):
    #         t = str(t)
    #     t = t.strip()
    #     clean_texts.append(t)
    # if not clean_texts:
    #     print(" Skipping empty batch — all texts were blank.")
    #     return []
    
    # resp = client.embeddings.create(model=EMBEDDING_MODEL, input=clean_texts)
    # return [d.embedding for d in resp.data]
    try:
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [d.embedding for d in resp.data]
    except Exception as e:
        print(f" Embedding failed. Example inputs: {texts}")
        raise


# =========================
# Index creation
# =========================
def create_node_vector_index(tx: Transaction, label: str, index_name: str):
    tx.run(
        f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
        FOR (n:{label}) ON (n.embedding)
        OPTIONS {{
          indexConfig: {{
            `vector.dimensions`: $dims,
            `vector.similarity_function`: "cosine"
          }}
        }}
        """,
        dims=MODEL_DIMS,
    )


def create_relationship_context_vector_index(tx: Transaction, rel_type: str, prop: str):
    index_name = f"{rel_type}_context_vector_index"
    tx.run(
        f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
        FOR ()-[r:{rel_type}]-() ON (r.{prop})
        OPTIONS {{
          indexConfig: {{
            `vector.dimensions`: $dims,
            `vector.similarity_function`: "cosine"
          }}
        }}
        """,
        dims=MODEL_DIMS,
    )

def create_relationship_vector_index(tx: Transaction, rel_type: str, prop: str):
    index_name = f"{rel_type}_vector_index"
    tx.run(
        f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
        FOR ()-[r:{rel_type}]-() ON (r.{prop})
        OPTIONS {{
          indexConfig: {{
            `vector.dimensions`: $dims,
            `vector.similarity_function`: "cosine"
          }}
        }}
        """,
        dims=MODEL_DIMS,
    )


def create_all_vector_indexes(session: Session):
    # for label, idx in NODE_LABELS:
    #     session.execute_write(create_node_vector_index, label, idx)
    for rel_type in RELATIONSHIP_LABELS:
        session.execute_write(create_relationship_context_vector_index, rel_type, "embedding")
        session.execute_write(create_relationship_vector_index, rel_type, "embedding_typeonly")
    # session.execute_write(create_relationship_vector_index, REL_VECTOR_INDEX_NAME, "embedding")
    # session.execute_write(create_relationship_vector_index, REL_TYPEONLY_VECTOR_INDEX_NAME, "embedding_typeonly")


# =========================
# Node embeddings
# =========================
NODE_FETCH_QUERIES = {
    "Title": """
        MATCH (n:Title)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.text AS title, n.abstract_text AS abstract
        LIMIT $limit
    """,
    "AbstractSentence": """
        MATCH (n:AbstractSentence)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.sentence AS sentence
        LIMIT $limit
    """,
    "Author": """
        MATCH (n:Author)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.name AS name
        LIMIT $limit
    """,
    "Advisor": """
        MATCH (n:Advisor)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.name AS name
        LIMIT $limit
    """,
    "Topic": """
        MATCH (n:Topic)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.label AS label
        LIMIT $limit
    """,
    "Department": """
        MATCH (n:Department)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.name AS name
        LIMIT $limit
    """,
    "University": """
        MATCH (n:University)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.name AS name
        LIMIT $limit
    """,
    "Degree": """
        MATCH (n:Degree)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.name AS name
        LIMIT $limit
    """,
    "Table": """
        MATCH (n:Table)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.caption_text AS caption
        LIMIT $limit
    """,
    "Figure": """
        MATCH (n:Figure)
        WHERE $reembed OR n.embedding IS NULL
        RETURN id(n) AS id, n.caption_text AS caption
        LIMIT $limit
    """,
}


def assemble_node_text(label: str, rec: Dict[str, Any]) -> str:
    if label == "Title":
        title = (rec.get("title") or "").strip()
        abstract = (rec.get("abstract") or "").strip()
        return (title + " " + abstract).strip()
    if label == "AbstractSentence":
        return (rec.get("sentence") or "").strip()
    if label in ("Table", "Figure"):
        cap_tion = (rec.get("caption") or "").strip()
        if not cap_tion:
            return None
        return cap_tion
    val = rec.get("name") or rec.get("label") or ""
    return str(val).strip()


def fetch_nodes_batch(session: Session, label: str, limit: int, reembed: bool) -> List[Dict[str, Any]]:
    rs = session.run(NODE_FETCH_QUERIES[label], limit=limit, reembed=reembed)
    return [r.data() for r in rs]


def write_node_embeddings(tx: Transaction, rows: List[Dict[str, Any]]):
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (n) WHERE id(n) = row.id
        SET n.embedding = row.embedding
        """,
        rows=rows,
    )


def embed_nodes_for_label(session: Session, label: str):
    i=0
    while True:
        batch = fetch_nodes_batch(session, label, BATCH_PULL, REEMBED)
        if not batch:
            break
        texts = [assemble_node_text(label, r) for r in batch]

        clean_texts = []
        for t in texts:
            if t is None:
                continue
            s = str(t).strip()
            if not s:
                continue
            if not t:
                return " "
            clean_texts.append(s)

        #  Add this new skip condition
        if not clean_texts:
            print(f" All {label} texts in this batch were blank — skipping to next batch {i}.")
            i = i+1
            continue

        out_rows = []
        for i in range(0, len(clean_texts), BATCH_EMBED):
            sub = clean_texts[i:i + BATCH_EMBED]
            vecs = embed_texts(sub)
            for k, v in enumerate(vecs):
                out_rows.append({"id": batch[i + k]["id"], "embedding": v})
        session.execute_write(write_node_embeddings, out_rows)
        time.sleep(0.5)


def embed_all_nodes(session: Session):
    for label, _ in NODE_LABELS:
        embed_nodes_for_label(session, label)


# =========================
# Relationship embeddings
# =========================
REL_FETCH_QUERY = """
MATCH (s)-[r]->(t)
WHERE $reembed OR r.embedding IS NULL OR r.embedding_typeonly IS NULL
OPTIONAL MATCH (s)-[:hasTitle|:titleOf]-(st:Title)
OPTIONAL MATCH (t)-[:hasTitle|:titleOf]-(tt:Title)
WITH s, r, t,
     head(collect(DISTINCT st.text)) AS st_text,
     head(collect(DISTINCT tt.text)) AS tt_text

WITH s, r, t, st_text, tt_text, type(r) AS rel_type, labels(s) AS sl, labels(t) AS tl
WITH s, r, t, st_text, tt_text, rel_type, sl, tl,
     CASE
       WHEN 'AbstractSentence' IN sl THEN s.classified_label
       WHEN 'AbstractSentence' IN tl THEN t.classified_label
       ELSE NULL
     END AS classified_label

WITH r, rel_type, sl, tl, st_text, tt_text, s, t, classified_label,
     CASE
       WHEN 'ETD' IN sl     AND rel_type <> 'hasTitle' AND rel_type <> 'titleOf' THEN coalesce(st_text, toString(s.etdId))
       WHEN 'Title' IN sl THEN s.text
       WHEN 'Author' IN sl OR 'Advisor' IN sl OR 'Department' IN sl
         OR 'University' IN sl OR 'Degree' IN sl THEN s.name
       WHEN 'Year' IN sl THEN toString(s.value)
       WHEN 'Topic' IN sl THEN s.label
       WHEN 'Figure' IN sl OR 'Table' IN sl THEN s.caption_text
       WHEN 'AbstractSentence' IN sl THEN s.sentence
       ELSE coalesce(toString(s.etdId), s.name, s.label, s.text, s.caption_text, s.sentence)
     END AS src_text,
     CASE
       WHEN 'ETD' IN tl     AND rel_type <> 'hasTitle' AND rel_type <> 'titleOf' THEN coalesce(tt_text, toString(t.etdId))
       WHEN 'Title' IN tl THEN t.text
       WHEN 'Author' IN tl OR 'Advisor' IN tl OR 'Department' IN tl
         OR 'University' IN tl OR 'Degree' IN tl THEN t.name
       WHEN 'Year' IN tl THEN toString(t.value)
       WHEN 'Topic' IN tl THEN t.label
       WHEN 'Figure' IN tl OR 'Table' IN tl THEN t.caption_text
       WHEN 'AbstractSentence' IN tl THEN t.sentence
       ELSE coalesce(toString(t.etdId), t.name, t.label, t.text, t.caption_text, t.sentence)
     END AS tgt_text

RETURN id(r) AS rid, rel_type, src_text, tgt_text, classified_label
LIMIT $limit;
"""


def fetch_relationships_batch(session: Session, limit: int, reembed: bool):
    rs = session.run(REL_FETCH_QUERY, limit=limit, reembed=reembed)
    return [r.data() for r in rs]


def assemble_rel_text(rel_type: str, src: str, tgt: str, label: Optional[str]) -> str:
    src = (src or "").strip()
    tgt = (tgt or "").strip()
    if rel_type in ("hasSentence", "sentenceOf") and label:
        return f"{src} {rel_type} of type {label} {tgt}".strip()
    return f"{src} {rel_type} {tgt}".strip()


def write_relationship_embeddings(tx: Transaction, rows: List[Dict[str, Any]]):
    tx.run(
        """
        UNWIND $rows AS row
        MATCH ()-[r]->() WHERE id(r) = row.id
        SET r.embedding = row.embedding,
            r.embedding_typeonly = row.embedding_typeonly
        """,
        rows=rows,
    )


def embed_all_relationships(session: Session):
    while True:
        batch = fetch_relationships_batch(session, BATCH_PULL, REEMBED)
        if not batch:
            break

        contextual_texts = [
            assemble_rel_text(b["rel_type"], b["src_text"], b["tgt_text"], b.get("classified_label"))
            for b in batch
        ]
        type_texts = [b["rel_type"] for b in batch]

        out_rows = []
        for i in range(0, len(contextual_texts), BATCH_EMBED):
            sub_ctx = contextual_texts[i:i + BATCH_EMBED]
            sub_type = type_texts[i:i + BATCH_EMBED]
            vecs_ctx = embed_texts(sub_ctx)
            vecs_type = embed_texts(sub_type)
            for k in range(len(vecs_ctx)):
                rid = batch[i + k]["rid"]
                out_rows.append({
                    "id": rid,
                    "embedding": vecs_ctx[k],
                    "embedding_typeonly": vecs_type[k],
                })

        session.execute_write(write_relationship_embeddings, out_rows)


# =========================
# Sample query helpers
# =========================
def query_node_index(session: Session, index_name: str, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    vec = embed_texts([query_text])[0]
    rs = session.run(
        """
        CALL db.index.vector.queryNodes($index_name, $top_k, $vec)
        YIELD node, score
        RETURN labels(node) AS labels, node AS n, score
        ORDER BY score DESC
        """,
        index_name=index_name, top_k=top_k, vec=vec,
    )
    return [r.data() for r in rs]


def query_relationship_index(session: Session, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    vec = embed_texts([query_text])[0]
    rs = session.run(
        """
        CALL db.index.vector.queryRelationships($idx, $top_k, $vec)
        YIELD relationship, score
        RETURN type(relationship) AS type, relationship AS r, score, id(relationship) AS rid
        ORDER BY score DESC
        """,
        idx="hasSentence_context_vector_index", top_k=top_k, vec=vec,
    )
    return [r.data() for r in rs]


def query_relationship_typeonly_index(session: Session, query_text: str, top_k: int = 5):
    vec = embed_texts([query_text])[0]
    rs = session.run(
        """
        CALL db.index.vector.queryRelationships($idx, $top_k, $vec)
        YIELD relationship, score
        RETURN type(relationship) AS type, relationship AS r, score
        ORDER BY score DESC
        """,
        idx="hasSentence_vector_index", top_k=top_k, vec=vec,
    )
    return [r.data() for r in rs]

# =========================
# MAIN
# =========================
import neo4j
from neo4j_graphrag.retrievers import HybridCypherRetriever
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
def main():

    with driver.session() as session:
        # embed_all_nodes(session)
        # print(" All node embeddings created successfully.")
        # embed_all_relationships(session)
        # create_all_vector_indexes(session)
        # print(" All embeddings and indexes created successfully.")
        # # 4) (Optional) quick sanity checks
        # examples = [
        #     ("titleEmbeddingIndex", "virtual reality classroom analytics"),
        #     ("abstractSentenceEmbeddingIndex", "what are the key findings on gesture recognition?"),
        #     ("figureEmbeddingIndex", "diagram of convolutional neural network architecture"),
        # ]
        # for idx, q in examples:
        #     rows = query_node_index(session, idx, q, 3)
        #     print(f"\nTop from node index '{idx}' for: {q!r}")
        #     for r in rows:
        #         print("  ", r["labels"], r["score"], dict(r["n"]) | {"embedding": "...truncated..."})

        # rel_rows = query_relationship_index(session, "machine learning", 3)
        # print("\nTop from relationship index (contextual):")
        # for r in rel_rows:
            # rr = dict(r["r"])
            # rr.pop("embedding", None); rr.pop("embedding_fwd", None); rr.pop("embedding_rev", None); rr.pop("embedding_typeonly", None)
            # print("  ", r["type"], f"{r['score']:.4f}", rr)
            # rel = r["r"]  # the relationship object
            # rel_id = rel.id
            # print(r)

        # rel_rows_type = query_relationship_typeonly_index(session, "machine learning", 3)
        # print("\nTop from relationship index (type-only):")
        # for r in rel_rows_type:
            # rr = dict(r["r"])
            # rr.pop("embedding", None); rr.pop("embedding_fwd", None); rr.pop("embedding_rev", None); rr.pop("embedding_typeonly", None)
            # print("  ", r["type"], f"{r['score']:.4f}", rr)
            # print(r)
        
        # 5) (Optional) example hybrid cypher retriever usage

        retrieval_query = "MATCH (node)-[:titleOf]->(e:ETD)" "RETURN e.etdId, node.text"
        embedder = OpenAIEmbeddings(model="text-embedding-ada-002", api_key=api_key_oai)
        retriever = HybridCypherRetriever(
            driver, "titleEmbeddingIndex", "titleSearch", retrieval_query, embedder
        )
        results = retriever.search(query_text="Find me a document on machine learning", top_k=5)
        for r in results:
            print(r)


if __name__ == "__main__":
    main()

        


