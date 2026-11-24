"""The directory: where agents discover businesses by category and area."""
import json
import os
import re
import threading
import uuid

from .schema import validate_card


class Directory:
    def __init__(self, path=None):
        self._cards = {}
        self._lock = threading.Lock()
        self._path = path
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._cards = json.load(f)

    def _save(self):
        if self._path:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._cards, f, ensure_ascii=False, indent=2)

    def register(self, card):
        """Validate and store a card. Returns (card_id, normalised_card)."""
        card = validate_card(card)
        slug = re.sub(r"[^a-z0-9]+", "-", card["name"].lower()).strip("-") or "shop"
        with self._lock:
            card_id = f"{slug}-{uuid.uuid4().hex[:6]}"
            self._cards[card_id] = card
            self._save()
        return card_id, card

    def get(self, card_id):
        with self._lock:
            return self._cards.get(card_id)

    def items(self):
        with self._lock:
            return list(self._cards.items())

    def search(self, category=None, area=None, language=None):
        results = []
        for card_id, card in self.items():
            if category and card["category"] != category.lower():
                continue
            if area and area.lower() not in card["area"].lower():
                continue
            if language and language.lower() not in [l.lower() for l in card["languages"]]:
                continue
            results.append({"id": card_id, **card})
        return results
