import logging


def _dedupe_case_insensitive(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        candidate = str(value or "").strip()
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def merge_csv_values(*raw_values: str, limit: int = 20) -> str:
    merged: list[str] = []
    for raw in raw_values:
        if not raw:
            continue
        merged.extend(token.strip() for token in str(raw).split(","))

    ordered = _dedupe_case_insensitive(merged)
    return ",".join(ordered[:limit])


def derive_daily_nltk_fields(title: str, user_message: str) -> dict[str, str]:
    text = f"{title} {user_message}".strip()
    if not text:
        return {
            "tags": "",
            "daily_people_names": "",
            "daily_places": "",
        }

    try:
        from nltk import ne_chunk, pos_tag, word_tokenize
        from nltk.corpus import stopwords
        from nltk.tree import Tree
    except Exception:
        return {
            "tags": "",
            "daily_people_names": "",
            "daily_places": "",
        }

    tags: list[str] = []
    people_names: list[str] = []
    places: list[str] = []

    try:
        try:
            stop_words = set(stopwords.words("english"))
        except LookupError:
            stop_words = set()

        tag_blocklist = {"example", "diary", "entry", "daily", "dream"}
        entity_blocklist = {
            "example",
            "diary",
            "entry",
            "daily",
            "dream",
            "today",
            "yesterday",
            "tomorrow",
            "morning",
            "afternoon",
            "evening",
            "night",
            "work",
            "home",
            "day",
            "week",
            "month",
            "year",
            "time",
            "project",
            "good",
            "great",
            "nice",
            "productive",
            "wonderful",
            "progress",
            "flying",
        }

        tokens = word_tokenize(text)
        tagged_tokens = pos_tag(tokens)
        ner_tree = ne_chunk(tagged_tokens)

        for token, pos in tagged_tokens:
            token_clean = token.strip().lower()
            if not token_clean or len(token_clean) < 3:
                continue
            if not token_clean.isalpha():
                continue
            if token_clean in stop_words or token_clean in tag_blocklist:
                continue
            if pos.startswith("NN") or pos.startswith("JJ"):
                tags.append(token_clean)

        for node in ner_tree:
            if not isinstance(node, Tree):
                continue

            label = node.label()
            entity = " ".join(leaf[0] for leaf in node.leaves()).strip()
            if not entity:
                continue

            if label == "PERSON":
                entity_lower = entity.lower()
                entity_words = entity_lower.split()
                if all(
                    word in stop_words or word in entity_blocklist
                    for word in entity_words
                ):
                    continue
                if len(entity_words) == 1 and (
                    entity_lower in stop_words or entity_lower in entity_blocklist
                ):
                    continue
                if entity.isupper() and len(entity) > 1:
                    continue

                people_names.append(entity)
                tags.append(entity.lower().replace(" ", "_"))
            elif label in {"GPE", "LOCATION", "FACILITY"}:
                places.append(entity)
                tags.append(entity.lower().replace(" ", "_"))
    except (LookupError, ValueError, TypeError):
        return {
            "tags": "",
            "daily_people_names": "",
            "daily_places": "",
        }
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).debug("NLTK enrichment failed: %s", exc)

    deduped_tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in tags:
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        deduped_tags.append(tag)

    return {
        "tags": ",".join(deduped_tags[:20]),
        "daily_people_names": ",".join(_dedupe_case_insensitive(people_names)[:20]),
        "daily_places": ",".join(_dedupe_case_insensitive(places)[:20]),
    }


