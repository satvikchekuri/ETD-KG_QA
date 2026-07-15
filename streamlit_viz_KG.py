import streamlit as st
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import os

# ---- Neo4j config ----
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "ADD_YOUR_PASSWORD_HERE"  # Replace with your Neo4j password

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run_query(etd_ids):
    query = """
    MATCH (e:ETD)
    WHERE e.etdId IN $etd_ids
    OPTIONAL MATCH path=(e)-[*1..2]-(n)
    RETURN path
    """
    with driver.session() as session:
        result = session.run(query, etd_ids=etd_ids)
        return [record["path"] for record in result if record["path"]]

def build_graph(paths):
    net = Network(height='700px', width='100%', directed=True, bgcolor='#222222', font_color='white')
    seen_nodes, seen_edges = set(), set()

    for path in paths:
        for node in path.nodes:
            node_id = str(node.element_id)
            if node_id not in seen_nodes:
                label = node.get("title") or node.get("name") or list(node.labels)[0]
                tooltip = "<br>".join(f"{k}: {v}" for k, v in dict(node).items())
                net.add_node(node_id, label=label, title=tooltip)
                seen_nodes.add(node_id)

        for rel in path.relationships:
            src = str(rel.start_node.element_id)
            tgt = str(rel.end_node.element_id)
            edge_id = f"{src}-{tgt}-{rel.type}"
            if edge_id not in seen_edges:
                tooltip = "<br>".join(f"{k}: {v}" for k, v in dict(rel).items())
                net.add_edge(src, tgt, label=rel.type, title=tooltip)
                seen_edges.add(edge_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        tmp_path = tmp.name
    net.show(tmp_path)
    return tmp_path

# ---- Streamlit UI ----
st.title(" ETD Knowledge Graph Visualizer")

etd_input = st.text_input("Enter comma-separated ETD IDs:", "etd1,etd2,etd3")

if st.button("Generate Graph"):
    # [eid.strip() for eid in etd_input.split(",") if eid.strip()]
    etd_ids = [str(x).strip().strip('"').strip("'") for x in etd_input.split(",") if x.strip()]
    if etd_ids:
        with st.spinner("Querying Neo4j and generating graph..."):
            paths = run_query(etd_ids)
            if not paths:
                st.warning("No results found for the given ETD IDs.")
            else:
                html_file = build_graph(paths)
                components.html(open(html_file, 'r', encoding='utf-8').read(), height=750, scrolling=True)
                os.remove(html_file)
