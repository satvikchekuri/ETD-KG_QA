import os
from openai import OpenAI
from neo4j import GraphDatabase

# === CONFIGURATION ===
client = OpenAI(api_key="ADD_YOUR_KEY_HERE")  # or set directly
EMBEDDING_MODEL = "text-embedding-ada-002" #"text-embedding-3-large" #"text-embedding-ada-002"  # dim=1536 

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "ADD_YOUR_PASSWORD_HERE"  # Replace with your Neo4j password
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# === 1. EMBEDDING FUNCTION ===
def get_embedding(text: str) -> list:
    text = text.replace("\n", " ").strip()
    response = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return response.data[0].embedding


# === 2. STORE EMBEDDINGS ===
def embed_nodes(tx):
    query = """
    MATCH (n)
    WHERE n.movie_title IS NOT NULL OR n.person_name IS NOT NULL
    RETURN id(n) AS id, n
    """
    for record in tx.run(query):
        node_id = record["id"]
        node = record["n"]
        text = " ".join(str(v) for v in node.values())
        embedding = get_embedding(text)
        tx.run("MATCH (n) WHERE id(n) = $id SET n.embedding = $embedding", id=node_id, embedding=embedding)


def embed_relationships(tx):
    query = """
    MATCH ()-[r]->()
    WHERE r.rel_text IS NOT NULL
    RETURN id(r) AS id, r.rel_text AS text
    """
    for record in tx.run(query):
        rel_id = record["id"]
        text = record["text"]
        embedding = get_embedding(text)
        tx.run("MATCH ()-[r]->() WHERE id(r) = $id SET r.embedding = $embedding", id=rel_id, embedding=embedding)


# === 3. CREATE VECTOR INDEXES ===
def create_vector_indexes(tx):
    tx.run("""
    CREATE VECTOR INDEX movienodeEmbeddingIndex IF NOT EXISTS
    FOR (n:Movie) ON (n.embedding)
    OPTIONS { indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: "cosine"
    }}
    """)

    tx.run("""
    CREATE VECTOR INDEX movierelEmbeddingIndex IF NOT EXISTS
    FOR ()-[r:DIRECTED]-() ON (r.embedding)
    OPTIONS { indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: "cosine"
    }}
    """)


# === 4. QUERY TOP MATCHES ===
def query_top_matches(query_text, top_k=5):
    embedding = get_embedding(query_text)

    with driver.session() as session:
        print(f"\n Query: \"{query_text}\"")

        # Top node matches
        print("\nTop Node Matches:")
        results = session.run("""
            CALL db.index.vector.queryNodes('movienodeEmbeddingIndex', $top_k, $embedding)
            YIELD node, score
            RETURN labels(node) AS labels, node, score
            ORDER BY score DESC
        """, embedding=embedding, top_k=top_k)

        for record in results:
            # print(record['labels'], record['movie_id'], record['movie_title'], record['score'])
            print(f"[{record['labels']}] {dict(record['node'])}  (score: {record['score']:.4f})")
        

        # Top relationship matches
        print("\nTop Relationship Matches:")
        results = session.run("""
            CALL db.index.vector.queryRelationships('movierelEmbeddingIndex', $top_k, $embedding)
            YIELD relationship, score
            RETURN type(relationship) AS rel_type, relationship, score
            ORDER BY score DESC
        """, embedding=embedding, top_k=top_k)

        for record in results:
            print(f"[{record['rel_type']}] {dict(record['relationship'])}  (score: {record['score']:.4f})")


# === 5. MAIN ENTRYPOINT ===
def main():
    # with driver.session() as session:
    #     print(" Creating vector indexes...")
    #     session.execute_write(create_vector_indexes)

    #     print(" Embedding nodes...")
    #     session.execute_write(embed_nodes)

    #     print(" Embedding relationships...")
    #     session.execute_write(embed_relationships)

    query_top_matches("Who directed Inception?")
    query_top_matches("Give me reviews of The Dark Knight.")


if __name__ == "__main__":
    main()
