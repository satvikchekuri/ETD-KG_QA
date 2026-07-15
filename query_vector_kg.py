from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorCypherRetriever
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j_graphrag.retrievers.base import RetrieverResultItem
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pandas as pd
import neo4j


def vector_neo4j_retreval(user_query: str):
# ==== CONFIG ====
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "ADD_YOUR_PASSWORD_HERE"  # Replace with your actual password
    OPENAI_KEY = "ADD_YOUR_KEY_HERE"  # Replace with your OpenAI key
    EMBEDDING_MODEL = "text-embedding-ada-002"
    MODEL_DIMS = 1536

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    client = OpenAI(api_key=OPENAI_KEY)

    embedder = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=OPENAI_KEY)

    # ==== Embedding Function ====
    def get_embedding(text: str):
        text = text.replace("\n", " ")
        resp = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return resp.data[0].embedding


    # ==== Result Formatter ====
    def result_formatter(record: neo4j.Record) -> RetrieverResultItem:
        metadata = {
            "node_id": record.get("node_id"),
            "label": record.get("label"),
            "score": record.get("score"),
            "etd_id": record.get("etd_id"),
            "URI": record.get("URI"),
            "text": record.get("text"),
            "classified_label": record.get("classified_label"),
            "abstract_text": record.get("abstract_text"),
            "embedding": record.get("embedding"),
            "topic_label": record.get("topic_label"),
        }
        return RetrieverResultItem(content=str(metadata), metadata=metadata)


    # ==== Cypher Queries per Node ====
    RETRIEVAL_QUERIES = {
        "title": """
            OPTIONAL MATCH (node)-[:titleOf]->(etd:ETD)
            RETURN id(node) AS node_id, labels(node)[0] AS label, score,
                etd.etdId AS etd_id, etd.URI AS URI,
                node.text AS text, node.embedding AS embedding, node.abstract_text AS abstract_text,
                NULL AS classified_label
        """,
        "abstractSentence": """
            MATCH (node)<-[:hasSentence]-(etd:ETD)
            OPTIONAL MATCH (etd)-[:hasTitle]->(t:Title)
            RETURN id(node) AS node_id, labels(node)[0] AS label, score,
                etd.etdId AS etd_id, etd.URI AS URI,
                node.sentence AS text, node.classified_label AS classified_label,
                node.embedding AS embedding, t.abstract_text AS abstract_text
        """,
        "figure": """
            MATCH (node)<-[:hasFigure]-(etd:ETD)
            WHERE node.caption_text IS NOT NULL
                AND trim(node.caption_text) <> ""
            RETURN id(node) AS node_id, labels(node)[0] AS label, score,
                etd.etdId AS etd_id, etd.URI AS URI,
                node.caption_text AS text, node.embedding AS embedding,
                NULL AS classified_label
        """,
        "table": """
            MATCH (node)<-[:hasTable]-(etd:ETD)
            WHERE node.caption_text IS NOT NULL
                AND trim(node.caption_text) <> ""
            RETURN id(node) AS node_id, labels(node)[0] AS label, score,
                etd.etdId AS etd_id, etd.URI AS URI,
                node.caption_text AS text, node.embedding AS embedding,
                NULL AS classified_label
        """,
        "topic": """
            RETURN id(node) AS node_id, labels(node)[0] AS label,
                node.label AS topic_label, node.embedding AS embedding,
                NULL AS classified_label, NULL AS score,
                NULL AS etd_id, NULL AS url, NULL AS text
        """
    }

    INDEX_MAP = {
        "title": "titleEmbeddingIndex",
        "abstractSentence": "abstractSentenceEmbeddingIndex",
        "topic": "topicEmbeddingIndex",
        "figure": "figureEmbeddingIndex",
        "table": "tableEmbeddingIndex"
    }

    INDEX_MAP_CAPTION = {
        "figure": "figureEmbeddingIndex",
        "table": "tableEmbeddingIndex"
    }

    TOP_K = {
        "title": 10,
        "abstractSentence": 75,
        "figure": 300,
        "table": 300,
        "topic": 1
    }

    NODE_WEIGHTS = {
        "title": 2.0,
        "abstractsentence": 2.0,
        "figure": 3.0,
        "table": 3.0,
        "topic": 1.0
    }


    # ==== Vector Retrieval ====
    def run_vector_cypher_retrieval(user_query: str):
        all_items = []
        query_emb = get_embedding(user_query)

        for node_type in INDEX_MAP:
            retriever = VectorCypherRetriever(
                driver=driver,
                index_name=INDEX_MAP[node_type],
                retrieval_query=RETRIEVAL_QUERIES[node_type],
                result_formatter=result_formatter,
                embedder=embedder
            )
            print(f">>> Retrieving from index: {node_type}")
            results = retriever.search(query_text=user_query, top_k=TOP_K[node_type])
            items = results.items

            # 1) Expand topic into top ETDs using Cypher
            if node_type == "topic" and items:
                topic_label = items[0].metadata.get("topic_label")
                with driver.session() as session:
                    cypher = """
                        MATCH (etd:ETD)-[:hasTopic]->(:Topic {label: $topic})
                        WITH collect(id(etd)) AS etd_ids
                        CALL db.index.vector.queryNodes('titleEmbeddingIndex', 1000, $embedding)
                        YIELD node, score
                        MATCH (etd:ETD)-[:hasTitle]->(node)
                        WHERE id(etd) IN etd_ids
                        RETURN etd.etdId AS etd_id,
                            etd.URI AS URI,
                            node.text AS text,
                            node.abstract_text AS abstract_text,
                            score,
                            id(node) AS node_id,
                            labels(node)[0] AS label,
                            node.embedding AS embedding,
                            NULL AS classified_label
                        ORDER BY score DESC
                        LIMIT 5;
                    """
                    topic_etds = session.run(cypher, embedding=query_emb, topic=topic_label).data()
                    for row in topic_etds:
                        all_items.append({
                            **row,
                            "label": row.get("label", "").lower()
                        })
                    
                continue
            
            for item in items:
                all_items.append({
                    **item.metadata,
                    "label": item.metadata["label"].lower()
                })
            
        # 2) Collect ETD IDs from Title, AbstractSentence, and Topic
        etd_ids = {
            r["etd_id"]
            for r in all_items
            if r.get("label") in ["title", "abstractsentence", "topic"] and r.get("etd_id")
        }   
        if not etd_ids:
            print(" No ETD IDs found for figure/table stage.")
            return all_items

        print(f"Found {len(etd_ids)} ETDs for figure/table retrieval.")

        # 3) Second-stage: Figures and Tables retrieval (like Topic ETDs)
        with driver.session() as session:
            for node_type, rel_type in [("figure", "hasFigure"), ("table", "hasTable")]:
                print(f">>> Second-stage retrieval for {node_type}s ...")
                # CALL db.index.vector.queryNodes('{INDEX_MAP_CAPTION[node_type]}', $top_k, $embedding)
                # YIELD node, score
                cypher = f"""
                    MATCH (node)<-[r:{rel_type}]-(etd:ETD)
                    WHERE etd.etdId IN $etd_ids
                        AND node.caption_text IS NOT NULL
                        AND trim(node.caption_text) <> ""
                    RETURN etd.etdId AS etd_id,
                        etd.URI AS URI,
                        node.caption_text AS text,
                        id(node) AS node_id,
                        labels(node)[0] AS label,
                        node.embedding AS embedding,
                        NULL AS classified_label
                """

                data = session.run(
                    cypher,
                    top_k=TOP_K.get(node_type,50),
                    embedding=query_emb,
                    etd_ids=list(etd_ids)
                ).data()
                print(f"  Retrieved {len(data)} {node_type} captions.")
                for row in data:
                    all_items.append({**row, "label": row.get("label", "").lower()})
            
        for r in all_items:
            node_type = r.get("label", "").lower()
            wt = NODE_WEIGHTS.get(node_type, 1.0)
            r["weighted_score"] = r.get("score", 0) * wt

        return all_items


    # ==== MMR + Weights ====
    def apply_mmr_and_weights(user_query: str, results):
        query_emb = get_embedding(user_query)
        doc_embs = np.array([r["embedding"] for r in results])

        query_sim = cosine_similarity(doc_embs, [query_emb]).flatten()
        weights = np.array([NODE_WEIGHTS.get(r["label"], 1.0) for r in results])
        query_sim *= weights   

        top_idxs = mmr(doc_embs, query_emb, query_sim, lambda_param=0.7, top_n=15)

        final = []
        for i in top_idxs:
            r = results[i]
            r["mmr_score"] = float(cosine_similarity([r["embedding"]], [query_emb])[0][0])
            r["weighted_mmr_score"] = r["mmr_score"] * NODE_WEIGHTS.get(r["label"], 1.0)
            final.append(r)

        final = sorted(final, key=lambda x: x["weighted_mmr_score"], reverse=True)
        return final, pd.DataFrame(final)


    # ==== MMR Algorithm ====
    def mmr(doc_embeddings, query_embedding, query_sim, lambda_param=1,top_n=5):
        doc_sim = cosine_similarity(doc_embeddings)
        # query_sim = cosine_similarity(doc_embeddings, [query_embedding]).flatten()
        selected, remaining = [], list(range(len(doc_embeddings)))
        while remaining and len(selected) < top_n:
            if not selected:
                idx = np.argmax(query_sim)
                selected.append(idx)
                remaining.remove(idx)
                continue
            mmr_scores = [
                (i, lambda_param * query_sim[i] - (1 - lambda_param) * max(doc_sim[i][j] for j in selected))
                for i in remaining
            ]
            idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected.append(idx)
            remaining.remove(idx)
        return selected
    

    print("\n=== Vector Retrieval ===")
    results = run_vector_cypher_retrieval(user_query)
    print(f"Retrieved {len(results)} nodes.")

    print("\n=== MMR + Weights ===")
    final, df = apply_mmr_and_weights(user_query, results)
    return final, df


# ==== Driver ====
if __name__ == "__main__":
    query = "What types of 3D interaction techniques have been explored to help users perform better in virtual or augmented reality environments?"
    # print("\n=== Vector Retrieval ===")
    # results = run_vector_cypher_retrieval(query)
    # print(f"Retrieved {len(results)} nodes.")

    # print("\n=== MMR + Weights ===")
    final, df = vector_neo4j_retreval(query)

    for r in final:
        print(f"[{r['label']}] {r.get('text', '')[:150]}... "
              f"(MMR={r['mmr_score']:.3f}, Weighted={r['weighted_mmr_score']:.3f})")

    print("\n=== DataFrame Preview ===")
    # print(df[["etd_id", "label", "node_id", "text", "classified_label", "score", "mmr_score", "weighted_final_score", "URI", "abstract_text"]])
    print(df[["etd_id", "label",  "text",  "score", "weighted_score", "mmr_score", "weighted_mmr_score"]])
    # print(df.columns)
