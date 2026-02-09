import json
from pathlib import Path
from tax import marginal_rate_table_by_input, marginal_rate_table_by_tag

BASE_DIR = Path(__file__).resolve().parent
PRIVATE_DIR = BASE_DIR.parent / 'private'


def load_inputs(year):
    with (PRIVATE_DIR / f'inputs_{year}.json').open('r') as f:
        return json.load(f)


def load_policy(year):
    with (BASE_DIR / f'policy_{year}.json').open('r') as f:
        return json.load(f)


def main(year, mode):
    inputs = load_inputs(year)
    policy = load_policy(year)
    if mode == 'input':
        table = marginal_rate_table_by_input(inputs, policy)
    elif mode == 'tag':
        table = marginal_rate_table_by_tag(inputs, policy)
    else:
        raise ValueError(f"Unsupported mode '{mode}'. Use 'input' or 'tag'.")
    print(table)

# LEAVE THESE HARD CODED!
year = 2024
mode = "input"
# mode = "tag"
main(year, mode)
