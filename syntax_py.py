# syntax.py
# syntax highlighter for microPython
import sys
from PyQt5.QtCore import QRegExp, QRegularExpression
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter

def format(color, style=''):
    '''Return a QTextCharFormat with the given attributes.
    '''
    _color = QColor()
    _color.setNamedColor(color)

    _format = QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)
    if 'italicbold' in style:
        _format.setFontItalic(True)
        _format.setFontWeight(QFont.Bold)
    return _format

#mybrawn = ("#7E5916")
# Syntax styles that can be shared by all languages
STYLES = {
    'keyword': format('#d88b68'),
    'operator': format('#d88b68'),
    'brace': format('#d88b68'),
    'defclass': format('#FC9C16', 'bold'),
    'classes': format('#FC9C16', 'bold'),
    'string': format('#77C96E'),
    'string2': format('#77C96E', 'italic'),
    'comment': format('#679FD3', 'italic'),
    'self': format('#D63030'),
    'selfnext': format('#D1D1D1'),
    'numbers': format('#6D97F9'),
    'boolean': format('#f2f268')
}

class Highlighter(QSyntaxHighlighter):
    '''
        Syntax highlighter for the microPython language.
    '''
    # Python keywords
    keywords = [
        'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def',
        'del', 'elif', 'else', 'except', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in',
        'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'print',
        'raise', 'return', 'super', 'try', 'while', 'with', 'yield',
        'None']

    # Python operators
    operators = [
        '=',
        # Comparison
        '==', '!=', '<', '<=', '>', '>=',
        # Arithmetic
        '\+', '-', '\*', '/', '//', '\%', '\*\*',
        # In-place
        '\+=', '-=', '\*=', '/=', '\%=',
        # Bitwise
        '\^', '\|', '\&', '\~', '>>', '<<',
    ]

    # Python braces
    braces = [
        '\{', '\}', '\(', '\)', '\[', '\]',
    ]
    def __init__(self, document):
        QSyntaxHighlighter.__init__(self, document)
        tri = ("'''")
        trid = ('"""')
        # Multi-line comments (expression, flag, style)
        # FIXME: The triple-quotes in these two lines will mess up the
        #   syntax highlighting from this point onward
        self.tri_single = (QRegExp(tri), 1, STYLES['comment'])
        self.tri_double = (QRegExp(trid), 2, STYLES['comment'])

        rules = []

        # Keyword, operator, and brace rules
        rules += [(r'\b%s\b' % w, 0, STYLES['keyword'])
            for w in Highlighter.keywords]
        rules += [(r'%s' % o, 0, STYLES['operator'])
            for o in Highlighter.operators]
        rules += [(r'%s' % b, 0, STYLES['brace'])
            for b in Highlighter.braces]

        # All other rules
        rules += [
            # Numeric literals
            (r'\b[+-]?[0-9]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, STYLES['numbers']),

            # 'self'
            (r'\bself\b', 0, STYLES['self']),

            # 'True'
            (r'\bTrue\b', 0, STYLES['boolean']),

            # 'False'
            (r'\bFalse\b', 0, STYLES['boolean']),

            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, STYLES['string']),

            # 'def' followed by a word
            (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),    # (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),

            # 'self.' followed by a word
            (r'\bself.\b\s*(\w+)', 1, STYLES['selfnext']),

            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, STYLES['classes']),

            # 'line comment' from '#' until a newline
            (r'#[^\n]*', 0, STYLES['comment']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QRegExp(pat), index, fmt) for (pat, index, fmt) in rules]

    # def highlightBlock(self, text):
    #     # Apply syntax highlighting to the given block of text.
    #     i = 1
    #     # Do other syntax formatting
    #     for expression, nth, format in self.rules:
    #         index = expression.indexIn(text, 0)
    #
    #         while index >= 0:
    #             # We actually want the index of the nth match
    #             index = expression.pos(nth)
    #             length = len(expression.cap(nth))
    #             self.setFormat(index, length, format)
    #             index = expression.indexIn(text, index + length)
    #
    #     self.setCurrentBlockState(0)
    #
    #     # Do multi-line comment strings
    #     in_multiline = self.match_multiline(text, *self.tri_single)
    #     if not in_multiline:
    #         in_multiline = self.match_multiline(text, *self.tri_double)

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """
        self.tripleQuoutesWithinStrings = []
        # Do other syntax formatting
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)
            if index >= 0:
                # if there is a string we check
                # if there are some triple quotes within the string
                # they will be ignored if they are matched again
                if expression.pattern() in [r'"[^"\\]*(\\.[^"\\]*)*"', r"'[^'\\]*(\\.[^'\\]*)*'"]:
                    innerIndex = self.tri_single[0].indexIn(text, index + 1)
                    if innerIndex == -1:
                        innerIndex = self.tri_double[0].indexIn(text, index + 1)
                    if innerIndex != -1:
                        tripleQuoteIndexes = range(innerIndex, innerIndex + 3)
                        self.tripleQuoutesWithinStrings.extend(tripleQuoteIndexes)

            while index >= 0:
                # skipping triple quotes within strings
                if index in self.tripleQuoutesWithinStrings:
                    index += 1
                    expression.indexIn(text, index)
                    continue

                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)
        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            in_multiline = self.match_multiline(text, *self.tri_double)

    def match_multiline(self, text, delimiter, in_state, style):
        """Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False otherwise
        if self.currentBlockState() == in_state:
            return True
        else:
            return False