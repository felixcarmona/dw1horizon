"""Translate guide text with the website's i18n catalog, preserving game names."""
from html import escape
from html.parser import HTMLParser
import re


def translate(page, english, strings):
    pairs = [(en, strings.get(key, en)) for key, en in english.items() if key.startswith('data.')]
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    exact = dict(pairs)
    templates = []
    for en, own in pairs:
        fields = re.findall(r'\{(\w+)\}', en)
        if not fields:
            continue
        pattern = re.escape(en)
        for field in fields:
            capture = r'(\d+)' if field in ('n', 'total', 'techniques', 'species') else r'(.+?)'
            pattern = pattern.replace(re.escape('{'+field+'}'), capture)
        templates.append((re.compile(pattern), fields, own))
    plain = {en: own for en, own in pairs if '{' not in en}
    labels = re.compile('|'.join(('(?<!\\w)' if s[0].isalnum() else '') + re.escape(s)
                                + ('(?!\\w)' if s[-1].isalnum() else '') for s in plain))

    class Translator(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.out = []
            self.skip = []
        def handle_starttag(self, tag, attrs):
            self.out.append(self.get_starttag_text())
            if tag not in ('meta', 'link', 'input', 'br', 'hr', 'img'):
                self.skip.append(any(k == 'translate' and v == 'no' for k, v in attrs) or (self.skip[-1] if self.skip else False))
        def handle_startendtag(self, tag, attrs):
            self.out.append(self.get_starttag_text())
        def handle_endtag(self, tag):
            self.out.append(f'</{tag}>')
            if self.skip:
                self.skip.pop()
        def handle_decl(self, decl):
            self.out.append(f'<!{decl}>')
        def handle_data(self, text):
            if self.skip and self.skip[-1]:
                self.out.append(escape(text, quote=False))
                return
            stripped = text.strip()
            result = exact.get(stripped)
            if result is None:
                for pattern, fields, own in templates:
                    found = pattern.fullmatch(stripped)
                    if found:
                        result = own
                        for key, value in zip(fields, found.groups()):
                            result = result.replace('{'+key+'}', value)
                        break
            if result is None:
                # Replace each source span once: translated labels never become inputs.
                for pattern, fields, own in templates:
                    if all(field in ('n', 'total', 'techniques', 'species') for field in fields):
                        def replacement(match):
                            result = own
                            for key, value in zip(fields, match.groups()):
                                result = result.replace('{'+key+'}', value)
                            return result
                        text = pattern.sub(replacement, text)
                result = labels.sub(lambda match: plain[match.group()], text)
            else:
                result = text[:len(text)-len(text.lstrip())] + result + text[len(text.rstrip()):]
            self.out.append(escape(result, quote=False))
    parser = Translator()
    parser.feed(page)
    return '\n'.join(line.rstrip() for line in ''.join(parser.out).splitlines()) + '\n'
