from openai import OpenAI
from neo4j import GraphDatabase


# === Configuration ===
# OPENAI_API_KEY = "sk-..."  # Replace with your OpenAI key
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "ADD_YOUR_PASSWORD_HERE"  # Replace with your actual password

client = OpenAI(api_key="ADD_YOUR_KEY_HERE")  # Replace with your OpenAI key

neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# === Step 1: Generate Cypher Query from Natural Language ===
def generate_cypher_from_question(natural_question):
    prompt = f"""
You are a Cypher expert. Given a user's question and the structure of a knowledge graph about Electronic Theses and Dissertations (ETDs), write a Cypher query compatible with Neo4j 5.x.

ETD has:
- title in (title:Title (title.text, title.abstract_text))
- figure (figure_caption), table captions (table_caption) and abstract sentences
- topic, department, degree, author, advisor, year

The graph contains relationships like:
(:ETD)-[:hasTitle]->(:Title)
(:ETD)-[:hasFigure]->(:Figure)
(:ETD)-[:hasSentence]->(:AbstractSentence)
(:ETD)-[:hasTopic]->(:Topic)
(:ETD)-[:hasAuthor]->(:Author)

Example cypher query with correct syntax:
MATCH (e)-[:hasTitle]->(t:Title)
WHERE t.text CONTAINS 'machine learning' OR t.abstract_text CONTAINS 'machine learning'
MATCH (e:ETD)-[:hasFigure]->(f:Figure)
WHERE f.caption_text CONTAINS 'machine learning'
MATCH (e:ETD)-[:hasTable]->(t:Table
WHERE t.caption_text CONTAINS 'machine learning'
OPTIONAL MATCH (e)-[:issuedYear]->(y:Year)
RETURN e, e.URI, t.text as text, t.abstract_text AS abstract_text, f.caption_text as figure_caption,f.figure_page_no, t.caption_text as table_caption, t.table_page_no, y.value AS year
ORDER BY y.value DESC
LIMIT 5

MATCH (e:ETD)-[:hasTitle]->(t)
OPTIONAL MATCH (e)-[:hasFigure]->(f:Figure)
WHERE toLower(f.caption_text) CONTAINS toLower("high-fidelity virtual environments")

OPTIONAL MATCH (e)-[:hasTable]->(tb:Table)
WHERE toLower(tb.caption_text) CONTAINS toLower("high-fidelity virtual environments")

OPTIONAL MATCH (e)-[:issuedYear]->(y:Year)

WHERE toLower(t.abstract_text) CONTAINS toLower("high-fidelity virtual environments")

RETURN e, e.URI, t.text AS title, t.abstract_text AS abstract_text, f.caption_text AS figure_caption, tb.caption_text AS table_caption, y.value AS year, score
ORDER BY score DESC, y.value DESC
LIMIT 5

Example of figure caption:
MATCH (e:ETD)
        MERGE (e)-[:hasFigure]->(f)
        MERGE (f)-[:figureOf]->(e)

The question is:
\"\"\"{natural_question}\"\"\"

Return only the Cypher query (ready to run without any unecessary special characters or tags) that retrieves the top 5 most relevant ETDs (including title and abstract_text and URI).
Query should be searched over title.abstract_text or title.text (first preference) and next (using OPTIONAL) on figure.caption_text or table.caption_text, unless specified only topic or abstract. Rank results by relevance and recency.
Think and execute step by step the query with the schema provided. Make sure no mistakes are made. 
     """
    prompt_new = f"""
You are a Neo4j and Cypher expert and electronic theses and dissertations (ETDs) specialist.
Translate the user's natural-language question into a Cypher query that fits the exact ETD schema, index strategy, and scoring rules described below. Also fits Neo4J 5.x syntax.

### GRAPH SCHEMA

# NODE LABELS & PROPERTIES
- ETD: etdId, URI
- Title: title, abstract_text
- Author: name 
- Advisor: name 
- Department: name 
- University: name 
- Year: value 
- Degree: name 
- Topic: label 
- FigureCaption: etdId, figure_id, figure_path, figure_page_no, caption_page_no, figure_caption 
- TableCaption: etdId, table_id, table_path, table_page_no, caption_page_no, table_caption 
- AbstractSentence: etdId, sentence, classified_label // labels: BACKGROUND | OBJECTIVE | METHODS | RESULTS | CONCLUSIONS

# RELATIONSHIPS  ( → has …  , ← inverse )
- (ETD) -[:hasTitle]→ (t:Title)        ←[:titleOf]-
- (ETD) -[:hasAuthor]→ (a:Author)      ←[:authorOf]-
- (ETD) -[:academicAdvisor]→ (ad:Advisor) ←[:academicAdvisorOf]-
- (ETD) -[:academicDiscipline]→ (d:Department) ←[:academicDisciplineOf]-
- (ETD) -[:publishedBy]→ (u:University) ←[:hasPublished]-
- (ETD) -[:issuedYear]→ (Year)
- (ETD) -[:degreeType]→ (Degree)
- (ETD) -[:hasTopic]→ (tp:Topic)       
- (ETD) -[:hasFigure]→ (FigureCaption) ←[f:figureOf]-
- (ETD) -[:hasTable]→ (TableCaption)  ←[t:tableOf]-
- (ETD) -[:hasSentence]→ (AbstractSentence) ←[:sentenceOf]-

# INDEXED FIELDS
- ETD.etdId (e)
- Author.name (a), Advisor.name (adv), University.name (u), Department.name (d), Degree.name (dg)
- Topic.label (tp)
- AbstractSentence.sentence (s)
- FigureCaption.(etdId, figure_id) (f)
- TableCaption.(etdId, table_id) (t)

### QUERY-SELECTION & SCORING RULES

1. If user query contains “figure”, “table”, or “caption”, treat FigureCaption.table_caption / figure_caption as the PRIMARY match source (weight 1.0).
2. Otherwise, treat AbstractSentence.sentence as the PRIMARY source (weight 1.0).
3. Secondary evidence (weight 0.5): FigureCaption / TableCaption (when NOT primary).
4. Optional evidence (weight 0.3): Title.abstract_text. (not needed always unless looking at collection level)
5. Weakest evidence (weight 0.1): Topic.label. (not needed always unless looking at collection level)
6. Prefer full-text search (CONTAINS or full-text index) on the chosen fields.
7. Return both the matched node text e.URI and its direct relationship to the ETD for provenance, or relation to immediate neighbor, plus any score you compute.
8. Always LIMIT results to 5, ordered by the score you assemble.

The question is:
\"\"\"{natural_question}\"\"\"

    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()
def generate_cypher_from_question1(natural_question):
    prompt = f"""
