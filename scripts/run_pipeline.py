"""One-shot: generate data, train, evaluate held-out test."""

from __future__ import annotations

from data.synthetic.generator import generate_all
from ml.training.train import train_and_select


def main() -> None:
    print("Generating synthetic splits...")
    print(generate_all())
    print("Training + final held-out evaluation...")
    print(train_and_select(run_test=True))


if __name__ == "__main__":
    main()
