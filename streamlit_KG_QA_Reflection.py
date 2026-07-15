from openai import OpenAI
from neo4j import GraphDatabase
import streamlit as st
from query_vector_kg import vector_neo4j_retreval
import json

# === Configuration ===
# OPENAI_API_KEY = "sk-..."  # Replace with your OpenAI key
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "ADD_YOUR_PASSWORD_HERE"  # Replace with your Neo4j password

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
def summarize_etd_results(records, question, final, df):
    # context_text = "\n".join(
    #     # f"- Title: {r.get('abstract_text') or r.get('title')}\n  Abstract: {r.get('abstract') or r.get('t.abstract_text')}" for r in records
    #     f"- Citation: {r.get('URI') or r.get('e.URI')}; Abstract: {r.get('abstract_text')}; Title: {r.get('title')}; Figure_Caption: {r.get('figure_caption')}; Table_Caption: {r.get('table_caption')}" for r in records
    # )
    context_text = "\n".join(
        f"- Citation: {r.get('URI') or r.get('e.URI')}; "
        f"Abstract: {r.get('abstract_text')}; "
        f"Title: {r.get('title')}; "
        f"Figure_Caption: {r.get('figure_caption')}; "
        f"Table_Caption: {r.get('table_caption')}"
        for r in records if isinstance(r, dict)
    )
    # Build new formatted context text
    context_text_new = "\n".join(
        f"- Citation: {r.get('URI')}; "
        f"Element Type: {(r.get('label'))}; "
        f"Text: {(r.get('text'))}; "
        f"Abstract: {r.get('abstract_text')}"
        for r in final
        if isinstance(r, dict)
    )

    
    prompt = f"""
You are a helpful assistant. A user asked the question: "{question}"

Here are ETDs retrieved from a knowledge graph along with their URIs:

{context_text}

Based on these, first evaluate the findings, rank them, and select TOP 5. Then write a concise paragraph summarizing the relevant findings for the user's question. Do not list them. Don't mention scores. Write as a coherent summary not as list.
Use citation-style references (include URI found in the context_text) to attribute claims to the correct ETD or figure/table caption.
    """
    prompt_joint = f"""
You are a helpful assistant. A user asked the question: "{question}"

ETDs are retrieved through two types of retrieval methods from a knowledge graph along with their URIs.

Based on the results from both retrieval methods, first evaluate each of them or their findings with respect to the question, rank them, and select TOP 6. For the given user's question, you will come up with an aswer based on these findings in following format: First have an answer summary of 1 sentence (upto 30 words). Then write a concise paragraph summarizing the relevant findings for the user's question (upto 187 words).
Definitely include at least one or more Figure/Table (available in element_type/figure_caption/table_caption) if not present.
Use citation-style references (include URI found in the context_text) to attribute claims to the correct ETD or figure/table caption (have [1]/[2] in text, and list them in the end).

ETDs from Text2Cypher Retrieval Method: {context_text}
ETDs from Vector Retrieval Method: {context_text_new}

    """
    # Definitely include at least one Figure/Table (available in element_type/figure_caption/table_caption) if not present and should still return ONLY 4 including the fig/table, and also add a cue like [F] or [T] as additional reference.
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt_joint}],
        temperature=1.0
    )
    return response.choices[0].message.content.strip()


import json

