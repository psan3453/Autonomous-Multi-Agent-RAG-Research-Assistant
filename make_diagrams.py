import os
import tempfile
os.environ['MPLCONFIGDIR'] = os.path.join(tempfile.gettempdir(), 'mpl_config')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_architecture_diagram(output_path):
    fig, ax = plt.subplots(figsize=(11, 7.5), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7.5)
    ax.axis('off')

    # Color Palette - Professional Academic
    c_blue = '#1f4e79'
    c_light_blue = '#e8f1f8'
    c_teal = '#007070'
    c_light_teal = '#e0f2f1'
    c_orange = '#c55a11'
    c_light_orange = '#fdf2e9'
    c_purple = '#5b2c6f'
    c_light_purple = '#f4ecf7'
    c_gray = '#4d5656'
    c_light_gray = '#f2f4f4'
    c_border = '#2c3e50'

    # Title
    ax.text(5.5, 7.15, 'System Architecture: Autonomous Multi-Agent RAG Research Assistant',
            ha='center', va='center', fontsize=14, fontweight='bold', color='#1a252f')

    # Layer 1: Scholarly Literature Ingestion Layer
    rect1 = patches.FancyBboxPatch((0.5, 5.6), 10.0, 1.25, boxstyle="round,pad=0.1,rounding_size=0.15",
                                  facecolor=c_light_blue, edgecolor=c_blue, linewidth=1.5)
    ax.add_patch(rect1)
    ax.text(0.7, 6.65, '1. Scholarly Discovery & Ingestion Layer', fontsize=11, fontweight='bold', color=c_blue)
    
    # Sub-boxes in Layer 1
    apis = [
        ('Semantic Scholar API\n(REST, x-api-key)', 1.0, 5.8, 2.6, 0.7),
        ('arXiv Export API\n(Atom XML / PDF)', 4.2, 5.8, 2.6, 0.7),
        ('OpenAlex REST API\n(Inverted Index Abstract)', 7.4, 5.8, 2.6, 0.7)
    ]
    for name, x, y, w, h in apis:
        b = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.1",
                                   facecolor='white', edgecolor='#7fb3d5', linewidth=1)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2, name, ha='center', va='center', fontsize=8.5, color='#154360', fontweight='semibold')

    # Down Arrow 1
    ax.annotate('', xy=(5.5, 5.25), xytext=(5.5, 5.6),
                arrowprops=dict(facecolor=c_blue, edgecolor='none', width=2, headwidth=7, headlength=6))

    # Layer 2: Local Document Processing & FAISS Vector Indexing Layer
    rect2 = patches.FancyBboxPatch((0.5, 3.8), 10.0, 1.35, boxstyle="round,pad=0.1,rounding_size=0.15",
                                  facecolor=c_light_teal, edgecolor=c_teal, linewidth=1.5)
    ax.add_patch(rect2)
    ax.text(0.7, 4.95, '2. Local Document Processing & Vector Storage (CPU-Optimized)', fontsize=11, fontweight='bold', color=c_teal)

    procs = [
        ('PyMuPDF (fitz) Parser\n1-Indexed Page Preservation', 0.8, 4.0, 2.8, 0.75),
        ('Recursive Token Chunking\n1000 char / 200 overlap', 4.0, 4.0, 2.8, 0.75),
        ('BGE-small-en-v1.5 + FAISS CPU\nIndexFlatIP Normalized Cosine', 7.2, 4.0, 3.0, 0.75)
    ]
    for name, x, y, w, h in procs:
        b = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.1",
                                   facecolor='white', edgecolor='#48c9b0', linewidth=1)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2, name, ha='center', va='center', fontsize=8.5, color='#0e6251', fontweight='semibold')

    # Down Arrow 2
    ax.annotate('', xy=(5.5, 3.45), xytext=(5.5, 3.8),
                arrowprops=dict(facecolor=c_teal, edgecolor='none', width=2, headwidth=7, headlength=6))

    # Layer 3: LangGraph Multi-Agent Orchestration Layer
    rect3 = patches.FancyBboxPatch((0.5, 1.8), 10.0, 1.55, boxstyle="round,pad=0.1,rounding_size=0.15",
                                  facecolor=c_light_orange, edgecolor=c_orange, linewidth=1.5)
    ax.add_patch(rect3)
    ax.text(0.7, 3.15, '3. LangGraph Multi-Agent Orchestration Layer (Stateful Cyclic Graph)', fontsize=11, fontweight='bold', color=c_orange)

    agents = [
        ('Analysis Agent\n15 Dimensions Extraction', 0.8, 2.0, 2.1, 0.95),
        ('Comparison Agent\nCross-Paper Matrix', 3.2, 2.0, 2.1, 0.95),
        ('Gap Discovery Agent\nCritical Evidence Rule', 5.6, 2.0, 2.2, 0.95),
        ('Proposal Agent\n18 Dims & Feasibility Rubric', 8.1, 2.0, 2.2, 0.95)
    ]
    for name, x, y, w, h in agents:
        b = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.1",
                                   facecolor='white', edgecolor='#e59866', linewidth=1)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2, name, ha='center', va='center', fontsize=8, color='#78281f', fontweight='semibold')

    # Inter-agent connecting arrows
    for start_x in [2.9, 5.3, 7.8]:
        ax.annotate('', xy=(start_x + 0.3, 2.48), xytext=(start_x, 2.48),
                    arrowprops=dict(arrowstyle="->", color=c_orange, lw=1.5))

    # Down Arrow 3
    ax.annotate('', xy=(5.5, 1.45), xytext=(5.5, 1.8),
                arrowprops=dict(facecolor=c_orange, edgecolor='none', width=2, headwidth=7, headlength=6))

    # Layer 4 & 5: Dual Persistence & Presentation Layer
    rect4 = patches.FancyBboxPatch((0.5, 0.3), 4.8, 1.05, boxstyle="round,pad=0.1,rounding_size=0.15",
                                  facecolor=c_light_purple, edgecolor=c_purple, linewidth=1.5)
    ax.add_patch(rect4)
    ax.text(0.7, 1.15, '4. Persistence Engine (Dual Sync)', fontsize=10, fontweight='bold', color=c_purple)
    ax.text(2.9, 0.65, 'Scoped SQLite DBMS (f"{proj}_{id}")\n+ Streamlit Session State Hydration',
            ha='center', va='center', fontsize=8.5, color='#4a235a')

    rect5 = patches.FancyBboxPatch((5.7, 0.3), 4.8, 1.05, boxstyle="round,pad=0.1,rounding_size=0.15",
                                  facecolor=c_light_gray, edgecolor=c_gray, linewidth=1.5)
    ax.add_patch(rect5)
    ax.text(5.9, 1.15, '5. Presentation & Dissemination', fontsize=10, fontweight='bold', color=c_gray)
    ax.text(8.1, 0.65, 'Interactive Streamlit UI Dashboard\n+ Publication Word Report Generator',
            ha='center', va='center', fontsize=8.5, color='#17202a')

    # Connecting bidirectional arrow between persistence and presentation
    ax.annotate('', xy=(5.65, 0.8), xytext=(5.35, 0.8),
                arrowprops=dict(arrowstyle="<->", color='#566573', lw=1.5))

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Architecture diagram saved to: {output_path}")

