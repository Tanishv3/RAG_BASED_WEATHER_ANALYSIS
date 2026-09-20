"""Light / dark theme: CSS variables + styling for the app and the custom sidebar."""
PAL = {
    False: dict(bg="#f4f7fb", side="#e9f0f8", card="#ffffff", fg="#1f2933", muted="#5b6b7b",
                border="#d5dfea", input="#ffffff", primary="#2b7bba", hover="#dbe8f5"),
    True: dict(bg="#0e1117", side="#141a24", card="#1a2130", fg="#e6e9ef", muted="#9aa4b2",
               border="#2a3446", input="#202839", primary="#4da3ff", hover="#243049"),
}

CSS = """
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg)!important;color:var(--fg)}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stSidebar"],[data-testid="stSidebar"]>div{background:var(--side)!important}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp summary,.stApp th,.stApp td{color:var(--fg)}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *,[data-testid="stMetricLabel"] *{color:var(--muted)!important}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{color:var(--fg)!important}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:10px 14px}
[class*="st-key-card"]{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 12px 6px 12px}
.stApp h1{text-align:center}
.st-key-mainnav{display:flex;justify-content:center;margin:2px 0 14px 0}
.st-key-mainnav [role="radiogroup"]{gap:8px;justify-content:center;flex-wrap:wrap}
.st-key-mainnav [role="radiogroup"] label{padding:8px 20px;border:1px solid var(--border);border-radius:999px;background:var(--card);cursor:pointer}
.st-key-mainnav [role="radiogroup"] label:hover{background:var(--hover)}
.st-key-mainnav [role="radiogroup"] label:has(input:checked){background:var(--primary);border-color:var(--primary)}
.st-key-mainnav [role="radiogroup"] label:has(input:checked) *{color:#fff!important}
.st-key-mainnav [role="radiogroup"] label>div:not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])){display:none}
.brand{padding:4px 2px 10px 2px;font-size:1.15rem;color:var(--fg)}
.brand span{font-size:.8rem;color:var(--muted)}
[data-testid="stSidebar"] [role="radiogroup"]{gap:2px;flex-wrap:wrap}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:5px 10px;border-radius:8px}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:var(--hover)}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:var(--hover);font-weight:600}
[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"],input,textarea{
  background:var(--input)!important;color:var(--fg)!important;border-color:var(--border)!important}
[data-baseweb="select"] *{color:var(--fg)!important}
[data-baseweb="select"] svg{fill:var(--fg)!important}
[data-baseweb="popover"] ul,[data-baseweb="popover"] li,[data-baseweb="menu"]{background:var(--input)!important;color:var(--fg)!important}
[data-baseweb="popover"] li:hover{background:var(--hover)!important}
[data-testid="stBaseButton-secondary"],.stButton button[kind="secondary"]{
  background:var(--card)!important;color:var(--fg)!important;border:1px solid var(--border)!important}
[data-testid="stBaseButton-secondary"] *,.stButton button[kind="secondary"] *{color:var(--fg)!important}
[data-testid="stBaseButton-primary"],.stButton button[kind="primary"]{background:var(--primary)!important;color:#fff!important}
[data-baseweb="tab"]{color:var(--muted)!important}
[data-baseweb="tab"][aria-selected="true"]{color:var(--primary)!important}
[data-testid="stExpander"] details{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:10px}
[data-testid="stChatMessage"]{background:var(--card);border:1px solid var(--border);border-radius:12px}
[data-testid="stChatInput"] textarea{color:var(--fg)!important}
[data-testid="stBottom"]>div,[data-testid="stBottomBlockContainer"]{background:var(--bg)!important}
.wx-wrap{max-height:380px;overflow:auto;border:1px solid var(--border);border-radius:12px;background:var(--card);margin-bottom:12px}
.wx-table{width:100%;border-collapse:collapse;font-size:.9rem}
.wx-table th{position:sticky;top:0;background:var(--card);text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);color:var(--muted)!important}
.wx-table td{padding:6px 10px;border-bottom:1px solid var(--border)}
.bar{position:relative;background:var(--hover);border-radius:6px;height:20px;min-width:90px}
.bar div{background:var(--primary);opacity:.55;height:100%;border-radius:6px}
.bar span{position:absolute;left:8px;top:0;line-height:20px;font-size:.8rem;color:var(--fg)}
"""


def css(dark):
    v = ";".join(f"--{k}:{c}" for k, c in PAL[dark].items())
    return f"<style>:root{{{v}}}{CSS}</style>"