You are a Cypher expert. Given a user's question and the structure of a knowledge graph about Electronic Theses and Dissertations (ETDs), write a Cypher query compatible with Neo4j 5.x.

ETD has:
- title in (title:Title (title.text, title.abstract_text))
- figure (figure_caption), table captions (table_caption) and abstract sentences
- topic, department, degree, author, advisor, year

The graph contains relationships like:
(:ETD)-[:hasTitle]->(:Title)
(:ETD)-[:hasFigure]->(:Figure)
(:ETD)-[:hasAuthor]->(:Author)
(:ETD)-[:hasTopic]->(:Topic)

Full Text Indexes available:
"titleSearch", "Title", "text"
"abstractSearch", "Title", "abstract_text"
"figureCaptionSearch", "Figure", "caption_text"
"tableCaptionSearch", "Table", "caption_text"

Example cypher query with correct syntax. Multiple keywords from user query text can be placed with a space in between as it is the same as OR operator. Use similar cypher structure:

CALL {{
WITH toLower("high-fidelity virtual environments augmented reality") AS query

// Title Search
CALL db.index.fulltext.queryNodes("titleSearch", query)
YIELD node, score
WITH node, score
ORDER BY score DESC
LIMIT 10
MATCH (e:ETD)-[:hasTitle]->(node)
RETURN e AS etd, node.text AS title, NULL AS abstract, NULL AS figure_caption, NULL AS figure_page_no,
       NULL AS table_caption, NULL AS table_page_no, score * 2 AS partialScore

UNION

// Abstract Search
WITH toLower("high-fidelity virtual environments augmented reality") AS query
CALL db.index.fulltext.queryNodes("abstractSearch", query)
YIELD node, score
WITH node, score
ORDER BY score DESC
LIMIT 10
MATCH (e:ETD)-[:hasTitle]->(node)
RETURN e AS etd, NULL AS title, node.abstract_text AS abstract, NULL AS figure_caption, NULL AS figure_page_no,
       NULL AS table_caption, NULL AS table_page_no, score * 3 AS partialScore

UNION

// Figure Caption Search
WITH toLower("high-fidelity virtual environments augmented reality") AS query
CALL db.index.fulltext.queryNodes("figureCaptionSearch", query)
YIELD node, score
WITH node, score
ORDER BY score DESC
LIMIT 10
MATCH (e:ETD)-[:hasFigure]->(node)
RETURN e AS etd, NULL AS title, NULL AS abstract, node.caption_text AS figure_caption, node.figure_page_no AS figure_page_no,
       NULL AS table_caption, NULL AS table_page_no, score * 1 AS partialScore

UNION

// Table Caption Search
WITH toLower("high-fidelity virtual environments augmented reality") AS query
CALL db.index.fulltext.queryNodes("tableCaptionSearch", query)
YIELD node, score
WITH node, score
ORDER BY score DESC
LIMIT 10
MATCH (e:ETD)-[:hasTable]->(node)
RETURN e AS etd, NULL AS title, NULL AS abstract, NULL AS figure_caption, NULL AS figure_page_no,
       node.caption_text AS table_caption, node.table_page_no AS table_page_no, score * 1AS partialScore
}}