def draw_pipeline_diagram(output_path):
    fig, ax = plt.subplots(figsize=(11, 7.0), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7.0)
    ax.axis('off')

    # Title
    ax.text(5.5, 6.7, 'Execution Pipeline: End-to-End Multi-Agent Scientific Review Flow',
            ha='center', va='center', fontsize=13.5, fontweight='bold', color='#1a252f')

    # Step 1: Input & Discovery
    box1 = patches.FancyBboxPatch((0.4, 5.0), 3.0, 1.3, boxstyle="round,pad=0.08,rounding_size=0.12",
                                 facecolor='#ebf5fb', edgecolor='#2980b9', linewidth=1.4)
    ax.add_patch(box1)
    ax.text(1.9, 6.05, 'Step 1: Literature Discovery', ha='center', va='center', fontsize=10, fontweight='bold', color='#1b4f72')
    ax.text(1.9, 5.45, 'Query Normalization\nMulti-Provider Failover (S2/arXiv/OpenAlex)\nTop-5 Candidates Selection (Paper A & B)',
            ha='center', va='center', fontsize=7.8, color='#154360')

    # Arrow 1->2
    ax.annotate('', xy=(3.8, 5.65), xytext=(3.4, 5.65),
                arrowprops=dict(arrowstyle="->", color='#2980b9', lw=2))

    # Step 2: PDF Parsing & FAISS Vector Indexing
    box2 = patches.FancyBboxPatch((4.0, 5.0), 3.1, 1.3, boxstyle="round,pad=0.08,rounding_size=0.12",
                                 facecolor='#e8f8f5', edgecolor='#16a085', linewidth=1.4)
    ax.add_patch(box2)
    ax.text(5.55, 6.05, 'Step 2: Parsing & Indexing', ha='center', va='center', fontsize=10, fontweight='bold', color='#0e6251')
    ax.text(5.55, 5.45, 'PyMuPDF Page-by-Page DOM Parsing\n1-Indexed Page Preservation (p. X)\nBGE Embeddings + FAISS CPU Flat Index',
            ha='center', va='center', fontsize=7.8, color='#0b5345')

    # Arrow 2->3
    ax.annotate('', xy=(7.5, 5.65), xytext=(7.1, 5.65),
                arrowprops=dict(arrowstyle="->", color='#16a085', lw=2))

    # Step 3: 15-Dimension Decomposition
    box3 = patches.FancyBboxPatch((7.7, 5.0), 2.9, 1.3, boxstyle="round,pad=0.08,rounding_size=0.12",
                                 facecolor='#fef9e7', edgecolor='#f39c12', linewidth=1.4)
    ax.add_patch(box3)
    ax.text(9.15, 6.05, 'Step 3: 15-Dim Decomposition', ha='center', va='center', fontsize=10, fontweight='bold', color='#7e5109')
    ax.text(9.15, 5.45, 'Analysis Agent per Paper\n15 Technical Dimensions Extracted\nStrict Pydantic JSON Schema Enforced',
            ha='center', va='center', fontsize=7.8, color='#784212')

    # Down Arrow from Step 3 to Step 4
    ax.annotate('', xy=(9.15, 4.3), xytext=(9.15, 4.95),
                arrowprops=dict(arrowstyle="->", color='#d35400', lw=2))

    # Step 4: Comparative Matrix & Trade-off Synthesis
    box4 = patches.FancyBboxPatch((7.7, 2.7), 2.9, 1.5, boxstyle="round,pad=0.08,rounding_size=0.12",
                                 facecolor='#fbeee6', edgecolor='#e67e22', linewidth=1.4)
    ax.add_patch(box4)
    ax.text(9.15, 3.95, 'Step 4: Comparative Synthesis', ha='center', va='center', fontsize=10, fontweight='bold', color='#873600')
    ax.text(9.15, 3.25, 'Comparison Agent Alignment\nSimilarities vs Differences\nQuantitative Trade-offs\nComputational Efficiency Analysis\nExact Textual Page Citations',
            ha='center', va='center', fontsize=7.5, color='#6e2c00')

    # Left Arrow from Step 4 to Step 5
    ax.annotate('', xy=(7.2, 3.45), xytext=(7.65, 3.45),
                arrowprops=dict(arrowstyle="->", color='#e67e22', lw=2))

    # Step 5: Critical Evidence Rule & Gap Classification
    box5 = patches.FancyBboxPatch((3.8, 2.7), 3.3, 1.5, boxstyle="round,pad=0.08,rounding_size=0.12",
                                 facecolor='#fdedec', edgecolor='#c0392b', linewidth=1.4)
    ax.add_patch(box5)
    ax.text(5.45, 3.95, 'Step 5: Gap Discovery Engine', ha='center', va='center', fontsize=10, fontweight='bold', color='#78281f')
    ax.text(5.45, 3.25, '7 Mandatory Taxonomy Categories\nAlgorithmic Critical Evidence Rule:\nVERIFIED (Corroborated by Text)\nUNVERIFIED (Plausible, Uncited)\n4-Tier Scientific Impact Rating',
            ha='center', va='center', fontsize=7.5, color='#641e16')

    # Left Arrow from Step 5 to Step 6
    ax.annotate('', xy=(3.3, 3.45), xytext=(3.75, 3.45),
                arrowprops=dict(arrowstyle="->", color='#c0392b', lw=2))

    # Step 6: 18-Dimension Proposal Generation
    box6 = patches.FancyBboxPatch((0.4, 2.7), 2.8, 1.5, boxstyle="round,pad=0.08,rounding_size=0.12",
                                 facecolor='#f4ecf7', edgecolor='#8e44ad', linewidth=1.4)
    ax.add_patch(box6)
    ax.text(1.8, 3.95, 'Step 6: Idea Generation', ha='center', va='center', fontsize=10, fontweight='bold', color='#512e5f')
    ax.text(1.8, 3.25, '3 Structured Proposals\n18 Standardized Dimensions\n6-Criteria Feasibility Scoring\n[RECOMMENDED CAPSTONE]\nAutomated Target Identification',
            ha='center', va='center', fontsize=7.5, color='#4a235a')

    # Down Arrow to Final Output
    ax.annotate('', xy=(5.5, 1.9), xytext=(1.8, 2.65),
                arrowprops=dict(arrowstyle="->", connectionstyle="angle,angleA=-90,angleB=180,rad=10", color='#8e44ad', lw=2))

    # Step 7: Final Outputs
    box7 = patches.FancyBboxPatch((2.0, 0.4), 7.0, 1.3, boxstyle="round,pad=0.08,rounding_size=0.15",
                                 facecolor='#eaeded', edgecolor='#34495e', linewidth=1.5)
    ax.add_patch(box7)
    ax.text(5.5, 1.45, 'Step 7: Automated Dissemination & Dual Persistence', ha='center', va='center', fontsize=10.5, fontweight='bold', color='#1b2631')
    ax.text(5.5, 0.85, 'Dual Synchronization (Scoped SQLite + Streamlit Session State)\nPublication-Grade Word Report Generation (.docx with Complete Matrix & Proposals)\nInteractive Streamlit Research Dashboard with Evidence Badges',
            ha='center', va='center', fontsize=8, color='#2c3e50')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Pipeline diagram saved to: {output_path}")

if __name__ == '__main__':
    draw_architecture_diagram('architecture_diagram.png')
    draw_pipeline_diagram('pipeline_diagram.png')
