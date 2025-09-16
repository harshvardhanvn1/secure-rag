import warnings
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

from typing import List, Dict, Tuple
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Build an NLP engine using spaCy small English model
provider = NlpEngineProvider(nlp_configuration={
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
})
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
anonymizer = AnonymizerEngine()

# Entities we care about right now
SUPPORTED_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "PERSON",
    "US_SSN",
]

def redact_text(text: str, entities: List[str] = SUPPORTED_ENTITIES) -> str:
    """
    Detect PII entities and replace each with a typed tag like <EMAIL_ADDRESS>.
    """
    results = analyzer.analyze(text=text, entities=entities, language="en")
    if not results:
        return text

    ops = {
        r.entity_type: OperatorConfig("replace", {"new_value": f"<{r.entity_type}>"})
        for r in results
    }
    return anonymizer.anonymize(text=text, analyzer_results=results, operators=ops).text

def redact_and_report(text: str, entities: List[str] = SUPPORTED_ENTITIES) -> Tuple[str, Dict[str, int]]:
    """
    Return (redacted_text, counts_by_entity).
    counts_by_entity includes only the SUPPORTED_ENTITIES with non-zero counts.
    """
    results: List[RecognizerResult] = analyzer.analyze(text=text, entities=entities, language="en")
    if not results:
        return text, {}

    ops = {
        r.entity_type: OperatorConfig("replace", {"new_value": f"<{r.entity_type}>"})
        for r in results
    }
    redacted = anonymizer.anonymize(text=text, analyzer_results=results, operators=ops).text

    counts: Dict[str, int] = {}
    for r in results:
        counts[r.entity_type] = counts.get(r.entity_type, 0) + 1

    return redacted, counts
