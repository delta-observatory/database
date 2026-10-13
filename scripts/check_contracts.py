"""Check every contract schema and example.

Each schema must be a valid draft 2020-12 schema. Each example file name
ends in .valid.json or .invalid.json, and the result must match the name.
Method parameter defaults must form a valid parameter document.

Run: uv run --with jsonschema==4.25.1 python scripts/check_contracts.py
"""
from pathlib import Path
import json
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1] / 'contracts'
EXAMPLE_SCHEMA = {
    'job': 'job/v1.schema.json',
    'result': 'result/v1.schema.json',
    'artifacts': 'artifacts/columns/v1.schema.json',
}


def load(path):
    return json.loads(path.read_text())


def defaults(schema):
    """Build a document from the 'default' keywords of an object schema."""
    if schema.get('type') == 'object':
        return {k: defaults(v) for k, v in schema['properties'].items()}
    return schema['default']


def method_schema(example):
    # examples/methods/<method-id>-<label>.<valid|invalid>.json
    for path in sorted((ROOT / 'methods').iterdir(), key=lambda p: -len(p.name)):
        if example.name.startswith(path.name + '-'):
            return path / 'v1.schema.json'
    raise SystemExit(f'no method schema for {example}')


def main():
    failures = []
    schemas = sorted(ROOT.rglob('*.schema.json'))
    for path in schemas:
        Draft202012Validator.check_schema(load(path))
    for path in sorted((ROOT / 'methods').glob('*/v*.schema.json')):
        schema = load(path)
        errors = list(Draft202012Validator(schema).iter_errors(defaults(schema)))
        if errors:
            failures.append(f'{path}: defaults are invalid: {errors[0].message}')
    examples = sorted((ROOT / 'examples').rglob('*.json'))
    for path in examples:
        kind = path.parent.name
        schema_path = method_schema(path) if kind == 'methods' else ROOT / EXAMPLE_SCHEMA[kind]
        errors = list(Draft202012Validator(load(schema_path)).iter_errors(load(path)))
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
