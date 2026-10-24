"""Check every contract schema and example.

Each schema must be a valid draft 2020-12 schema. Each example file name
ends in .valid.json or .invalid.json, and the result must match the name.
Method parameter defaults must form a valid parameter document.
Record schemas refer to records/common/v1.schema.json. A registry of every
schema, keyed by its $id, resolves those references.

Run: uv run --with jsonschema==4.25.1 python scripts/check_contracts.py
"""
from pathlib import Path
import json
import sys

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1] / 'contracts'
EXAMPLE_SCHEMA = {
    'job': 'job/v1.schema.json',
    'result': 'result/v1.schema.json',
    'artifacts': 'artifacts/columns/v1.schema.json',
    'exports': 'exports/manifest/v1.schema.json',
}
PREFIXED = ('methods', 'records', 'inputs')


def load(path):
    return json.loads(path.read_text())


def defaults(schema):
    """Build a document from the 'default' keywords of an object schema."""
    if schema.get('type') == 'object':
        return {k: defaults(v) for k, v in schema['properties'].items()}
    return schema['default']


def prefixed_schema(example, kind):
    # examples/<methods|records|inputs>/<schema-directory>-<label>.<valid|invalid>.json
    for path in sorted((ROOT / kind).iterdir(), key=lambda p: -len(p.name)):
        if example.name.startswith(path.name + '-'):
            version = 2 if example.name.startswith(path.name + '-v2-') else 1
            return path / f'v{version}.schema.json'
    raise SystemExit(f'no {kind} schema for {example}')


def validator(schema, registry):
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def main():
    failures = []
    schemas = sorted(ROOT.rglob('*.schema.json'))
    for path in schemas:
        Draft202012Validator.check_schema(load(path))
    registry = Registry().with_resources((load(p)['$id'], Resource.from_contents(load(p))) for p in schemas)
    for path in sorted((ROOT / 'methods').glob('*/v*.schema.json')):
        schema = load(path)
        errors = list(Draft202012Validator(schema).iter_errors(defaults(schema)))
        if errors:
            failures.append(f'{path}: defaults are invalid: {errors[0].message}')
    examples = sorted((ROOT / 'examples').rglob('*.json'))
    for path in examples:
        kind = path.parent.name
        schema_path = prefixed_schema(path, kind) if kind in PREFIXED else ROOT / EXAMPLE_SCHEMA[kind]
        errors = list(validator(load(schema_path), registry).iter_errors(load(path)))
        expected_valid = path.name.endswith('.valid.json')
        if not expected_valid and not path.name.endswith('.invalid.json'):
            failures.append(f'{path}: name must end in .valid.json or .invalid.json')
        elif expected_valid and errors:
            failures.append(f'{path}: expected valid: {errors[0].message}')
        elif not expected_valid and not errors:
            failures.append(f'{path}: expected invalid, but it passed')
    for failure in failures:
        print('FAIL', failure)
    print(f'{len(schemas)} schemas, {len(examples)} examples, {len(failures)} failures')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
