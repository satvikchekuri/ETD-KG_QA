# Structured Knowledge Graph for Scholarly Exploration: IR and QA System for ETDs and their Elements

This repository contains the code and data for our paper, *Structured Knowledge Graph for Scholarly Exploration: IR and QA System for ETDs and their Elements*.

## Repository Structure

| File / Folder | Description |
|---|---|
| `Data/` | Dataset files for the ETD knowledge graph (see [Data](#data)). |
| `etd_dataset_analysis.py` | Exploratory analysis and statistics of the ETD dataset. |
| `neo4j_injest.py` | Ingests ETD data and constructs the knowledge graph in Neo4j. |
| `neo4j_injest_batch.py` | Batched version of the ingestion pipeline for larger datasets. |
| `neo4j_ingest_embeddings.py` | Computes and loads element/relationship embeddings into the graph. |
| `query_KG.py` | Text2Cypher retrieval — generates and runs Cypher queries from questions. |
| `query_vector_kg.py` | Vector-based retrieval over graph elements and relationships. |
| `streamlit_KG.py` | Streamlit app for the KG-based QA system. |
| `streamlit_KG_QA_Reflection.py` | QA app with the self-reflection / self-feedback module. |
| `streamlit_viz_KG.py` | Streamlit app for interactive graph visualization (PyVis). |
| `test_neo4j.py` | Connectivity and sanity tests for the Neo4j instance. |
| `environment.yml` | Conda environment specification. |
| `requirements.txt` | Python dependencies (pip). |

## Data

The `Data/` folder contains the dataset files used to build the ETD knowledge graph and also the user study results.

| `userstudy_answers.csv` | User study question and answer pairs. 8 QA pairs per department (total 4) per method (3 methods, which include 2 baselines). Total 96 QA pairs. |
| `User_Study_Results_External.xlsx` | User study results, which record participants' selections. |
| `data.tar.gz` | After unzipping, you will find below 4 files:

  | `processed_data_26k_etd_enriched.csv` | 26K ETD metadata |
  | `etd_figures.csv` | Figure captions extracted from 26K ETDs |
  | `etd_tables.csv` | Table captions extracted from 26K ETDs |
  | `26k_etd_as_classified.csv` | Abstract sentences classification label for all 26K ETDs |

## Setup

### 1. Clone the repository

### 2. Install dependencies

Using conda:
```bash
conda env create -f environment.yml
conda activate <env-name>
```

Or using pip:
```bash
pip install -r requirements.txt
```

### 3. Set up Neo4j

Install and run Neo4j 5.x (Desktop, Docker, or a local server). Then configure connection details and your OpenAI API key via environment variables:

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
export OPENAI_API_KEY="your-openai-key"
```

## Usage

### Build the knowledge graph
```bash
python neo4j_injest_batch.py            
python neo4j_ingest_embeddings.py # add embeddings for vector retrieval
```

### Run the QA system
```bash
streamlit run streamlit_KG.py
streamlit run streamlit_KG_QA_Reflection.py # added reflection feature
```