WITH etd, 
     collect(DISTINCT title)[0] AS title,
     collect(DISTINCT abstract)[0] AS abstract_text,
     collect(DISTINCT figure_caption)[0] AS figure_caption,
     collect(DISTINCT figure_page_no)[0] AS figure_page_no,
     collect(DISTINCT table_caption)[0] AS table_caption,
     collect(DISTINCT table_page_no)[0] AS table_page_no,
     sum(partialScore) AS totalScore

OPTIONAL MATCH (etd)-[:issuedYear]->(y:Year)

RETURN etd.URI as URI, title, abstract_text, figure_caption, figure_page_no, table_caption, table_page_no, y.value AS year, totalScore
ORDER BY totalScore DESC, y.value DESC
LIMIT 5; 

The question is:
\"\"\"{natural_question}\"\"\"

Return only the Cypher query (ready to run without any unecessary special characters or tags. no cypher ''' etc as well) that retrieves the top 5 most relevant ETDs.
Query should be searched over title.abstract_text or title.text and next on figure.caption_text or table.caption_text, unless specified only topic or other. Rank results.
Think and execute step by step the query with the schema provided. Make sure no mistakes are made. 
     """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

def generate_cypher_from_question2(natural_question):
    prompt = f"""
You are a Cypher expert. Given a user's question and the structure of a knowledge graph about Electronic Theses and Dissertations (ETDs), write a Cypher query compatible with Neo4j 5.x.

ETD has:
- title in (title:Title (title.text, title.abstract_text))
- figure (figure_caption), table captions (table_caption) and abstract sentences
- topic, department, degree, author, advisor, year

The graph contains relationships like:
(:ETD)-[:hasTitle]->(:Title)
(:ETD)-[:hasFigure]->(:Figure)
(:ETD)-[:hasAuthor]->(:Author)
(:ETD)-[:hasTopic]->(:Topic)

Full Text Indexes available:
"titleSearch", "Title", "text"

Example cypher query with correct syntax:

CALL db.index.fulltext.queryNodes("titleSearch", "high-fidelity virtual environments augmented reality")
YIELD node AS t, score

MATCH (e:ETD)-[:hasTitle]->(t)

OPTIONAL MATCH (e)-[:hasFigure]->(f:Figure)
WHERE toLower(f.caption_text) CONTAINS toLower("high-fidelity virtual environments augmented reality")

OPTIONAL MATCH (e)-[:hasTable]->(tb:Table)
WHERE toLower(tb.caption_text) CONTAINS toLower("high-fidelity virtual environments augmented reality")

OPTIONAL MATCH (e)-[:issuedYear]->(y:Year)

WHERE toLower(t.abstract_text) CONTAINS toLower("high-fidelity virtual environments augmented reality")

RETURN e, 
       e.URI, 
       t.text AS title, 
       t.abstract_text AS abstract_text, 
       f.caption_text AS figure_caption, 
       tb.caption_text AS table_caption, 
       y.value AS year,
       score
ORDER BY score DESC, y.value DESC
LIMIT 5;

The question is:
\"\"\"{natural_question}\"\"\"

Return only the Cypher query (ready to run without any unecessary special characters or tags. no cypher ''' etc as well) that retrieves the top 5 most relevant ETDs.
Query should be searched over title.text or title.abstract_text and next on figure.caption_text or table.caption_text, unless specified only topic or other. Rank results by relevancy and recency.
Think and execute step by step the query with the schema provided. Make sure no mistakes are made. 
     """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

# === Step 2: Run Cypher Query ===
def run_cypher_query(query, limit=5):
    with neo4j_driver.session() as session:
        result = session.run(query)
        records = [record.data() for record in result]
        # return records[:limit]
        # print("records:", records)
        return records


# === Step 3: Summarize the Results as a Paragraph ===
def summarize_etd_results(records, question):
    context_text = "\n".join(
        # f"- Title: {r.get('abstract_text') or r.get('title')}\n  Abstract: {r.get('abstract') or r.get('t.abstract_text')}" for r in records
        f"- Citation: {r.get('URI') or r.get('e.URI')}; Abstract: {r.get('abstract_text')}; Title: {r.get('title')}; Figure_Caption: {r.get('figure_caption')}; Table_Caption: {r.get('table_caption')}" for r in records
    )
    
    prompt = f"""
