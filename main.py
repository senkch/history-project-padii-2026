from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

INPUT_JSON = Path("dictionary.json")
OUTPUT_HTML = Path("index.html")
OUTPUT_CSS = Path("styles.css")


@dataclass
class Entry:
    word: str
    meaning: str = ""
    example: str = ""


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    return json.loads(raw)


def _first_non_empty(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _to_entry(word: str, value: Any) -> Entry:
    word = str(word).strip()
    if not word:
        return Entry(word="")

    if isinstance(value, str):
        return Entry(word=word, meaning=value.strip())

    if isinstance(value, dict):
        meaning = _first_non_empty(
            value,
            ["translation", "meaning", "definition", "text", "description", "value"],
        )
        example = _first_non_empty(value, ["example", "sentence", "usage"])
        return Entry(word=word, meaning=meaning, example=example)

    if isinstance(value, list):
        joined = "; ".join(str(item).strip() for item in value if str(item).strip())
        return Entry(word=word, meaning=joined)

    return Entry(word=word, meaning=str(value).strip())


def normalize_entries(data: Any) -> list[Entry]:
    entries: list[Entry] = []

    if isinstance(data, dict):
        for container_key in ["terms", "entries", "words", "dictionary", "items", "data"]:
            container = data.get(container_key)
            if isinstance(container, (list, dict)):
                return normalize_entries(container)

        direct_word = _first_non_empty(data, ["word", "term", "name", "title"])
        if direct_word:
            meaning = _first_non_empty(
                data,
                ["translation", "meaning", "definition", "text", "description"],
            )
            example = _first_non_empty(data, ["example", "sentence", "usage"])
            return [Entry(word=direct_word, meaning=meaning, example=example)]

        for word, value in data.items():
            entry = _to_entry(str(word), value)
            if entry.word:
                entries.append(entry)
        return entries

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                word = item.strip()
                if word:
                    entries.append(Entry(word=word))
                continue

            if isinstance(item, dict):
                word = _first_non_empty(item, ["word", "term", "name", "title"])
                if word:
                    meaning = _first_non_empty(
                        item,
                        ["translation", "meaning", "definition", "text", "description"],
                    )
                    example = _first_non_empty(item, ["example", "sentence", "usage"])
                    entries.append(Entry(word=word, meaning=meaning, example=example))
                    continue

                if len(item) == 1:
                    single_word, single_value = next(iter(item.items()))
                    entry = _to_entry(str(single_word), single_value)
                    if entry.word:
                        entries.append(entry)

    return entries


def word_sort_key(word: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFKD", word.casefold())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_marks, word.casefold()


def _entry_group_letter(word: str) -> str:
    trimmed = word.strip()
    if not trimmed:
        return "#"
    return trimmed[0].upper()


def capitalize_first(word: str) -> str:
    text = word.strip()
    if not text:
        return ""
    return text[0].upper() + text[1:]


def group_entries(entries: list[Entry]) -> list[tuple[str, list[Entry]]]:
    grouped: dict[str, list[Entry]] = {}

    for entry in entries:
        letter = _entry_group_letter(entry.word)
        grouped.setdefault(letter, []).append(entry)

    ordered_letters = sorted(grouped.keys(), key=word_sort_key)
    ordered_groups: list[tuple[str, list[Entry]]] = []

    for letter in ordered_letters:
        letter_entries = sorted(grouped[letter], key=lambda entry: word_sort_key(entry.word))
        ordered_groups.append((letter, letter_entries))

    return ordered_groups


def render_single_card(entry: Entry) -> str:
    meaning_text = entry.meaning.strip() if entry.meaning else "Без перевода"
    example_text = entry.example.strip() if entry.example else "Пример не добавлен"

    word_display = escape(capitalize_first(entry.word))
    meaning_display = escape(meaning_text)

    word_attr = escape(entry.word, quote=True)
    meaning_attr = escape(meaning_text, quote=True)
    example_attr = escape(example_text, quote=True)

    return (
        f"""
        <article
            class=\"word-card\"
            tabindex=\"0\"
            data-word=\"{word_attr}\"
            data-meaning=\"{meaning_attr}\"
            data-example=\"{example_attr}\"
        >
            <div class=\"word-main\">
                <h2>{word_display}</h2>
                <p class=\"meaning\">{meaning_display}</p>
            </div>
        </article>
        """.strip()
    )


def render_cards(entries: list[Entry]) -> str:
    if not entries:
        return (
            '<p class="empty">Словарь пока пуст. '
            'Добавьте записи в <code>dictionary.json</code> '
            'и снова запустите <code>py -3 main.py</code>.</p>'
        )

    groups = group_entries(entries)
    group_blocks: list[str] = []
    for letter, letter_entries in groups:
        cards = "\n".join(render_single_card(entry) for entry in letter_entries)
        group_blocks.append(
            f"""
            <section class=\"letter-group\" aria-label=\"{escape(letter, quote=True)}\">
                <div class=\"letter-divider\">
                    <h2>{escape(letter)}</h2>
                    <span>{len(letter_entries)}</span>
                </div>
                <div class=\"cards-grid\">
                    {cards}
                </div>
            </section>
            """.strip()
        )

    return "\n".join(group_blocks)


def render_html(entries: list[Entry]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards_html = render_cards(entries)

    return f"""<!doctype html>
<html lang=\"ru\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>Словарь</title>
    <link rel=\"stylesheet\" href=\"{OUTPUT_CSS.name}\">
</head>
<body>
    <main class=\"container\">
        <header class=\"page-header\">
            <h1>Выражения в России XVIII века по изданию «Юности честное зерцало»</h1>
            <p>Выполнили: Губайдуллина Вероника, Дорофеев Максим</p>
            <p>ПАДИИ-2</p>
            <p>Источники: <a href="https://azbyka.ru/otechnik/6/yunosti-chestnoe-zertsalo-ili-pokazanie-k-zhitejskomu-obhozhdeniyu/#source">Азбука веры</a></p>
        </header>
        <section class=\"dictionary-groups\">
            {cards_html}
        </section>
    </main>

    <div class=\"modal-backdrop\" id=\"entry-modal\" hidden>
        <article
            class=\"modal-card\"
            role=\"dialog\"
            aria-modal=\"true\"
            aria-labelledby=\"modal-word\"
            aria-describedby=\"modal-meaning modal-example\"
        >
            <button class=\"modal-close\" id=\"modal-close\" type=\"button\" aria-label=\"Закрыть\">&times;</button>
            <h2 id=\"modal-word\" class=\"modal-word\"></h2>
            <p id=\"modal-meaning\" class=\"modal-meaning\"></p>
            <p id=\"modal-example\" class=\"modal-example\"></p>
        </article>
    </div>

    <script>
        const modal = document.getElementById('entry-modal');
        const modalClose = document.getElementById('modal-close');
        const modalWord = document.getElementById('modal-word');
        const modalMeaning = document.getElementById('modal-meaning');
        const modalExample = document.getElementById('modal-example');
        const cards = document.querySelectorAll('.word-card');
        let lastTrigger = null;

        const asSentence = (value) => {{
            const text = (value || '').trim();
            if (!text) {{
                return '';
            }}
            if (/[.!?…]$/.test(text)) {{
                return text;
            }}
            return `${{text}}.`;
        }};

        const capitalizeFirst = (value) => {{
            const text = (value || '').trim();
            if (!text) {{
                return '';
            }}
            return text.charAt(0).toLocaleUpperCase('ru-RU') + text.slice(1);
        }};

        const closeModal = () => {{
            if (modal.hidden) {{
                return;
            }}

            modal.classList.remove('visible');
            document.body.classList.remove('modal-open');
            window.setTimeout(() => {{
                modal.hidden = true;
                if (lastTrigger) {{
                    lastTrigger.focus();
                }}
            }}, 180);
        }};

        const openModal = (card) => {{
            lastTrigger = card;
            const word = capitalizeFirst(card.dataset.word || '');
            const meaning = asSentence(card.dataset.meaning || 'Без перевода');
            const example = asSentence(card.dataset.example || 'Пример не добавлен');

            modalWord.textContent = word;
            modalMeaning.textContent = `- ${{meaning}}`;
            modalExample.textContent = `"${{example}}"`;

            modal.hidden = false;
            document.body.classList.add('modal-open');
            window.requestAnimationFrame(() => modal.classList.add('visible'));
            modalClose.focus();
        }};

        cards.forEach((card) => {{
            card.addEventListener('click', () => openModal(card));
            card.addEventListener('keydown', (event) => {{
                if (event.key === 'Enter' || event.key === ' ') {{
                    event.preventDefault();
                    openModal(card);
                }}
            }});
        }});

        modalClose.addEventListener('click', closeModal);
        modal.addEventListener('click', (event) => {{
            if (event.target === modal) {{
                closeModal();
            }}
        }});

        document.addEventListener('keydown', (event) => {{
            if (event.key === 'Escape') {{
                closeModal();
            }}
        }});
    </script>
</body>
</html>
"""


def main() -> None:
    data = _read_json(INPUT_JSON)
    entries = normalize_entries(data)
    entries.sort(key=lambda entry: word_sort_key(entry.word))
    OUTPUT_HTML.write_text(render_html(entries), encoding="utf-8")
    print(f"Done: created {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
