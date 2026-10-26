#!/usr/bin/env python3
"""Flag likely clutter in a draft, in the spirit of Zinsser's brackets.

Every flag is a prompt for attention, not a verdict. Read the sentence
without the flagged words and decide whether it still works.

Usage:
    python3 clutter_check.py draft.md
    python3 clutter_check.py draft.md --json
    cat draft.txt | python3 clutter_check.py -
    python3 clutter_check.py draft.md --only qualifier,inflated
    python3 clutter_check.py draft.md --ignore passive,long-sentence

Standard library only. Skips YAML front matter, fenced code blocks,
inline code spans and URLs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass

# ---------------------------------------------------------------------------
# Phrase rules: (pattern, suggestion). Plain phrases are escaped and matched
# case-insensitively on word boundaries; whitespace matches any run of
# whitespace. Patterns starting with "re:" are used as raw regexes.
# ---------------------------------------------------------------------------

INFLATED = [
    ("at this point in time", "now"),
    ("at the present time", "now"),
    ("at this juncture", "now"),
    ("at the present moment", "now"),
    ("currently being", "being"),
    ("due to the fact that", "because"),
    ("owing to the fact that", "because"),
    ("in light of the fact that", "because"),
    ("in spite of the fact that", "although"),
    ("despite the fact that", "although"),
    ("regardless of the fact that", "although"),
    ("the fact that", "recast; often just 'that'"),
    ("with the possible exception of", "except"),
    ("until such time as", "until"),
    ("for the purpose of", "for, to"),
    ("referred to as", "called"),
    ("in order to", "to"),
    ("in order for", "for"),
    ("in the event that", "if"),
    ("in the event of", "if"),
    ("on a daily basis", "daily"),
    ("on a regular basis", "regularly"),
    ("on a weekly basis", "weekly"),
    ("at all times", "always"),
    ("in the near future", "soon"),
    ("prior to", "before"),
    ("subsequent to", "after"),
    ("in close proximity", "near"),
    ("a large number of", "many"),
    ("a majority of", "most"),
    ("the vast majority of", "most"),
    ("a number of", "some, several (or give the number)"),
    ("has the ability to", "can"),
    ("have the ability to", "can"),
    ("is able to", "can"),
    ("are able to", "can"),
    ("is in a position to", "can"),
    ("totally lacked the ability to", "couldn't"),
    ("make a decision", "decide"),
    ("made a decision", "decided"),
    ("conduct an investigation", "investigate"),
    ("provide assistance", "help"),
    ("give consideration to", "consider"),
    ("take into consideration", "consider"),
    ("reach a conclusion", "conclude"),
    ("is of the opinion that", "thinks"),
    ("as a matter of fact", "in fact (or cut)"),
    ("in terms of", "about, in, for (or recast)"),
    ("with regard to", "about"),
    ("with respect to", "about"),
    ("in relation to", "about"),
    ("in regard to", "about"),
    ("for all intents and purposes", "cut"),
    ("each and every", "each, every"),
    ("first and foremost", "first"),
    ("whether or not", "whether"),
    ("going forward", "cut, or 'from now on'"),
    ("moving forward", "cut, or 'from now on'"),
    ("at the end of the day", "cut"),
    ("personal friend", "friend"),
    ("personal feeling", "feeling"),
    ("personal opinion", "opinion"),
    ("personal physician", "doctor"),
    ("re:\\bexperienc(?:e|es|ed|ing)\\b", "'Experiencing' is an ultimate clutterer: say what happens ('Does it hurt?')"),
    ("negative cash-flow position", "losing money, broke"),
]

LONG_WORDS = [
    ("assistance", "help"),
    ("numerous", "many"),
    ("facilitate", "ease, help"),
    ("facilitates", "eases, helps"),
    ("remainder", "rest"),
    ("initial", "first"),
    ("initially", "at first"),
    ("implement", "do, carry out"),
    ("implemented", "did, carried out, built"),
    ("implementation", "doing, carrying out (or recast with a verb)"),
    ("sufficient", "enough"),
    ("attempt", "try"),
    ("attempted", "tried"),
    ("utilize", "use"),
    ("utilizes", "uses"),
    ("utilized", "used"),
    ("utilizing", "using"),
    ("utilization", "use"),
    ("commence", "begin, start"),
    ("commenced", "began, started"),
    ("terminate", "end, stop"),
    ("endeavor", "try"),
    ("ascertain", "find out"),
    ("demonstrate", "show"),
    ("approximately", "about"),
    ("additional", "more, extra"),
    ("purchase", "buy"),
    ("obtain", "get"),
    ("procure", "get"),
    ("require", "need"),
    ("requires", "needs"),
    ("transmit", "send"),
    ("possess", "have"),
    ("reside", "live"),
    ("subsequently", "later, then"),
    ("consequently", "so"),
    ("optimal", "best"),
    ("methodology", "method"),
    ("functionality", "features, what it does"),
    ("individual", "person, man, woman (if you mean a person)"),
    ("individuals", "people"),
    ("presently", "'presently' means soon; for 'now' write now"),
    ("currently", "now (or cut)"),
]

VERB_PREPOSITION = [
    ("re:\\bhead(?:s|ed|ing)?\\s+up\\b", "head, lead"),
    ("re:\\bfac(?:e|es|ed|ing)\\s+up\\s+to\\b", "face"),
    ("re:\\bfree(?:s|d|ing)?\\s+up\\b", "free"),
    ("re:\\border(?:s|ed|ing)?\\s+up\\b", "order"),
    ("re:\\bbeef(?:s|ed|ing)?\\s+up\\b", "strengthen"),
    ("re:\\bfir(?:e|es|ed|ing)\\s+off\\b", "send"),
    ("re:\\bstep(?:s|ped|ping)?\\s+down\\b", "vague: resigned? retired? fired? Say which"),
    ("re:\\bmeet(?:s|ing)?\\s+with\\b|\\bmet\\s+with\\b", "meet, met"),
    ("re:\\bconnect(?:s|ed|ing)?\\s+up\\b", "connect"),
    ("re:\\btest(?:s|ed|ing)?\\s+out\\b", "test"),
    ("re:\\bsum(?:s|med|ming)?\\s+up\\b", "sum"),
    ("re:\\bopen(?:s|ed|ing)?\\s+up\\b", "open"),
    ("re:\\bend(?:s|ed|ing)?\\s+up\\b", "end"),
    ("re:\\bfinish(?:es|ed|ing)?\\s+up\\b", "finish"),
    ("re:\\breach(?:es|ed|ing)?\\s+out\\b", "call, write, ask"),
    ("re:\\bcircl(?:e|es|ed|ing)\\s+back\\b", "come back to (say when)"),
]

REDUNDANT = [
    ("re:\\bblar\\w*\\s+loudly\\b", "blared"),
    ("re:\\bclench\\w*\\s+(?:\\w+\\s+){0,2}tightly\\b", "drop 'tightly'"),
    ("re:\\bsmil\\w*\\s+happily\\b", "drop 'happily'"),
    ("re:\\bgrin\\w*\\s+widely\\b", "drop 'widely'"),
    ("re:\\bwhisper\\w*\\s+(?:quietly|softly)\\b", "drop the adverb"),
    ("re:\\bshout\\w*\\s+loudly\\b", "drop 'loudly'"),
    ("totally flabbergasted", "flabbergasted"),
    ("effortlessly easy", "easy"),
    ("re:\\b(?:completely|totally)\\s+(?:destroyed|eliminated|finished|unanimous)\\b", "drop the adverb"),
    ("re:\\bplan(?:s|ned|ning)?\\s+(?:ahead|in advance)\\b", "plan"),
    ("re:\\brepeat(?:s|ed|ing)?\\s+again\\b", "repeat"),
    ("re:\\breturn(?:s|ed|ing)?\\s+back\\b", "return"),
    ("re:\\b(?:combine|join|merge)(?:s|d|ed|ing)?\\s+together\\b", "drop 'together'"),
    ("still remains", "remains"),
    ("tall skyscraper", "skyscraper"),
    ("end result", "result"),
    ("final outcome", "outcome"),
    ("past history", "history"),
    ("past experience", "experience"),
    ("future plans", "plans"),
    ("advance warning", "warning"),
    ("added bonus", "bonus"),
    ("free gift", "gift"),
    ("unexpected surprise", "surprise"),
    ("basic fundamentals", "fundamentals"),
    ("true facts", "facts"),
    ("general consensus", "consensus"),
    ("new innovation", "innovation"),
    ("close proximity", "near"),
    ("decidedly", "retire it"),
    ("eminently", "retire it"),
    ("arguably", "if provable, drop it; if arguable, say so"),
    ("virtually", "retire it, or be exact"),
    ("admittedly", "retire it"),
    ("literally", "only if it's literal"),
]

QUALIFIERS = [
    ("a bit", "cut: don't be a bit confused, be confused"),
    ("a little", "cut if it hedges"),
    ("sort of", "cut"),
    ("kind of", "cut (unless you mean 'a type of')"),
    ("rather", "cut"),
    ("quite", "cut"),
    ("very", "cut, or find a stronger word"),
    ("re:\\btoo\\s+(?=(?:good|bad|happy|sure|much|many|well|keen|pleased|thrilled)\\b)", "'too' for 'very' is clutter, unless wry"),
    ("pretty much", "cut"),
    ("re:\\bpretty\\s+(?=(?:good|bad|expensive|cheap|sure|big|small|hard|easy|clear|well|much|fast|slow)\\b)", "cut 'pretty'"),
    ("in a sense", "means nothing; cut"),
    ("in a very real sense", "cut"),
    ("somewhat", "cut"),
    ("fairly", "cut"),
    ("slightly", "cut, or be exact"),
    ("more or less", "cut"),
    ("to some extent", "cut"),
    ("relatively", "relative to what? cut or compare"),
    ("basically", "cut"),
    ("essentially", "cut"),
    ("actually", "cut"),
    ("really", "cut"),
    ("truly", "cut"),
    ("extremely", "cut, or find a stronger word"),
    ("incredibly", "cut"),
    ("absolutely", "cut"),
    ("totally", "cut"),
    ("hopefully", "cut, or say who hopes"),
    ("re:\\bit\\s+(?:seems|appears)\\s+(?:that\\s+)?", "take a stand"),
    ("re:\\bI\\s+(?:think|feel|believe)\\s+(?:that\\s+)?", "the opinion is obviously yours; cut"),
]

THROAT_CLEARING = [
    ("I might add", "if you might add, add it"),
    ("re:\\bit\\s+should\\s+be\\s+(?:pointed\\s+out|noted|mentioned|emphasized)\\s+that\\b", "point it out"),
    ("re:\\bit\\s+is\\s+(?:interesting|important|worth\\s+noting|worth\\s+mentioning|crucial|essential)\\s+to\\s+note\\s+that\\b", "make it interesting; just say it"),
    ("re:\\bit\\s+is\\s+worth\\s+(?:noting|mentioning)\\s+that\\b", "just say it"),
    ("re:\\bit\\s+is\\s+(?:clear|obvious|evident)\\s+that\\b", "if it's clear, the reader will see it"),
    ("this will interest you", "readers stop being interested"),
    ("needless to say", "then don't say it"),
    ("it goes without saying", "then let it go"),
    ("re:\\bas\\s+(?:we\\s+all|everyone)\\s+knows?\\b", "if they know, why tell them?"),
    ("re:\\bin\\s+this\\s+(?:article|essay|document|post|section|paper|memo|README|guide)\\s*,?\\s+(?:I|we)\\s+(?:will|would\\s+like\\s+to|aim\\s+to|want\\s+to)\\b", "start doing it"),
    ("re:\\bthe\\s+purpose\\s+of\\s+this\\s+(?:memo|email|document|article|post)\\s+is\\s+to\\b", "state the purpose as the first sentence"),
    ("re:\\b(?:let\\s+me\\s+be\\s+clear|to\\s+be\\s+honest|frankly|to\\s+tell\\s+you\\s+the\\s+truth)\\b", "implies you weren't before"),
    ("re:\\b(?:in\\s+today's\\s+fast-paced\\s+world|in\\s+this\\s+day\\s+and\\s+age)\\b", "stock opener; cut"),
    ("re:\\bI\\s+(?:just\\s+)?wanted\\s+to\\s+(?:reach\\s+out|follow\\s+up|let\\s+you\\s+know|take\\s+this\\s+opportunity|give\\s+(?:you\\s+)?a\\s+quick\\s+update)\\b", "start with the point"),
    ("re:\\bI\\s+hope\\s+this\\s+(?:email|message|note)\\s+finds\\s+you\\s+well\\b", "start with the point"),
    ("re:\\btake\\s+this\\s+opportunity\\s+to\\b", "just do it"),
    ("re:\\bit\\s+remains\\s+to\\s+be\\s+seen\\b|\\bit\\s+is\\s+too\\s+early\\s+to\\s+tell\\b", "take a stand"),
    ("re:\\byou\\s+see,", "'I stop reading writers who say \"You see.\"'"),
]

FAD_JARGON = [
    ("paradigm", "model, pattern"),
    ("paradigm shift", "change (say what changed)"),
    ("parameters", "limits (if you don't mean a variable)"),
    ("prioritize", "rank"),
    ("prioritizing", "ranking"),
    ("potentialize", "say what you mean"),
    ("re:\\bdialogu(?:e|es|ed|ing)\\s+with\\b", "talk with"),
    ("re:\\binterfac(?:e|es|ed|ing)\\s+with\\b", "meet, talk, work with"),
    ("re:\\b(?:your|my|our|their|his|her)\\s+input\\b", "ideas, opinion"),
    ("re:\\bimpact(?:s|ed|ing)\\b", "'impact' as a verb: affect, hit"),
    ("re:\\bde-impact\\w*", "say what you mean"),
    ("re:\\baccess(?:es|ed|ing)?\\s+(?:the\\s+)?(?:facts|information|data)\\b", "get, see, find"),
    ("downsizing", "layoffs, firing"),
    ("re:\\bgrow(?:ing)?\\s+the\\s+business\\b", "expand"),
    ("ongoing", "usually cut"),
    ("disincentive", "say what discourages what"),
    ("re:\\bdefinitiz\\w*", "define, settle"),
    ("re:\\bfinaliz\\w*", "finish, complete"),
    ("re:\\bleverag(?:e|es|ed|ing)\\b", "use"),
    ("re:\\bsynerg\\w*", "cooperation, work together"),
    ("bandwidth", "time, attention (unless you mean network capacity)"),
    ("actionable", "practical, useful"),
    ("deliverables", "name what you'll deliver"),
    ("learnings", "lessons"),
    ("re:\\b(?:robust|seamless(?:ly)?|world-class|best-in-class|cutting-edge|next-generation|state-of-the-art|game-changing|game\\s+changer|revolutionary)\\b", "show it with a fact"),
    ("re:\\bempower(?:s|ed|ing)?\\b", "let, help"),
    ("re:\\benabl(?:e|es|ed|ing)\\s+(?:users|teams|you|customers)\\s+to\\b", "let"),
    ("touch base", "talk, meet"),
    ("low-hanging fruit", "the easy part"),
    ("move the needle", "make a difference (say how much)"),
    ("deep dive", "close look"),
    ("re:\\b(?:get\\s+)?aligned\\s+on\\b", "agree on"),
    ("re:\\bsocializ(?:e|ed|ing)\\s+(?:the|this|an?)\\s+(?:idea|proposal|plan|doc)\\b", "share, discuss"),
    ("re:\\boperationaliz\\w*", "do, start, run"),
    ("re:\\bincentiviz\\w*", "encourage, pay"),
    ("solutioning", "solving"),
    ("ideate", "think of, come up with"),
    ("re:\\bthe\\s+ask\\b", "the request"),
]

JOURNALESE = [
    ("re:\\bnotables\\b", "well-known people (name them)"),
    ("re:\\bthe\\s+greats\\b", "name them"),
    ("famed", "famous, or show why"),
    ("staffers", "staff, employees"),
    ("upcoming", "next, coming, or the date"),
    ("re:\\benthus(?:e|es|ed|ing)\\b", "be enthusiastic"),
    ("re:\\bemot(?:e|es|ed|ing)\\b", "act, show"),
    ("put teeth into", "enforce, strengthen"),
    ("top brass", "officials, executives (name them)"),
    ("powers that be", "officials (name them)"),
    ("umpteenth", "give the number"),
    ("zillions", "give the number"),
    ("re:\\.\\s+Period\\.", "cut 'Period.'"),
]

CLICHES = [
    "shouldered his way", "only to be met", "waging a lonely war", "sending shock waves",
    "send shock waves", "kiss of death", "in the final analysis", "leave no stone unturned",
    "leaves no stone unturned", "tried and true", "the same old chestnuts",
    "think outside the box", "level playing field", "perfect storm", "raise the bar",
    "hit the ground running", "tip of the iceberg", "food for thought", "elephant in the room",
    "few and far between", "last but not least", "in the nick of time", "a whole new ballgame",
    "avoid like the plague", "crystal clear", "push the envelope", "best of both worlds",
    "by leaps and bounds", "not rocket science", "double-edged sword", "only time will tell",
    "time will tell", "calm before the storm", "lost my marbles", "kicked the bucket",
    "bottom dollar", "in the pink", "at first glance", "a far cry from", "dead as a doornail",
    "cool as a cucumber", "busy as a bee", "since the dawn of time", "since time immemorial",
    "the rest is history", "it is what it is", "back to the drawing board", "par for the course",
    "rule of thumb", "the ball is in your court", "on the same page", "win-win",
    "enjoyed a spell of illness", "enjoying a slump",
]

TRAVELESE = [
    "wondrous", "dappled", "roseate", "fabled", "scudding", "quaint", "nestled",
    "half-forgotten", "old meets new", "beckon", "beckons", "beckoning", "hidden gem",
    "breathtaking", "picturesque", "bustling", "unspoiled", "off the beaten path",
    "feast for the senses", "melting pot", "land of contrasts",
]

PRE_LABELS = [
    ("surprisingly", "let the fact surprise on its own"),
    ("predictably", "let the reader judge"),
    ("of course", "if it's obvious, cut; if not, don't say 'of course'"),
    ("interestingly", "make it interesting instead"),
    ("ironically", "only if it truly is; usually cut"),
    ("remarkably", "let the fact be remarkable"),
    ("amazingly", "let the reader be amazed"),
    ("shockingly", "let the reader be shocked"),
    ("needless to say", "then don't say it"),
]

SUMMARY_SIGNALS = [
    ("in sum", "the sound of cranking: stop instead"),
    ("in summary", "stop instead of summarizing"),
    ("in conclusion", "stop instead of summarizing"),
    ("to summarize", "stop instead of summarizing"),
    ("to sum up", "stop instead of summarizing"),
    ("all in all", "stop instead of summarizing"),
    ("re:\\bwhat\\s+(?:insights|lessons)\\s+can\\s+we\\s+glean\\b", "cranking; stop"),
]

USAGE = [
    ("re:\\b(?:is|are|was|were|be|been)\\s+comprised\\s+of\\b", "'comprise' means include: 'comprises' or 'is composed of'"),
    ("irregardless", "regardless"),
    ("could care less", "couldn't care less"),
    ("for all intensive purposes", "for all intents and purposes (or cut)"),
    ("re:\\b(?:rather|very|quite|somewhat|most|more)\\s+unique\\b", "unique takes no degrees"),
    ("between you and I", "between you and me"),
    ("re:\\b(?:and|or)\\s+myself\\b|\\bmyself\\s+and\\b", "me (or I): 'myself' is the refuge of idiots taught that 'me' is a dirty word"),
    ("re:\\b(?!(?:other|like|clock|counterclock|anticlock|length|cross|street|penny|edge|step|stretch|side|lengthy)wise\\b)[a-z]{3,}wise\\b", "drop the '-wise' suffix"),
    ("re:\\bflaunt(?:s|ed|ing)?\\s+(?:the|a|this|these|those)\\s+(?:rules?|law|laws|regulations?|convention)\\b", "flout (defy); flaunt means show off"),
    ("re:\\bfortuitous\\b", "means accidental, not lucky"),
    ("re:\\bdisinterested\\b", "means impartial; for 'not interested' write uninterested"),
    ("re:\\bto\\s+author\\b", "to write"),
    ("re:\\bless\\s+(?:people|items|bugs|errors|users|files|requests|words|mistakes|calories)\\b", "fewer (countable)"),
    ("re:\\bcould\\s+of\\b|\\bshould\\s+of\\b|\\bwould\\s+of\\b", "could have / should have / would have"),
]

AMBIGUOUS_CONTRACTIONS = [
    ("re:\\b(?:I|he|she|we|they|you|it)'d\\b", "'had' or 'would'? Readers may guess wrong"),
    ("re:\\b(?:could|should|would|might|must)'ve\\b", "invented contraction; write 'could have'"),
]

SLASH_PRONOUNS = [
    ("re:\\b(?:he/she|she/he|s/he|him/her|her/him|his/her|her/his|himself/herself)\\b", "never: recast with 'we', 'you', a plural, or drop the pronoun"),
]

PHRASE_GROUPS = [
    ("inflated", INFLATED),
    ("long-word", LONG_WORDS),
    ("verb-preposition", VERB_PREPOSITION),
    ("redundant", REDUNDANT),
    ("qualifier", QUALIFIERS),
    ("throat-clearing", THROAT_CLEARING),
    ("jargon", FAD_JARGON),
    ("journalese", JOURNALESE),
    ("cliche", [(p, "cliché: replace with a fresh phrase or a plain statement") for p in CLICHES]),
    ("travelese", [(p, "travelese: find the detail unique to this place") for p in TRAVELESE]),
    ("pre-label", PRE_LABELS),
    ("summary", SUMMARY_SIGNALS),
    ("usage", USAGE),
    ("contraction", AMBIGUOUS_CONTRACTIONS),
    ("slash-pronoun", SLASH_PRONOUNS),
]

ALL_CATEGORIES = [name for name, _ in PHRASE_GROUPS] + [
    "passive",
    "concept-nouns",
    "there-is",
    "however",
    "exclamation",
    "long-sentence",
    "long-paragraph",
]

IRREGULAR_PARTICIPLES = (
    "known|seen|done|made|given|taken|written|shown|built|found|held|kept|left|lost|paid|put|"
    "sent|set|told|understood|chosen|driven|broken|spoken|stolen|forgotten|hidden|begun|brought|"
    "bought|caught|taught|thought|felt|heard|met|read|run|said|sold|won|drawn|grown|thrown|worn|"
    "torn|born|borne|beaten|bitten|eaten|fallen|forgiven|frozen|ridden|risen|shaken|sung|sunk|"
    "swept|sworn|undertaken|withdrawn|overseen|overtaken|rewritten|led|fed|bred|bound|ground|hung|"
    "laid|lent|lit|meant|shut|spent|split|spread|struck|stuck|stung|wound|cut|hit|hurt|let|quit"
)
PASSIVE_RE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|get|gets|got|gotten)\s+(?:\w+ly\s+)?"
    r"(?:(?!need|feed|seed|speed|bleed|breed|proceed|exceed|succeed|indeed|red|bed|shed|wed|ted)\w{2,}ed|"
    + IRREGULAR_PARTICIPLES
    + r")\b"
    r"(?:\s+by\b)?",
    re.IGNORECASE,
)
PASSIVE_SKIP = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:interested|tired|excited|bored|married|"
    r"supposed|used|located|based|pleased|concerned|involved|related|qualified|scared|"
    r"worried|surprised|amazed|prepared|satisfied|dedicated|committed|determined|limited|"
    r"advanced|experienced|sophisticated|complicated|detailed|crowded|talented|organized|"
    r"skilled|retired|dressed|finished|done|gone)\b",
    re.IGNORECASE,
)

CONCEPT_NOUN_RE = re.compile(
    r"\b[a-z]{4,}(?:tion|sion|ment|ance|ence|ity|ness|ization|isation|ency|ancy)s?\b",
    re.IGNORECASE,
)
CONCEPT_NOUN_STOP = {
    "question", "questions", "mention", "nation", "station", "position", "section", "version",
    "moment", "moments", "comment", "comments", "government", "document", "documents",
    "element", "elements", "apartment", "department", "city", "cities", "business",
    "sentence", "sentences", "audience", "evidence", "science", "difference", "experience",
    "distance", "balance", "chance", "dance", "silence", "violence", "fence", "conference",
    "reference", "references", "sequence", "instance", "entrance", "commitment", "community",
    "university", "opportunity", "activity", "quality", "reality", "identity", "security",
    "authority", "majority", "minority", "priority", "property", "liberty", "society",
    "variety", "ability", "darkness", "witness", "illness", "kindness", "happiness", "attention",
    "direction", "information", "population", "education", "tradition", "condition",
    "function", "functions", "action", "actions", "option", "options", "motion", "emotion",
    "lotion", "potion", "portion", "fiction", "nonfiction", "fraction", "vision", "television",
    "decision", "occasion", "mission", "permission", "session", "passion", "tension",
    "pension", "mansion", "explosion", "confusion", "conclusion", "excitement", "payment",
    "equipment", "environment", "management", "statement", "agreement", "argument",
    "treatment", "development", "movement", "settlement", "tournament", "instrument",
    "ornament", "parliament", "sentiment", "segment", "fragment", "basement", "cement",
    "garment", "pavement", "punishment", "replacement", "requirement", "assignment",
    "appointment", "investment", "relationship", "importance", "performance", "insurance",
    "appearance", "ambulance", "allowance", "assistance", "existence", "presence", "absence",
    "patience", "intelligence", "independence", "influence", "license", "residence",
    "frequency", "emergency", "agency", "currency", "efficiency", "tendency", "policy",
}

THERE_IS_RE = re.compile(r"^\W*(?:(?:but|and|so|however|yet|still|now|today),?\s+)?(?:there\s+(?:is|are|was|were|will\s+be|has\s+been|have\s+been))\b", re.IGNORECASE)
HOWEVER_START_RE = re.compile(r"^\W*however\b", re.IGNORECASE)
HOWEVER_END_RE = re.compile(r"\bhowever\W*$", re.IGNORECASE)
EXCLAMATION_RE = re.compile(r"(?<![!\[])!(?![=\[(])")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
URL_RE = re.compile(r"https?://\S+|www\.\S+|\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"<[^>\n]+>")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*")
TABLE_OR_RULE_RE = re.compile(r"^\s*(?:\||[-*_]{3,}\s*$)")
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


@dataclass
class Flag:
    line: int
    column: int
    category: str
    text: str
    suggestion: str


def compile_rule(pattern: str) -> re.Pattern:
    if pattern.startswith("re:"):
        return re.compile(pattern[3:], re.IGNORECASE)
    parts = [re.escape(p) for p in pattern.split()]
    body = r"\s+".join(parts)
    return re.compile(r"(?<![\w'’-])" + body + r"(?![\w'’-])", re.IGNORECASE)


COMPILED_GROUPS = [
    (name, [(compile_rule(p), s) for p, s in rules]) for name, rules in PHRASE_GROUPS
]


def blank_out(text: str, pattern: re.Pattern) -> str:
    """Replace matches with spaces so column positions stay correct."""
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def prepare_lines(raw: str) -> list[str]:
    """Return lines with code, front matter, URLs and HTML blanked out."""
    lines = raw.splitlines()
    out: list[str] = []
    in_fence = False
    fence_marker = ""
    in_front_matter = bool(lines) and lines[0].strip() == "---"
    for i, line in enumerate(lines):
        if in_front_matter:
            out.append("")
            if i > 0 and line.strip() == "---":
                in_front_matter = False
            continue
        m = FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence, fence_marker = True, m.group(1)
            elif m.group(1) == fence_marker:
                in_fence = False
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        cleaned = blank_out(line, INLINE_CODE_RE)
        cleaned = blank_out(cleaned, URL_RE)
        cleaned = blank_out(cleaned, HTML_TAG_RE)
        out.append(cleaned)
    return out


def drop_nested(spans: list[tuple[int, int, Flag]]) -> list[Flag]:
    """Keep the most specific flag: drop any match lying inside a longer one."""
    kept = []
    for start, end, flag in spans:
        nested = any(
            s <= start and end <= e and (e - s) > (end - start)
            for s, e, _ in spans
        )
        if not nested:
            kept.append(flag)
    return kept


def phrase_flags(lines: list[str], enabled: set[str]) -> list[Flag]:
    flags: list[Flag] = []
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        spans: list[tuple[int, int, Flag]] = []
        seen: set[tuple[int, int, str]] = set()

        def add(m: re.Match, category: str, suggestion: str, text: str | None = None) -> None:
            key = (m.start(), m.end(), category)
            if key in seen or not m.group(0).strip():
                return
            seen.add(key)
            flag = Flag(lineno, m.start() + 1, category, text or m.group(0).strip(), suggestion)
            spans.append((m.start(), m.end(), flag))

        for category, rules in COMPILED_GROUPS:
            if category not in enabled:
                continue
            for regex, suggestion in rules:
                for m in regex.finditer(line):
                    add(m, category, suggestion)
        if "passive" in enabled:
            for m in PASSIVE_RE.finditer(line):
                if not PASSIVE_SKIP.match(m.group(0)):
                    add(m, "passive", "likely passive: who did it? Use an active verb "
                                      "unless there's no comfortable way around it")
        if "exclamation" in enabled:
            for m in EXCLAMATION_RE.finditer(line):
                add(m, "exclamation", "avoid: let word order create emphasis; never flag a joke", "!")
        flags.extend(drop_nested(spans))
    return flags


def paragraphs(lines: list[str]) -> list[list[tuple[int, str]]]:
    """Group prose lines into paragraphs. Headings, list items and table rows stand alone."""
    paras: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or TABLE_OR_RULE_RE.match(line):
            if current:
                paras.append(current)
                current = []
            continue
        if HEADING_RE.match(line) or LIST_ITEM_RE.match(line):
            if current:
                paras.append(current)
            current = []
            text = LIST_ITEM_RE.sub("", HEADING_RE.sub("", line))
            if LIST_ITEM_RE.match(line):
                current = [(lineno, text)]
            continue
        current.append((lineno, re.sub(r"^\s*>\s?", "", line)))
    if current:
        paras.append(current)
    return paras


def sentences_with_lines(para: list[tuple[int, str]], lines: list[str]) -> list[tuple[int, int, str]]:
    """Split a paragraph into sentences, returning (line, column, sentence)."""
    joined = ""
    starts: list[tuple[int, int, int]] = []
    for lineno, text in para:
        stripped = text.strip()
        indent = lines[lineno - 1].find(stripped[:20]) if stripped else 0
        starts.append((len(joined), lineno, max(indent, 0)))
        joined += stripped + " "
    result = []
    pos = 0
    for piece in SENTENCE_SPLIT_RE.split(joined):
        idx = joined.find(piece, pos)
        pos = idx + len(piece)
        if not piece.strip():
            continue
        off, line, indent = next(((o, ln, ind) for o, ln, ind in reversed(starts) if o <= idx), starts[0])
        result.append((line, indent + (idx - off) + 1, piece.strip()))
    return result


def structure_flags(lines: list[str], enabled: set[str], max_sentence: int, max_paragraph: int) -> tuple[list[Flag], int]:
    flags: list[Flag] = []
    total_words = 0
    for para in paragraphs(lines):
        para_words = sum(len(WORD_RE.findall(t)) for _, t in para)
        total_words += para_words
        if "long-paragraph" in enabled and para_words > max_paragraph:
            flags.append(Flag(para[0][0], 1, "long-paragraph", f"{para_words} words",
                              f"over {max_paragraph} words: writing is visual; consider a break where the thought turns"))
        for lineno, col, sentence in sentences_with_lines(para, lines):
            words = WORD_RE.findall(sentence)
            if "long-sentence" in enabled and len(words) > max_sentence:
                flags.append(Flag(lineno, col, "long-sentence", f"{len(words)} words: {sentence[:60]}…",
                                  f"over {max_sentence} words: probably two thoughts; break it at a natural joint"))
            if "concept-nouns" in enabled:
                nouns = [w for w in CONCEPT_NOUN_RE.findall(sentence) if w.lower() not in CONCEPT_NOUN_STOP]
                if len(nouns) >= 3 or (len(nouns) >= 2 and len(words) <= 12):
                    flags.append(Flag(lineno, col, "concept-nouns", ", ".join(nouns[:5]),
                                      "abstract nouns doing the verbs' work: who is doing what? Turn nouns back into verbs"))
            if "there-is" in enabled and THERE_IS_RE.match(sentence):
                flags.append(Flag(lineno, col, "there-is", THERE_IS_RE.match(sentence).group(0).strip(),
                                  "weak opener: lead with the real subject"))
            if "however" in enabled:
                if HOWEVER_START_RE.match(sentence):
                    flags.append(Flag(lineno, col, "however", "However…",
                                      "don't start with 'however' (wet dishrag); use 'But', or move it a few words in"))
                elif HOWEVER_END_RE.search(sentence):
                    flags.append(Flag(lineno, col, "however", "…however.",
                                      "'however' at the end has lost its howeverness; move it early"))
    return flags, total_words


def analyze(raw: str, enabled: set[str], max_sentence: int, max_paragraph: int) -> dict:
    lines = prepare_lines(raw)
    flags = phrase_flags(lines, enabled)
    sflags, words = structure_flags(lines, enabled, max_sentence, max_paragraph)
    flags.extend(sflags)
    flags.sort(key=lambda f: (f.line, f.column, f.category))
    counts = Counter(f.category for f in flags)
    phrase_flag_count = sum(v for k, v in counts.items() if k not in {"long-sentence", "long-paragraph", "concept-nouns"})
    return {
        "words": words,
        "flags": [asdict(f) for f in flags],
        "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "flags_per_100_words": round(100 * phrase_flag_count / words, 1) if words else 0.0,
    }


def render_text(result: dict, source: str, raw_lines: list[str]) -> str:
    out = []
    flags = result["flags"]
    if not flags:
        out.append(f"{source}: {result['words']} words, no flags. Still read it aloud.")
        return "\n".join(out)
    current_line = None
    for f in flags:
        if f["line"] != current_line:
            current_line = f["line"]
            snippet = raw_lines[current_line - 1].strip() if current_line - 1 < len(raw_lines) else ""
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."
            out.append(f"\n{source}:{current_line}: {snippet}")
        out.append(f"  col {f['column']:>3}  [{f['category']}] \"{f['text']}\" -> {f['suggestion']}")
    out.append("")
    out.append(f"Summary: {result['words']} words, {len(flags)} flags "
               f"({result['flags_per_100_words']} phrase flags per 100 words)")
    for cat, n in result["counts"].items():
        out.append(f"  {cat:<18} {n}")
    out.append("\nEach flag is a bracket, not a verdict: read the sentence without it and decide.")
    return "\n".join(out)


def parse_categories(value: str | None) -> set[str]:
    if not value:
        return set()
    cats = {c.strip() for c in value.split(",") if c.strip()}
    unknown = cats - set(ALL_CATEGORIES)
    if unknown:
        raise SystemExit(f"Unknown categories: {', '.join(sorted(unknown))}. "
                         f"Known: {', '.join(ALL_CATEGORIES)}")
    return cats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag likely clutter in prose (Zinsser's brackets, automated). "
                    f"Categories: {', '.join(ALL_CATEGORIES)}.")
    parser.add_argument("path", help="file to check, or '-' for stdin")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--only", help="comma-separated categories to include")
    parser.add_argument("--ignore", help="comma-separated categories to skip")
    parser.add_argument("--max-sentence-words", type=int, default=35)
    parser.add_argument("--max-paragraph-words", type=int, default=150)
    args = parser.parse_args(argv)

    if args.path == "-":
        raw = sys.stdin.read()
        source = "<stdin>"
    else:
        try:
            with open(args.path, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        source = args.path

    enabled = parse_categories(args.only) or set(ALL_CATEGORIES)
    enabled -= parse_categories(args.ignore)

    result = analyze(raw, enabled, args.max_sentence_words, args.max_paragraph_words)
    if args.json:
        result["source"] = source
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render_text(result, source, raw.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
