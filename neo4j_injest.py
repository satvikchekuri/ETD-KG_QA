import pandas as pd
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "ADD_YOUR_PASSWORD_HERE"  # <-- Change this

# CSV paths
etd_csv = "processed_data_26k_etd_enriched.csv"
figures_csv = "etd_figures.csv"
tables_csv = "etd_tables.csv"
abstract_csv = "26k_etd_as_classified.csv"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def create_indexes(session):
    index_queries = [
        "CREATE INDEX IF NOT EXISTS FOR (e:ETD) ON (e.etdId)",
        # "CREATE INDEX IF NOT EXISTS FOR (a:Author) ON (a.name)",
        # "CREATE INDEX IF NOT EXISTS FOR (adv:Advisor) ON (adv.name)",
        # "CREATE INDEX IF NOT EXISTS FOR (u:University) ON (u.name)",
        # "CREATE INDEX IF NOT EXISTS FOR (d:Department) ON (d.name)",
        # "CREATE INDEX IF NOT EXISTS FOR (dg:Degree) ON (dg.name)",
        # "CREATE INDEX IF NOT EXISTS FOR (tp:Topic) ON (tp.label)",
        # "CREATE INDEX IF NOT EXISTS FOR (s:AbstractSentence) ON (s.sentence)",
        "CREATE INDEX IF NOT EXISTS FOR (f:Figure) ON (f.etdId)",
        "CREATE INDEX IF NOT EXISTS FOR (f:Figure) ON (f.figure_id)",
        "CREATE INDEX IF NOT EXISTS FOR (t:Table) ON (t.etdId)",
        "CREATE INDEX IF NOT EXISTS FOR (t:Table) ON (t.table_id)"
    ]
    for query in index_queries:
        session.run(query)

    # Create full-text indexes (if they don't exist)
    # session.run("""
    # CALL db.index.fulltext.createNodeIndex("captionSearch", ["FigureCaption", "TableCaption"], ["figure_caption", "table_caption"])
    # """)
    # session.run("""
    # CALL db.index.fulltext.createNodeIndex("abstractSearch", ["Title"], ["abstract_text"])
    # """)

    # Fulltext indexes (safe drop + create)
    def create_fulltext_index(name, label, field):
        session.run(f"DROP INDEX {name} IF EXISTS")
        session.run(f"CREATE FULLTEXT INDEX {name} FOR (n:{label}) ON EACH [n.{field}]")

    create_fulltext_index("titleSearch", "Title", "text")
    create_fulltext_index("figureCaptionSearch", "Figure", "caption_text")
    create_fulltext_index("tableCaptionSearch", "Table", "caption_text")
    create_fulltext_index("authorSearch", "Author", "name")
    create_fulltext_index("advisorSearch", "Advisor", "name")
    create_fulltext_index("departmentSearch", "Department", "name")
    create_fulltext_index("universitySearch", "University", "name")
    create_fulltext_index("degreeSearch", "Degree", "name")
    create_fulltext_index("topicSearch", "Topic", "label")
    create_fulltext_index("abstractSentenceSearch", "AbstractSentence", "sentence")
    create_fulltext_index("abstractSearch", "Title", "abstract_text")


def ingest_etds(tx, row):
    tx.run("""
        MERGE (e:ETD {etdId: $etdId})
        SET e.URI = $URI

        MERGE (t:Title {text: $title})
        SET t.abstract_text = $abstract
           
        MERGE (a:Author {name: $author})
        MERGE (d:Department {name: $department})
        MERGE (adv:Advisor {name: $advisor})
        MERGE (u:University {name: $university})
        MERGE (y:Year {value: $year})
        MERGE (dg:Degree {name: $degree})
        MERGE (tp:Topic {label: $topic})

        MERGE (e)-[:hasTitle]->(t)
        MERGE (t)-[:titleOf]->(e)
        MERGE (e)-[:hasAuthor]->(a)
        MERGE (a)-[:authorOf]->(e)
        MERGE (e)-[:academicAdvisor]->(adv)
        MERGE (adv)-[:academicAdvisorOf]->(e)
        MERGE (e)-[:publishedBy]->(u)
        MERGE (u)-[:hasPublished]->(e)
        MERGE (e)-[:issuedYear]->(y)
        MERGE (e)-[:degreeType]->(dg)
        MERGE (e)-[:academicDiscipline]->(d)
        MERGE (d)-[:academicDisciplineOf]->(e)
        MERGE (e)-[:hasTopic]->(tp)
        MERGE (tp)-[:topicOf]->(e)
    """, row)

def ingest_figures(tx, row):
    tx.run("""
        MERGE (f:Figure {
            etdId: $etdId,
            figure_id: $figure_id,
            figure_path: $figure_path,
            figure_page_no: $figure_page_no,
            caption_page_no: $caption_page_no,
            caption_text: $figure_caption
        })
        WITH f   
        MATCH (e:ETD {etdId: $etdId})
        MERGE (e)-[:hasFigure]->(f)
        MERGE (f)-[:figureOf]->(e)
    """, row)

def ingest_tables(tx, row):
    tx.run("""
        MERGE (t:Table {
            etdId: $etdId,
            table_id: $table_id,
            table_path: $table_path,
            table_page_no: $table_page_no,
            caption_page_no: $caption_page_no,
            caption_text: $table_caption
        })
        WITH t
        MATCH (e:ETD {etdId: $etdId})
        MERGE (e)-[:hasTable]->(t)
        MERGE (t)-[:tableOf]->(e)
    """, row)

def ingest_sentences(tx, row):
    tx.run("""
        MERGE (s:AbstractSentence {
            etdId: $etdId,
            sentence: $sentence,
            classified_label: $label
        })
        WITH s
        MATCH (e:ETD {etdId: $etdId})
        MERGE (e)-[:hasSentence]->(s)
        MERGE (s)-[:sentenceOf]->(e)
    """, row)

def main():
    # Load CSVs
    df_etd = pd.read_csv(etd_csv).fillna("")
    df_figures = pd.read_csv(figures_csv).fillna("")
    df_tables = pd.read_csv(tables_csv).fillna("")
    df_abstract = pd.read_csv(abstract_csv).fillna("")

    with driver.session() as session:
        create_indexes(session)

        for _, row in df_etd.iterrows():
            session.write_transaction(ingest_etds, {
                "etdId": str(row["ID"]),
                "URI": row["URI"],
                "abstract": row["abstract"],
                "author": row["author"],
                "advisor": row["advisor"],
                "department": row["department"],
                "university": row["university"],
                "year": str(row["year"]),
                "degree": row["degree"],
                "topic": row["topic_label"],
                "title": row["title"]
            })

        for _, row in df_figures.iterrows():
            session.write_transaction(ingest_figures, {
                "etdId": str(row["ID"]),
                "figure_id": row["figure_id"],
                "figure_path": row["figure_path"],
                "figure_page_no": row["figure_page_no"],
                "caption_page_no": row["caption_page_no"],
                "figure_caption": row.get("figure_caption", "")
            })

        for _, row in df_tables.iterrows():
            session.write_transaction(ingest_tables, {
                "etdId": str(row["ID"]),
                "table_id": row["table_id"],
                "table_path": row["table_path"],
                "table_page_no": row["table_page_no"],
                "caption_page_no": row["caption_page_no"],
                "table_caption": row.get("table_caption", "")
            })

        for _, row in df_abstract.iterrows():
            session.write_transaction(ingest_sentences, {
                "etdId": str(row["ID"]),
                "sentence": row["abstract_sentence"],
                "label": row["classified_label"]
            })

if __name__ == "__main__":
    main()
