import re
import unicodedata
from typing import List, Optional, Dict, Any, Set, Tuple

class ItemDisambiguator:
    """
    Ultra-Sensitive AI Item Disambiguator & Matcher for Accounting & Inventory.
    
    Specifically prevents improper merging of inventory items whose names differ
    by ending suffixes, sizes, weights, packaging, grades, or physical states:
    - "G'isht M-100 pishiq" vs "G'isht M-100 xom"
    - "Qog'oz A4 80g" vs "Qog'oz A4 75g"
    - "Truba d-20mm" vs "Truba d-25mm"
    - "Kabel VVG 3x1.5" vs "Kabel VVG 3x2.5"
    - "Sement M-400 50kg" vs "Sement M-400 25kg"
    - "Un 1-nav" vs "Un 2-nav"
    - "SvetoCopy Classic" vs "SvetoCopy Premium"
    """

    # Distinctive suffix/modifier keywords in Uzbek and Russian trade nomenclature
    STATE_KEYWORDS: Set[str] = {
        # Qualities & physical state
        "pishiq", "xom", "quyma", "qopda", "qoplarda", "qadoqda", "qadoqlangan",
        "dona", "donali", "paket", "rulon", "blok", "pachka",
        # Grades & categories
        "oliy", "1-nav", "2-nav", "3-nav", "1-sort", "2-sort", "3-sort",
        "sort1", "sort2", "sort3", "nav1", "nav2", "toifa-a", "toifa-b",
        # Product tiers / editions
        "classic", "premium", "ultra", "pro", "max", "plus", "eco", "standart", "standard",
        # Common colors
        "oq", "qora", "qizil", "kok", "ko'k", "sariq", "yashil", "kulrang", "jigar",
        "bely", "belyy", "cherny", "krasny", "siniy", "zeleny",
        # Import/origin
        "mahalliy", "import", "xitoy", "rossiya", "turkiya"
    }

    # Regex patterns for trailing dimensions, measurements, and numerical specs
    DIMENSION_PATTERN = re.compile(
        r'(?:^|\s|[(\[-])(\d+(?:[.,]\d+)?\s*(?:mm|cm|sm|m|kg|g|gr|l|ml|litr|t|tonna|m2|m3|w-?\d+|v|kv|vt|wt|mkr|mk|sm|dona))\b',
        re.IGNORECASE
    )
    MULTIPLIER_PATTERN = re.compile(
        r'(?:^|\s|[(\[-])(\d+(?:[.,]\d+)?\s*[x*х×]\s*\d+(?:[.,]\d+)?(?:\s*[x*х×]\s*\d+(?:[.,]\d+)?)?)\b',
        re.IGNORECASE
    )
    GRADE_NUM_PATTERN = re.compile(
        r'\b(?:m|b|d|a|v|g)-?(\d{2,4})\b',
        re.IGNORECASE
    )

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Normalizes apostrophes, dashes, and basic whitespace."""
        if not text:
            return ""
        # Normalize unicode
        t = unicodedata.normalize("NFKC", str(text))
        # Normalize all Uzbek apostrophes / single quotes (\u2018, \u2019, \u02bb, \u02bc, `, ', etc.)
        t = re.sub(r"[\u2018\u2019\u02bb\u02bc\u02bd\u02be\u0060\u00b4\u2032']", "'", t)
        # Normalize dashes and hyphens
        t = re.sub(r"[\u2013\u2014\u2212-]", "-", t)
        # Collapse multiple spaces
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @classmethod
    def extract_features(cls, name: str) -> Dict[str, Any]:
        """
        Extracts base stem, numeric dimensions, multiplier patterns,
        and trailing semantic modifiers from an item name.
        """
        clean = cls.clean_text(name).lower()
        if not clean:
            return {
                "raw": "",
                "stem": "",
                "dimensions": set(),
                "multipliers": set(),
                "grades": set(),
                "state_modifiers": set(),
                "trailing_tokens": [],
                "tokens": []
            }

        # 1. Extract multipliers (e.g. 3x1.5, 2x2.5)
        multipliers = set(re.findall(cls.MULTIPLIER_PATTERN, clean))
        # Remove matched multipliers for cleaner stem
        clean_no_mult = cls.MULTIPLIER_PATTERN.sub(" ", clean)

        # 2. Extract dimensions (e.g. 80g, 50kg, 20mm, 5l)
        dimensions = set()
        for match in re.findall(cls.DIMENSION_PATTERN, clean_no_mult):
            d_clean = match.replace(" ", "")
            dimensions.add(d_clean)
        clean_no_dim = cls.DIMENSION_PATTERN.sub(" ", clean_no_mult)

        # 3. Extract grade numbers (e.g. M-100, M-400, A-500)
        grades = set(re.findall(cls.GRADE_NUM_PATTERN, clean))

        # 4. Extract token words
        tokens = [tok.strip(",.;:()[]{}\"'") for tok in clean_no_dim.split() if tok.strip(",.;:()[]{}\"'")]

        state_modifiers = set()
        for tok in tokens:
            if tok in cls.STATE_KEYWORDS:
                state_modifiers.add(tok)

        # Trailing tokens (last 2 non-empty tokens are most critical in trade nomenclatures)
        trailing_tokens = tokens[-2:] if len(tokens) >= 2 else tokens

        # Base stem without modifiers
        stem_tokens = [t for t in tokens if t not in cls.STATE_KEYWORDS]
        stem = " ".join(stem_tokens).strip()

        return {
            "raw": clean,
            "stem": stem,
            "dimensions": dimensions,
            "multipliers": multipliers,
            "grades": grades,
            "state_modifiers": state_modifiers,
            "trailing_tokens": trailing_tokens,
            "tokens": tokens
        }

    @classmethod
    def are_distinct_items(cls, name1: str, name2: str) -> bool:
        """
        Returns TRUE if name1 and name2 represent physically different products
        and MUST NOT be merged, even if their stems or MXIK codes match.
        """
        f1 = cls.extract_features(name1)
        f2 = cls.extract_features(name2)

        # Exact match
        if f1["raw"] == f2["raw"]:
            return False

        # If both are empty
        if not f1["raw"] or not f2["raw"]:
            return f1["raw"] != f2["raw"]

        # Check 1: Conflicting dimensions (e.g. "80g" vs "75g", "20mm" vs "25mm", "50kg" vs "25kg")
        if f1["dimensions"] or f2["dimensions"]:
            if f1["dimensions"] != f2["dimensions"]:
                return True

        # Check 2: Conflicting multipliers (e.g. "3x1.5" vs "3x2.5")
        if f1["multipliers"] or f2["multipliers"]:
            if f1["multipliers"] != f2["multipliers"]:
                return True

        # Check 3: Conflicting grades (e.g. M-100 vs M-400)
        if f1["grades"] or f2["grades"]:
            if f1["grades"] != f2["grades"]:
                return True

        # Check 4: Conflicting state modifiers (e.g. "pishiq" vs "xom", "1-nav" vs "2-nav", "classic" vs "premium")
        if f1["state_modifiers"] or f2["state_modifiers"]:
            if f1["state_modifiers"] != f2["state_modifiers"]:
                return True

        # Check 5: Trailing token differences
        # If stems are identical or very close, but the trailing token differs
        if f1["trailing_tokens"] and f2["trailing_tokens"]:
            last1 = f1["trailing_tokens"][-1]
            last2 = f2["trailing_tokens"][-1]
            if last1 != last2:
                # If either trailing token has numbers or is in keywords
                if any(c.isdigit() for c in (last1 + last2)) or (last1 in cls.STATE_KEYWORDS or last2 in cls.STATE_KEYWORDS):
                    return True
                # If both are substantial words (>2 letters) and stems match
                if len(last1) >= 3 and len(last2) >= 3 and f1["stem"] == f2["stem"]:
                    return True

        # Check 6: Levenshtein / character edit distance if stems differ
        if f1["stem"] != f2["stem"]:
            # If length differs substantially or stems are not sub-strings
            if f1["stem"] not in f2["stem"] and f2["stem"] not in f1["stem"]:
                # Calculate Jaccard similarity of tokens
                set1 = set(f1["tokens"])
                set2 = set(f2["tokens"])
                intersection = len(set1 & set2)
                union = len(set1 | set2)
                jaccard = intersection / union if union > 0 else 0
                if jaccard < 0.85:
                    return True

        return False

    @classmethod
    def find_best_match(
        cls,
        target_name: str,
        candidates: List[Any],
        target_ikpu: Optional[str] = None
    ) -> Optional[Any]:
        """
        Ultra-sensitive candidate lookup.
        Ensures candidates with conflicting suffix modifiers or distinct specs
        are strictly rejected, even if IKPU matches.
        
        candidates: Sequence of items with .name (and optionally .ikpu_code).
        """
        if not target_name or not candidates:
            return None

        clean_target = cls.clean_text(target_name).lower()

        # 1. Exact normalized match (highest confidence)
        for cand in candidates:
            cand_name = getattr(cand, "name", "")
            if cls.clean_text(cand_name).lower() == clean_target:
                return cand

        # 2. Candidate filtering & sensitive disambiguation
        # If IKPU is given, filter to items with same IKPU, or consider all candidates
        filtered_candidates = []
        if target_ikpu:
            target_ikpu_clean = str(target_ikpu).strip().rstrip(".0")
            for cand in candidates:
                cand_ikpu = getattr(cand, "ikpu_code", None)
                if cand_ikpu:
                    cand_ikpu_clean = str(cand_ikpu).strip().rstrip(".0")
                    if cand_ikpu_clean == target_ikpu_clean:
                        filtered_candidates.append(cand)

        # If no same-IKPU candidates found, search all candidates
        pool = filtered_candidates if filtered_candidates else candidates

        best_match = None
        best_score = 0.0

        for cand in pool:
            cand_name = getattr(cand, "name", "")
            # STRICT CHECK: If AI determines they are distinct items, DO NOT MATCH!
            if cls.are_distinct_items(target_name, cand_name):
                continue

            # Compute token similarity
            f_target = cls.extract_features(target_name)
            f_cand = cls.extract_features(cand_name)

            set1 = set(f_target["tokens"])
            set2 = set(f_cand["tokens"])
            union = len(set1 | set2)
            if union == 0:
                continue

            jaccard = len(set1 & set2) / union
            # Require at least 0.90 similarity to merge non-identical strings
            if jaccard > best_score and jaccard >= 0.90:
                best_score = jaccard
                best_match = cand

        return best_match
