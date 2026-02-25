"""
validate_ontology.py

Checks the ontology for logical consistency using HermiT via owlready2.
This script validates the TBox (schema) only - not instance data.
Run when ontology.ttl changes, not as part of the enrichment pipeline.

Inputs:
    ontology/ontology.ttl - OWL ontology

Outputs:
    logs/validate_ontology.log - operational log

Usage:
    python pipeline/validate_ontology.py
"""

import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from rdflib import Graph

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
ONTOLOGY_PATH = ROOT / "ontology" / "ontology.ttl"
LOG_PATH = ROOT / "logs" / "validate_ontology.log"

# ─── Logging ──────────────────────────────────────────────────────────────────

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ─── Locate HermiT jar ────────────────────────────────────────────────────────


def find_hermit_jar():
    """Locate the HermiT jar bundled with owlready2."""
    try:
        import owlready2

        hermit_dir = Path(owlready2.__file__).parent / "hermit"
        hermit_jar = hermit_dir / "HermiT.jar"
        if not hermit_jar.exists():
            log.error("HermiT jar not found at %s", hermit_jar)
            sys.exit(1)
        return str(hermit_dir), str(hermit_jar)
    except ImportError:
        log.error("owlready2 is not installed - run: pip install owlready2")
        sys.exit(1)


# ─── Convert Turtle to RDF/XML ────────────────────────────────────────────────


def convert_to_rdfxml(ontology_path):
    """
    Parse ontology Turtle with rdflib and serialize to a temporary
    RDF/XML file for HermiT. Returns the temp file path.
    """
    log.info("Parsing ontology from %s", ontology_path)
    graph = Graph()
    graph.parse(ontology_path, format="turtle")
    log.info("Loaded %d triples", len(graph))

    tmp = tempfile.NamedTemporaryFile(suffix=".owl", delete=False)
    graph.serialize(tmp.name, format="xml")
    log.info("Serialized to temporary RDF/XML at %s", tmp.name)
    return tmp.name


# ─── Run HermiT ───────────────────────────────────────────────────────────────


def run_hermit(hermit_dir, hermit_jar, rdfxml_path):
    """
    Run HermiT consistency check against the RDF/XML ontology file.
    Returns the subprocess result.
    """
    log.info("Running HermiT consistency check...")
    result = subprocess.run(
        [
            "java",
            "-cp",
            f"{hermit_dir}:{hermit_jar}",
            "org.semanticweb.HermiT.cli.CommandLine",
            "-c",
            "--verbose",
            "-I",
            f"file://{rdfxml_path}",
        ],
        capture_output=True,
        text=True,
    )
    return result


# ─── Parse HermiT output ──────────────────────────────────────────────────────


def parse_result(result):
    """
    Interpret HermiT exit code and output.
    Exit code 0 = consistent. Exit code 1 = inconsistent or error.
    """
    if result.returncode == 0:
        log.info("Ontology is consistent - no issues found")
        return True

    # distinguish inconsistency from other errors
    stderr = result.stderr or ""
    if "InconsistentOntologyException" in stderr:
        log.error("INCONSISTENCY DETECTED")
        log.error("HermiT output:")
        for line in stderr.splitlines():
            log.error("  %s", line)
    else:
        log.error("HermiT encountered an error:")
        for line in stderr.splitlines():
            log.error("  %s", line)

    return False


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    """
    Entry point. Converts ontology to RDF/XML, runs HermiT consistency
    check, logs result. Exits non-zero if inconsistency detected.
    """
    log.info("=== validate_ontology.py starting ===")

    hermit_dir, hermit_jar = find_hermit_jar()
    rdfxml_path = convert_to_rdfxml(ONTOLOGY_PATH)

    try:
        result = run_hermit(hermit_dir, hermit_jar, rdfxml_path)
        consistent = parse_result(result)
    finally:
        Path(rdfxml_path).unlink(missing_ok=True)

    log.info("=== validate_ontology.py complete ===")
    sys.exit(0 if consistent else 1)


if __name__ == "__main__":
    main()
