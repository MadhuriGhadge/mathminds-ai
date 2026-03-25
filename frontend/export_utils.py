import re
import requests
import io
import logging

logger = logging.getLogger(__name__)

def generate_latex(markdown_text: str) -> str:
    """Converts basic markdown with MathJax into a raw LaTeX document string."""
    tex = markdown_text
    
    # Protect math blocks temporarily so regex doesn't mess up math internals
    math_blocks = []
    def save_math(match):
        math_blocks.append(match.group(0))
        return f"__MATH_{len(math_blocks)-1}__"
        
    tex = re.sub(r'\$\$.*?\$\$', save_math, tex, flags=re.DOTALL)
    tex = re.sub(r'\$.*?\$', save_math, tex)
    
    # Markdown -> LaTeX conversions
    tex = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', tex)
    tex = re.sub(r'\*(.*?)\*', r'\\textit{\1}', tex)
    tex = re.sub(r'^### (.*)$', r'\\subsubsection*{\1}', tex, flags=re.MULTILINE)
    tex = re.sub(r'^## (.*)$', r'\\subsection*{\1}', tex, flags=re.MULTILINE)
    tex = re.sub(r'^# (.*)$', r'\\section*{\1}', tex, flags=re.MULTILINE)
    
    # Simple list handling
    tex = re.sub(r'^- (.*)$', r'\\item \1', tex, flags=re.MULTILINE)
    if "\\item" in tex:
        # Extremely naive list wrapping
        tex = re.sub(r'((\\item.*\n?)+)', r'\\begin{itemize}\n\1\\end{itemize}\n', tex)
    
    # Replace empty lines with double escape for spacing if needed
    # Actually, empty lines in LaTeX are good for paragraph breaks.
    
    # Restore math blocks
    for i, block in enumerate(math_blocks):
        tex = tex.replace(f"__MATH_{i}__", block)
        
    preamble = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath, amssymb, amsfonts}
\usepackage{geometry}
\geometry{a4paper, margin=1in}
\usepackage{hyperref}
\usepackage{xcolor}

\title{MathMinds Generated Report}
\author{MathMinds AI Assistant}
\date{\today}

\begin{document}
\maketitle

"""
    return preamble + tex + "\n\n\\end{document}"


def compile_pdf(tex_content: str) -> bytes:
    """Compiles a complete LaTeX string to a PDF using public latexonline.cc API."""
    try:
        r = requests.post(
            "https://latexonline.cc/compile",
            data={"text": tex_content},
            timeout=30
        )
        if r.status_code == 200:
            return r.content
        else:
            logger.error(f"LaTeX compile failed: {r.status_code} - {r.text[:200]}")
    except Exception as e:
        logger.error(f"LaTeX API exception: {e}")
    return b""
