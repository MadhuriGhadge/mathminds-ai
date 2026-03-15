

## Project Objective

The goal of MathMinds AI is to build a system that can:
- Interpret handwritten equations from images
- Understand natural language word problems
- Analyze charts or probability/statistics images
- Retrieve helpful information using semantic search
- Produce explainable step-by-step solutions

All of this is exposed through an interactive web interface powered by Python.

## Demo

**HuggingFace Space**: [https://huggingface.co/spaces/ghadgemadhuri92/mathstutor](https://huggingface.co/spaces/ghadgemadhuri92/mathstutor)

## Key Features

### 1. Handwritten Equation Recognition
Users can upload an image of handwritten mathematics.

**Pipeline**: Image → OCR → Symbol Parsing → Math Expression → Solver

**Technologies involved**:
- TrOCR / OCR pipeline
- Expression parser
- SymPy symbolic solver

### 2. Word Problem Understanding
MathMinds AI can analyze natural language math questions such as:
"A train travels 60 km/h for 2.5 hours. How far does it go?"

**The system**:
- Interprets the problem using LLMs
- Extracts numerical relationships
- Generates a mathematical representation
- Solves using SymPy


### 3. Image-Based Probability & Statistics Analysis
The system can analyze:
- charts
- tables
- probability diagrams
- statistics graphs

Using image analysis capabilities of gemini, it extracts relevant information and answers questions related to the image.

### 4. Explainable Solutions
MathMinds AI emphasizes explainability.
Instead of only returning a result, the system generates:
- step-by-step derivations
- symbolic transformations
- intermediate reasoning

### 5. Semantic Retrieval with Embeddings
The system uses vector embeddings to retrieve relevant:
- formulas
- solved examples
- reference explanations

This improves the accuracy of complex problems.

## System Architecture

```text
                User
                 │
                 ▼
           Streamlit UI
                 │
                 ▼
              FastAPI
                 │
   ┌─────────────┼─────────────┐
   ▼             ▼             ▼
 OCR Engine   LLM Pipeline   Image Analysis
   │             │             │
   ▼             ▼             ▼
 Expression   Problem        Feature
 Parsing      Understanding  Extraction
   │             │             │
   └─────────────▼─────────────┘
                Solver
               (SymPy)
                 │
                 ▼
             Response
```

## Tech Stack

**Backend**
- Python 3.10+
- FastAPI

**Frontend**
- Streamlit

**AI / ML**
- SymPy (symbolic math solving)
- TrOCR (handwritten text recognition)
- YOLO (image object detection)
- LLM APIs for reasoning and parsing

**Data & Storage**
- MongoDB (session state and logs)
- Vector embeddings layer
- Supabase (vector storage / retrieval)

**Dev Tools**
- Git
- Docker

## Project Structure
Example simplified structure:
```text
MathMinds-AI
│
├── backend
│   ├── api
│   │   ├── routes
│   │   └── services
│   │
│   ├── ocr
│   │   ├── image_preprocessing.py
│   │   └── trocr_pipeline.py
│   │
│   ├── solver
│   │   ├── sympy_solver.py
│   │   └── expression_parser.py
│   │
│   ├── image_analysis
│   │   └── yolo_detection.py
│   │
│   └── retrieval
│       └── embeddings_search.py
│
├── frontend
│   └── streamlit_app.py
│
├── database
│   └── mongo_client.py
│
├── experiments
│   └── research notebooks
│
├── requirements.txt
└── README.md
```

## Branch Information
This repository currently contains multiple development branches.

- **main**: Stable project documentation and baseline implementation.
- **experiment-adk**: Active development branch where experimental pipelines and new features are being tested.


## Limitations & Known Issues
MathMinds AI is still an experimental project, several limitations currently exist.

### 1. API Quota Exhaustion
Some components depend on external APIs (LLM providers).
Possible issues:
- API rate limits
- quota exhaustion
- slow response times

Mitigation strategies include caching and local models in future versions.

### 2. OCR Accuracy for Handwritten Math
Handwritten mathematical notation is extremely difficult to recognize due to:
- varied writing styles
- symbol overlap
- ambiguous characters

Current OCR pipelines may misinterpret:
- fractions
- integrals
- superscripts/subscripts

Improving symbol segmentation is an ongoing area of work.

### 3. YOLO Model Instability
The YOLO-based image analysis module for charts and probability diagrams still faces challenges:
- false detections
- poor performance on complex diagrams
- inconsistent bounding boxes

Model retraining and dataset improvements are planned.

### 4. High Sensitivity to Input Quality
The system performs best when:
- images are clear
- handwriting is legible
- problem statements are structured

Low quality images or ambiguous wording may produce incorrect results.

### 5. Incomplete Reasoning Pipelines
Some reasoning tasks still depend heavily on LLM prompting.
This means:
- occasional hallucinations
- inconsistent solution steps
- failure on very complex problems

Planned improvements include:
- Better handwritten math recognition
- Custom-trained symbol segmentation model
- Improved YOLO training dataset
- Local LLM integration
- Advanced symbolic reasoning pipelines
- Interactive solution visualization