# === Self-Reflection / Self-Feedback Module ===
def reflect_and_revise(question, draft_answer, records, final):
    # Build the same evidence context the summarizer saw, so the critic
    # judges grounding/citations against the exact retrieved set.
    context_text = "\n".join(
        f"- Citation: {r.get('URI') or r.get('e.URI')}; "
        f"Abstract: {r.get('abstract_text')}; "
        f"Title: {r.get('title')}; "
        f"Figure_Caption: {r.get('figure_caption')}; "
        f"Table_Caption: {r.get('table_caption')}"
        for r in records if isinstance(r, dict)
    )
    context_text_new = "\n".join(
        f"- Citation: {r.get('URI')}; "
        f"Element Type: {r.get('label')}; "
        f"Text: {r.get('text')}; "
        f"Abstract: {r.get('abstract_text')}"
        for r in final if isinstance(r, dict)
    )

    # Collect the set of URIs actually present in retrieved context, so the
    # critic can flag any cited URI that isn't grounded.
    valid_uris = set()
    for r in records:
        if isinstance(r, dict):
            uri = r.get('URI') or r.get('e.URI')
            if uri:
                valid_uris.add(uri)
    for r in final:
        if isinstance(r, dict) and r.get('URI'):
            valid_uris.add(r.get('URI'))

    critique_prompt = f"""
You are a strict evaluator of an answer produced by an ETD retrieval QA system.

User question:
"{question}"

Retrieved evidence (Text2Cypher):
{context_text}

Retrieved evidence (Vector retrieval):
{context_text_new}

URIs actually present in the retrieved context:
{chr(10).join(sorted(valid_uris)) if valid_uris else "(none)"}

Draft answer to evaluate:
\"\"\"{draft_answer}\"\"\"

Evaluate the draft answer on three dimensions:
1. GROUNDING — Is every claim supported by the retrieved evidence above? Flag any claim not traceable to the evidence.
2. COMPLETENESS — Does the answer fully address the user's question, including at least one figure/table reference where relevant?
3. CITATION_CORRECTNESS — Are all cited URIs present in the list of URIs above? Flag any citation that does not appear there.

Respond ONLY with a JSON object, no markdown, in this exact shape:
{{
  "grounding": {{"pass": true/false, "issues": "brief description or empty string"}},
  "completeness": {{"pass": true/false, "issues": "brief description or empty string"}},
  "citation_correctness": {{"pass": true/false, "issues": "brief description or empty string"}},
  "needs_revision": true/false
}}
"""

    critique_resp = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": critique_prompt}],
        temperature=0.2
    )
    raw = critique_resp.choices[0].message.content.strip()
    # Strip accidental code fences before parsing.
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        critique = json.loads(raw)
    except json.JSONDecodeError:
        # If the critic returns malformed JSON, fail safe: keep the draft.
        return draft_answer, {"error": "Could not parse critique", "raw": raw}

    if not critique.get("needs_revision", False):
        return draft_answer, critique

    # Assemble a targeted list of only the failing dimensions.
    issues = []
    for dim in ("grounding", "completeness", "citation_correctness"):
        d = critique.get(dim, {})
        if not d.get("pass", True) and d.get("issues"):
            issues.append(f"- {dim}: {d['issues']}")
    issues_text = "\n".join(issues) if issues else "- General quality issues."

    revision_prompt = f"""
You are revising an answer for an ETD QA system so it is fully grounded, complete, and correctly cited.

User question: "{question}"

Retrieved evidence (Text2Cypher):
{context_text}

Retrieved evidence (Vector retrieval):
{context_text_new}

Only these URIs may be cited:
{chr(10).join(sorted(valid_uris)) if valid_uris else "(none)"}

Original answer:
\"\"\"{draft_answer}\"\"\"

The following problems were found and must be fixed:
{issues_text}

Rewrite the answer. Keep the original format: one sentence answer summary (up to 30 words), then a concise paragraph (up to 187 words). Include at least one Figure/Table reference. Use citation-style references [1]/[2] in text and list the URIs at the end. Only cite URIs from the allowed list above. Remove or correct any unsupported claim or invalid citation.
"""

    revision_resp = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": revision_prompt}],
        temperature=1.0
    )
    revised = revision_resp.choices[0].message.content.strip()
    return revised, critique

# Include atleast one Figure/Table (available in element_type/figure_caption/table_caption) if not present and should still return ONLY 5 including the fig/table, and also add a cue like [F] or [T] as additional reference. 
# Then write a concise paragraph summarizing the relevant findings for the user's question. Do not list them. Don't mention scores. Write as a coherent summary not as list.
#  Try to limit upto 220 words.
# === Streamlit App ===
st.title("ETD Knowledge Graph QA")

