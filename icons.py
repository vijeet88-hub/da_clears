"""Small inline SVG pictograms, one per ISO, viewBox 0 0 100 100. Color is
passed in so each renders in its own ISO's brand color."""


def pine_tree(color):
    """ISO-NE"""
    return f"""
    <svg viewBox="0 0 100 100" width="44" height="44">
      <rect x="44" y="78" width="12" height="16" fill="{color}" opacity="0.55"/>
      <polygon points="50,40 20,76 80,76" fill="{color}" opacity="0.75"/>
      <polygon points="50,20 28,56 72,56" fill="{color}" opacity="0.85"/>
      <polygon points="50,4 35,36 65,36" fill="{color}"/>
    </svg>"""


def liberty_bell(color):
    """PJM"""
    return f"""
    <svg viewBox="0 0 100 100" width="44" height="44">
      <path d="M50 8 C40 8 38 18 38 24 C25 28 19 54 14 70 C12 76 15 80 20 80
               L80 80 C85 80 88 76 86 70 C81 54 75 28 62 24 C62 18 60 8 50 8 Z"
            fill="{color}"/>
      <rect x="11" y="80" width="78" height="9" rx="4.5" fill="{color}" opacity="0.85"/>
      <path d="M50 26 L55 38 L46 48 L52 60" stroke="white" stroke-width="2.5"
            fill="none" opacity="0.9"/>
    </svg>"""


def skyline(color):
    """NYISO"""
    return f"""
    <svg viewBox="0 0 100 100" width="44" height="44">
      <rect x="6"  y="58" width="14" height="32" fill="{color}" opacity="0.6"/>
      <rect x="24" y="44" width="14" height="46" fill="{color}" opacity="0.75"/>
      <rect x="42" y="26" width="16" height="64" fill="{color}"/>
      <rect x="47" y="10" width="6"  height="18" fill="{color}"/>
      <rect x="62" y="50" width="14" height="40" fill="{color}" opacity="0.75"/>
      <rect x="80" y="62" width="12" height="28" fill="{color}" opacity="0.6"/>
    </svg>"""


def texas_star(color):
    """ERCOT"""
    points = ("50,5 60.58,35.44 92.75,36.09 67.12,55.56 76.45,86.41 "
              "50,68 23.55,86.41 32.88,55.56 7.25,36.09 39.42,35.44")
    return f"""
    <svg viewBox="0 0 100 100" width="44" height="44">
      <polygon points="{points}" fill="{color}"/>
    </svg>"""