def derive_dream_nltk_fields(row_data: dict[str, str]) -> dict[str, str]:
    text_parts = [
        row_data.get("title", ""),
        row_data.get("plot", ""),
        row_data.get("cast", ""),
        row_data.get("symbols_and_imagery", ""),
        row_data.get("insight", ""),
        row_data.get("action", ""),
        row_data.get("other", ""),
    ]
    text = " ".join(part for part in text_parts if part).strip()

    if not text:
        return {
            "tags": row_data.get("tags", ""),
            "dream_people_names": "",
            "dream_places": "",
        }

    try:
        from nltk import ne_chunk, pos_tag, word_tokenize
        from nltk.corpus import stopwords
        from nltk.tree import Tree
    except Exception:
        return {
            "tags": row_data.get("tags", ""),
            "dream_people_names": "",
            "dream_places": "",
        }

    tags: list[str] = []
    people_names: list[str] = []
    places: list[str] = []

    try:
        try:
            stop_words = set(stopwords.words("english"))
        except LookupError:
            stop_words = set()

        tag_blocklist = {
            "image",
            "generated",
            "prompt",
            "example",
            "unknown",
            "dream",
            "lucid",
            "vivid",
            "nightmare",
        }
        entity_blocklist = {
            "dream",
            "flying",
            "image",
            "generated",
            "prompt",
            "lucid",
            "vivid",
            "nightmare",
            "sleep",
            "wake",
            "asleep",
            "awake",
            "night",
            "morning",
            "example",
            "unknown",
            "people",
            "person",
            "someone",
            "somebody",
            "freedom",
            "joy",
            "fear",
            "love",
            "hope",
            "peace",
            "happiness",
            "sadness",
            "anger",
            "excitement",
            "wonder",
            "surprise",
            "wings",
            "clouds",
            "mountains",
            "ocean",
            "sky",
            "water",
            "light",
            "darkness",
            "shadow",
            "time",
            "space",
            "world",
            "life",
            "death",
            "present",
            "past",
            "future",
            "day",
            "week",
            "month",
            "year",
        }

        tokens = word_tokenize(text)
        tagged_tokens = pos_tag(tokens)
        ner_tree = ne_chunk(tagged_tokens)

        for token, pos in tagged_tokens:
            token_clean = token.strip().lower()
            if not token_clean or len(token_clean) < 3:
                continue
            if not token_clean.isalpha():
                continue
            if token_clean in stop_words or token_clean in tag_blocklist:
                continue
            if pos.startswith("NN") or pos.startswith("JJ"):
                tags.append(token_clean)

        for node in ner_tree:
            if not isinstance(node, Tree):
                continue

            label = node.label()
            entity = " ".join(leaf[0] for leaf in node.leaves()).strip()
            if not entity:
                continue

            if label == "PERSON":
                entity_lower = entity.lower()
                entity_words = entity_lower.split()
                if all(
                    word in stop_words or word in entity_blocklist
                    for word in entity_words
                ):
                    continue
                if len(entity_words) == 1 and (
                    entity_lower in stop_words or entity_lower in entity_blocklist
                ):
                    continue
                if entity.isupper() and len(entity) > 1:
                    continue

                people_names.append(entity)
                tags.append(entity.lower().replace(" ", "_"))
            elif label in {"GPE", "LOCATION", "FACILITY"}:
                places.append(entity)
                tags.append(entity.lower().replace(" ", "_"))
    except (LookupError, ValueError, TypeError):
        return {
            "tags": row_data.get("tags", ""),
            "dream_people_names": "",
            "dream_places": "",
        }
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).debug("Dream NLTK enrichment failed: %s", exc)

    deduped_tags: list[str] = []
    seen_tags: set[str] = set()
    if row_data.get("tags"):
        for tag in row_data["tags"].split(","):
            tag_clean = tag.strip().lower()
            if tag_clean and tag_clean not in seen_tags and tag_clean not in tag_blocklist:
                if (
                    "image" not in tag_clean
                    and "generated" not in tag_clean
                    and "prompt" not in tag_clean
                ):
                    seen_tags.add(tag_clean)
                    deduped_tags.append(tag_clean)

    for tag in tags:
        if tag in seen_tags or tag in tag_blocklist:
            continue
        seen_tags.add(tag)
        deduped_tags.append(tag)

    return {
        "tags": ",".join(deduped_tags[:20]),
        "dream_people_names": ",".join(_dedupe_case_insensitive(people_names)[:20]),
        "dream_places": ",".join(_dedupe_case_insensitive(places)[:20]),
    }
