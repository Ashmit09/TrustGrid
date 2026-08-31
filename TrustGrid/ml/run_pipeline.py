"""
TrustGrid ML Pipeline — Master Runner.

Runs the complete ML pipeline in order:
  1. Generate synthetic dataset
  2. Train buyer reliability model
  3. Train seller reliability model

Usage
-----
  cd TrustGrid
  python ml/run_pipeline.py

The trained models are saved to ml/models/ and will be loaded by the
FastAPI backend when computing ML-assisted trust scores.

Note on retraining
------------------
This pipeline is designed for offline training. In production, the model
would be retrained periodically as new behavioral data accumulates.
For this prototype, we train once and load the saved model for inference.
"""
import sys
from pathlib import Path
import time

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    start = time.time()
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + "   TrustGrid ML Pipeline".center(58) + "║")
    print("╚" + "═" * 58 + "╝\n")

    # Step 1 — Generate dataset
    print("STEP 1: Generating synthetic dataset")
    print("─" * 60)
    from ml.dataset.generate_dataset import main as gen_main
    gen_main()

    # Step 2 — Train buyer model
    print("\n\nSTEP 2: Training buyer reliability model")
    print("─" * 60)
    from ml.training.train_buyer import train_buyer_model
    train_buyer_model()

    # Step 3 — Train seller model
    print("\n\nSTEP 3: Training seller reliability model")
    print("─" * 60)
    from ml.training.train_seller import train_seller_model
    train_seller_model()

    elapsed = time.time() - start
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + f"  Pipeline complete in {elapsed:.1f}s".center(58) + "║")
    print("║" + "  Models saved to ml/models/".center(58) + "║")
    print("╚" + "═" * 58 + "╝\n")


if __name__ == "__main__":
    main()