question = st.text_input("Ask a question about ETDs (e.g., machine learning in fisheries):")
if question:
    with st.spinner("Generating Cypher query..."):
        cypher_query = generate_cypher_from_question(question)
        cypher_query1 = generate_cypher_from_question1(question)
        cypher_query2 = generate_cypher_from_question2(question)

    st.subheader("🔎 Generated Cypher")
    st.code(cypher_query1, language="cypher")

    with st.spinner("Querying Neo4j..."):
        records = run_cypher_query(cypher_query1, limit=5)
        st.write(records)
        records += run_cypher_query(cypher_query2, limit=5)
        

    if not records:
        records = run_cypher_query(cypher_query, limit=5)
        if not records:
            st.warning("No results found.")
    else:
        st.subheader(" Top Results for Text2Cypher retrieval")
        # for i, r in enumerate(records, 1):
        #     print(f"{i}. URI: {r.get('URI') or r.get('e.URI')}; Title: {r.get('text') or r.get('title')}; Figure_Caption: {r.get('figure_caption')}; Table_Caption: {r.get('table_caption')}")
        output_lines = [
            f"Citation: {r.get('URI') or r.get('e.URI')}; "
            # f"Abstract: {r.get('abstract_text')}; "
            f"Title: {r.get('title')}; "
            f"Figure_Caption: {r.get('figure_caption')}; "
            f"Table_Caption: {r.get('table_caption')}"
            for r in records
        ]
        print_top = "\n".join(output_lines)
        st.write(print_top)
      
    
        # for i, r in enumerate(records, 1):
        #     citation = r.get('e.URI')
            # print(f"{i}. URI: {r.get('URI') or r.get('e.URI')}; Title: {r.get('abstract_text') or r.get('title')}")
            # st.markdown(f"**[{i}]** `{citation}` — {r.get('abstract_text', '')}...")

        with st.spinner("Adding results from node and edge vector retrievals..."):
            final, df = vector_neo4j_retreval(question)
                # for r in final:
            #     print(f"[{r['label']}] {r.get('text', '')[:150]}... "
            #           f"(MMR={r['mmr_score']:.3f}, Weighted={r['weighted_final_score']:.3f})")

            st.subheader("Top Results for Element/Relationship vector retrieval...")
            st.write(df[["etd_id", "node_id", "label", "text", "URI", "abstract_text","score", "mmr_score", "weighted_mmr_score"]])


        with st.spinner("Summarizing..."):
            summary = summarize_etd_results(question, records, final, df)
        
        with st.spinner("Reflecting on answer quality..."):
            summary, critique = reflect_and_revise(question, summary, records, final)

        st.subheader("Summary with Citations")
        st.write(summary)

        with st.expander("Self-reflection report"):
            st.json(critique)

# # === Step 4: Orchestrator ===
# def query_etd_kg(question):
#     print(f"\n User question: {question}")
    
#     cypher_query = generate_cypher_from_question(question)
#     print(f"\n Generated Cypher:\n{cypher_query}")

#     try:
#         records = run_cypher_query(cypher_query, limit=5)

#         if not records:
#             print("\n No results found.")
#             return

#         print("\n Context (Top 5 ETDs):")
#         for i, r in enumerate(records, 1):
#             print(f"{i}. URI: {r.get('URI') or r.get('e.URI')}; Title: {r.get('abstract_text') or r.get('title')}")
#             # print(f"   Abstract: {r.get('abstract') or r.get('t.abstract_text')[:150]}...\n")

#         summary = summarize_etd_results(records, question)
#         print(f"\n Answer Summary:\n{summary}")

#     except Exception as e:
#         print(f"\n Error running Cypher:\n{e}")


# # === Example Run ===
# if __name__ == "__main__":
#     user_question = "What are some ETD figure captions related to machine learning?" #What are some ETDs related to machine learning?
#     query_etd_kg(user_question)