You are a helpful assistant. A user asked the question: "{question}"

Here are ETDs retrieved from a knowledge graph along with their URIs:

{context_text}

Based on these, first evaluate the findings, rank them, and select TOP 5. Then write a concise paragraph summarizing the relevant findings for the user's question. Do not list them. Write as a coherent summary.
Use citation-style references (include URI found in the context_text) to attribute claims to the correct ETD.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()


# === Step 4: Orchestrator ===
def query_etd_kg(question):
    print(f"\n User question: {question}")
    
    cypher_query = generate_cypher_from_question(question)
    cypher_query1 = generate_cypher_from_question1(question)
    cypher_query2 = generate_cypher_from_question2(question)
    print(f"\n Generated Cypher:\n{cypher_query1}")

    try:
        records = run_cypher_query(cypher_query1, limit=5)
        records += run_cypher_query(cypher_query2, limit=5)

        if not records:
            records = run_cypher_query(cypher_query, limit=5)
            if not records:
                print("\n No results found.")
                return

        print("\n Context (Top 5 ETDs):")
        print("###############################################################")
        print(type(records[0]))
        for i, r in enumerate(records, 1):
            print(f"{i}. URI: {r.get('URI') or r.get('e.URI')}; Title: {r.get('text') or r.get('title')}; Abstract: {r.get('abstract_text')}; Figure_Caption: {r.get('figure_caption')}; Table_Caption: {r.get('table_caption')}")
            # print(f"   Abstract: {r.get('abstract') or r.get('t.abstract_text')[:150]}...\n")

        summary = summarize_etd_results(records, question)
        print(f"\n Answer Summary:\n{summary}")

    except Exception as e:
        print(f"\n Error running Cypher:\n{e}")


# === Example Run ===
if __name__ == "__main__":
    user_question = "What technology solutions have been developed to reduce digital inequity for low-resource communities? Also provide any related figures or tables?" # "What are related to machine learning?" #"What are some ETD figure captions related to machine learning?"
    query_etd_kg(user_question)
