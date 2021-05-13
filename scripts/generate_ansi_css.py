"""
This file is used to generate ansi.min.css.

ansi.css's classes are compatible with ansi2html's conv.convert(ansi, full=False) output.

"""

from ansi2html import Ansi2HTMLConverter
conv = Ansi2HTMLConverter()

# ref. https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html

ansi = ''

# Foreground

# 8 colors
for i in range(30, 38):
    ansi += f'\x1b[{i}m\x1b[0m'
# 16 colors
for i in range(30, 38):
    ansi += f'\x1b[{i};1m\x1b[0m'
# 256 colors
for i in range(0, 265):
    ansi += f'\x1b[38;5;{i}m\x1b[0m'

# Background

# 8 colors
for i in range(40, 48):
    ansi += f'\x1b[{i}m\x1b[0m'
# 16 colors
for i in range(40, 48):
    ansi += f'\x1b[{i};1m\x1b[0m'
# 256 colors
for i in range(0, 265):
    ansi += f'\x1b[48;5;{i}m\x1b[0m'

# Decorations
# bold
ansi += f'\x1b[1m\x1b[0m'
# underline
ansi += f'\x1b[4m\x1b[0m'
# reversed
ansi += f'\x1b[7m\x1b[0m'

html = conv.convert(ansi)
css = "".join(f".ansi{line}" for line in html.split('</style>')[0].split('.ansi')[2:])
css_minified = css.replace(' ', '').replace('\n', '').replace(';}', '}')
print(css_minified)
